import hashlib
import hmac
import json
import random
import secrets
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from chase201.catalog import COMPOSITION, ROLES
from chase201.config import get_settings
from chase201.draft_rules import SIMPLE_SELECTIONS, draft_offers, opponent_players, rating_band
from chase201.models import (
    BattingPerformance,
    BowlingPerformance,
    CatalogVersion,
    Decision,
    Draft,
    DraftOffer,
    DraftSlot,
    Idempotency,
    Match,
    MatchEvent,
    Player,
    Selection,
    Session,
    SimulationProfile,
    Team,
    TeamMember,
    now,
    uid,
)
from chase201.schemas import LegacyStrategyDecision, StrategyDecision, V2StrategyDecision
from chase201.timing import timed
from chase201.tradeoffs import (
    TRADEOFF_SELECTION,
    DraftProfile,
    playstyle,
    shuffled_allocation,
    validate_allocation,
)
from chase_engine import engine as v3_engine
from chase_engine import legacy
from chase_engine.engine import (
    GameState,
    PlayerProfile,
)
from chase_engine.types import BowlingStyle, Transition
from chase_engine.v2 import engine as v2_engine
from chase_engine.v31 import engine as v31_engine
from chase_engine.v31.types import BowlingStyle as SimpleBowlingStyle
from chase_engine.v32 import engine as v32_engine
from chase_engine.v33 import engine as v33_engine
from chase_engine.v34 import engine as v34_engine
from chase_engine.v35 import engine as v35_engine

THREE_MODE_RULESETS = {"v3.0", "v3.1", "v3.2", "v3.3", "v3.4", "v3.5"}
SIMPLE_RULESETS = {"v3.1", "v3.2", "v3.3", "v3.4", "v3.5"}


def engine_for(ruleset: str) -> Any:
    if ruleset == "v3.5":
        return v35_engine
    if ruleset == "v3.4":
        return v34_engine
    if ruleset == "v3.3":
        return v33_engine
    if ruleset == "v3.2":
        return v32_engine
    if ruleset == "v3.1":
        return v31_engine
    return v3_engine if ruleset == "v3.0" else v2_engine


def owned(item: Draft | Match, principal: Session) -> None:
    if principal.kind == "guest" and item.created_at.replace(tzinfo=UTC) <= now() - timedelta(
        days=30
    ):
        raise HTTPException(404, "This guest game has expired")
    if not (
        (principal.user_id and item.user_id == principal.user_id)
        or (principal.kind == "guest" and item.session_id == principal.id and item.user_id is None)
    ):
        raise HTTPException(404, "Not found")


async def get_draft(
    db: AsyncSession, draft_id: str, principal: Session, lock: bool = False
) -> Draft:
    q = select(Draft).where(Draft.id == draft_id)
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    draft = await db.scalar(q)
    if not draft:
        raise HTTPException(404, "Draft not found")
    owned(draft, principal)
    return draft


async def get_match(
    db: AsyncSession, match_id: str, principal: Session, lock: bool = False
) -> Match:
    q = select(Match).where(Match.id == match_id)
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    match = await db.scalar(q)
    if not match:
        raise HTTPException(404, "Match not found")
    owned(match, principal)
    return match


def check_revision(item: Draft | Match | Session, expected: int) -> None:
    if item.revision != expected:
        raise HTTPException(409, "State changed. Refresh and try your decision again.")


def fingerprint(body: dict) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def replay(
    db: AsyncSession, principal: Session, key: str, scope: str, body: dict
) -> dict | None:
    actor = f"user:{principal.user_id}" if principal.user_id else f"guest:{principal.id}"
    item = await db.get(Idempotency, (actor, key, scope))
    if item:
        if item.fingerprint != fingerprint(body):
            raise HTTPException(
                409, "This idempotency key was already used with a different request"
            )
        return item.response
    return None


def remember(
    db: AsyncSession, principal: Session, key: str, scope: str, body: dict, result: dict
) -> dict:
    actor = f"user:{principal.user_id}" if principal.user_id else f"guest:{principal.id}"
    db.add(
        Idempotency(
            actor=actor, key=key, scope=scope, fingerprint=fingerprint(body), response=result
        )
    )
    return result


def summary(
    player: Player, profile: SimulationProfile | None = None, simple: bool = False
) -> dict[str, Any]:
    return {
        "id": player.id,
        "name": player.name,
        "role": player.role,
        "overallRating": player.overall_rating,
        **({"battingRating": profile.batting} if profile is not None and not simple else {}),
        **(
            {
                "battingPlaystyle": playstyle(
                    (profile.batting_control, profile.batting_rotation, profile.batting_power)
                ),
                "battingControl": profile.batting_control,
                "battingRotation": profile.batting_rotation,
                "battingPower": profile.batting_power,
            }
            if profile is not None and not simple
            else {}
        ),
    }


async def draft_view(db: AsyncSession, draft: Draft) -> dict:
    rows = (
        await db.execute(
            select(DraftSlot, Player, SimulationProfile, Selection.player_id)
            .outerjoin(DraftOffer, DraftOffer.slot_id == DraftSlot.id)
            .outerjoin(Player, Player.id == DraftOffer.player_id)
            .outerjoin(SimulationProfile, SimulationProfile.player_id == Player.id)
            .outerjoin(Selection, Selection.slot_id == DraftSlot.id)
            .where(DraftSlot.draft_id == draft.id)
            .order_by(DraftSlot.position, Player.id)
        )
    ).all()
    slots: dict[str, dict] = {}
    for slot, player, profile, selected_id in rows:
        if slot.id not in slots:
            band = rating_band(slot.position, draft.selection_ruleset)
            slots[slot.id] = {
                "id": slot.id,
                "role": slot.role,
                "position": slot.position,
                "options": [],
                "selectedPlayerId": selected_id,
                "ratingLabel": band.label,
                "minimumRating": band.minimum,
                "maximumRating": band.maximum,
            }
        if player is not None and profile is not None:
            slots[slot.id]["options"].append(
                summary(player, profile, draft.selection_ruleset in SIMPLE_SELECTIONS)
            )
    match_id = (
        await db.scalar(
            select(Match.id).join(Team, Team.id == Match.team_id).where(Team.draft_id == draft.id)
        )
        if draft.status == "CONFIRMED"
        else None
    )
    return {
        "id": draft.id,
        "revision": draft.revision,
        "status": draft.status,
        "catalogVersion": draft.catalog_id,
        "selectionRuleset": draft.selection_ruleset,
        "battingOrder": draft.batting_order,
        "matchId": match_id,
        "slots": list(slots.values()),
    }


async def create_draft(db: AsyncSession, principal: Session, expected: int) -> Draft:
    check_revision(principal, expected)
    with timed("catalog"):
        catalog_rows = (
            await db.execute(
                select(CatalogVersion, Player)
                .outerjoin(Player, Player.catalog_id == CatalogVersion.id)
                .where(CatalogVersion.id == get_settings().catalog_version)
            )
        ).all()
    version = catalog_rows[0][0] if catalog_rows else None
    if not version or (get_settings().environment == "production" and not version.approved):
        raise HTTPException(503, "The player catalog is not ready")
    if version.selection_ruleset not in {TRADEOFF_SELECTION, *SIMPLE_SELECTIONS}:
        raise HTTPException(503, "New drafts require a validated simple or tradeoff catalog")
    catalog = [player for _, player in catalog_rows if player is not None]
    draft = Draft(
        session_id=None if principal.user_id else principal.id,
        user_id=principal.user_id,
        catalog_id=version.id,
        selection_ruleset=version.selection_ruleset,
    )
    db.add(draft)
    with timed("draft_write"):
        await db.flush()
    try:
        if version.selection_ruleset in SIMPLE_SELECTIONS:
            offers = draft_offers(catalog, secrets.SystemRandom(), version.selection_ruleset)
        else:
            profiles = await engine_team(db, [p.id for p in catalog])
            validate_allocation(
                [
                    DraftProfile(
                        p.id,
                        p.role,
                        p.overall,
                        (p.batting_control, p.batting_rotation, p.batting_power),
                    )
                    for p in profiles
                ],
                version.offer_allocation,
            )
            by_id = {p.id: p for p in catalog}
            offers = [
                [by_id[i] for i in group]
                for group in shuffled_allocation(version.offer_allocation, secrets.SystemRandom())
            ]
    except ValueError as error:
        raise HTTPException(503, str(error)) from error
    slots = [
        DraftSlot(id=uid(), draft_id=draft.id, position=position, role=role)
        for position, role in enumerate(ROLES)
    ]
    db.add_all(slots)
    with timed("draft_write"):
        await db.flush()
    db.add_all(
        DraftOffer(slot_id=slot.id, player_id=player.id)
        for slot, options in zip(slots, offers, strict=True)
        for player in options
    )
    principal.revision += 1
    with timed("draft_write"):
        await db.flush()
    return draft


async def select_player(db: AsyncSession, draft: Draft, slot_id: str, player_id: str) -> None:
    previous_selection = aliased(Selection)
    player_selection = aliased(Selection)
    row = (
        await db.execute(
            select(DraftSlot, Player, previous_selection, player_selection)
            .join(DraftOffer, DraftOffer.slot_id == DraftSlot.id)
            .join(Player, Player.id == DraftOffer.player_id)
            .outerjoin(previous_selection, previous_selection.slot_id == DraftSlot.id)
            .outerjoin(
                player_selection,
                and_(
                    player_selection.draft_id == draft.id,
                    player_selection.player_id == player_id,
                ),
            )
            .where(DraftSlot.id == slot_id, DraftOffer.player_id == player_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(422, "Choose a player from this slot's five options")
    slot, player, choice, previous_player_choice = row
    if slot.draft_id != draft.id or player.role != slot.role:
        raise HTTPException(422, "Choose a player from this slot's five options")
    validate_rating(draft, slot, player)
    if previous_player_choice and previous_player_choice.slot_id != slot_id:
        raise HTTPException(422, "A player can only be selected once")
    if choice:
        choice.player_id = player_id
    else:
        db.add(Selection(slot_id=slot_id, draft_id=draft.id, player_id=player_id))
    draft.batting_order = []


def validate_rating(draft: Draft, slot: DraftSlot, player: Player) -> None:
    band = rating_band(slot.position, draft.selection_ruleset)
    if not band.minimum <= player.overall_rating <= band.maximum:
        raise HTTPException(
            422,
            f"This {band.label.lower()} slot requires a rating of {band.minimum}–{band.maximum}",
        )


async def validate_order(db: AsyncSession, draft: Draft, order: list[str]) -> None:
    rows = (
        await db.execute(
            select(Selection, DraftSlot, Player)
            .join(DraftSlot, Selection.slot_id == DraftSlot.id)
            .join(Player, Player.id == Selection.player_id)
            .where(Selection.draft_id == draft.id)
        )
    ).all()
    ids = [choice.player_id for choice, _, _ in rows]
    if len(ids) != 11 or len(set(ids)) != 11 or len(order) != 11 or set(order) != set(ids):
        raise HTTPException(
            422, "Batting order must contain all eleven selected players exactly once"
        )
    if Counter(player.role for _, _, player in rows) != COMPOSITION:
        raise HTTPException(
            422, "XI must contain 5 batters, 1 keeper, 2 all-rounders and 3 bowlers"
        )
    offered = set(
        (
            await db.execute(
                select(DraftOffer.slot_id, DraftOffer.player_id).where(
                    DraftOffer.slot_id.in_([slot.id for _, slot, _ in rows])
                )
            )
        ).all()
    )
    for choice, slot, player in rows:
        validate_rating(draft, slot, player)
        if slot.role != player.role or (slot.id, choice.player_id) not in offered:
            raise HTTPException(422, "Selected player does not belong to the slot's offers")


async def confirm_team(db: AsyncSession, draft: Draft) -> None:
    await validate_order(db, draft, draft.batting_order)
    team = Team(draft_id=draft.id)
    db.add(team)
    await db.flush()
    for position, player_id in enumerate(draft.batting_order):
        db.add(TeamMember(team_id=team.id, player_id=player_id, position=position))
    draft.status = "CONFIRMED"


async def engine_team(db: AsyncSession, ids: list[str], ruleset: str = "v3.0") -> list[Any]:
    rows = (
        await db.execute(
            select(Player, SimulationProfile)
            .join(SimulationProfile, SimulationProfile.player_id == Player.id)
            .where(Player.id.in_(ids))
        )
    ).all()
    profiles = {p.id: engine_profile(p, profile, ruleset) for p, profile in rows}
    return [profiles[i] for i in ids]


def engine_profile(player: Player, profile: SimulationProfile, ruleset: str) -> Any:
    return (
        v31_engine.PlayerProfile(
            id=player.id,
            role=player.role,
            overall=player.overall_rating,
            batting=75 if ruleset in {"v3.4", "v3.5"} else profile.batting,
            bowling_control=profile.bowling_control,
            bowling_threat=profile.bowling_threat,
            bowling_style=SimpleBowlingStyle(profile.bowling_style),
        )
        if ruleset in SIMPLE_RULESETS
        else PlayerProfile(
            player.id,
            player.role,
            player.overall_rating,
            profile.batting_control,
            profile.batting_rotation,
            profile.batting_power,
            profile.bowling_control,
            profile.bowling_threat,
            BowlingStyle(profile.bowling_style),
        )
    )


@dataclass
class MatchPeople:
    ids: list[str]
    players: dict[str, Player]
    profiles: dict[str, SimulationProfile]

    def engine_team(self, ids: list[str], ruleset: str) -> list[Any]:
        return [engine_profile(self.players[i], self.profiles[i], ruleset) for i in ids]

    def legacy_team(self, ids: list[str]) -> list[legacy.Player]:
        return [
            legacy.Player(
                i, self.profiles[i].batting, self.profiles[i].bowling, self.players[i].role
            )
            for i in ids
        ]


async def load_match_people(db: AsyncSession, match: Match) -> MatchPeople:
    ids = [entry["player_id"] for entry in match.state["batting"]]
    with timed("roster"):
        rows = (
            await db.execute(
                select(Player, SimulationProfile)
                .join(SimulationProfile, SimulationProfile.player_id == Player.id)
                .where(Player.id.in_([*ids, *match.opponent]))
            )
        ).all()
    return MatchPeople(
        ids,
        {player.id: player for player, _ in rows},
        {player.id: profile for player, profile in rows},
    )


async def legacy_team(db: AsyncSession, ids: list[str]) -> list[legacy.Player]:
    rows = (
        await db.execute(
            select(Player, SimulationProfile)
            .join(SimulationProfile, SimulationProfile.player_id == Player.id)
            .where(Player.id.in_(ids))
        )
    ).all()
    profiles = {
        p.id: legacy.Player(p.id, profile.batting, profile.bowling, p.role) for p, profile in rows
    }
    return [profiles[i] for i in ids]


async def team_ids(db: AsyncSession, team_id: str) -> list[str]:
    return list(
        (
            await db.scalars(
                select(TeamMember.player_id)
                .where(TeamMember.team_id == team_id)
                .order_by(TeamMember.position)
            )
        ).all()
    )


async def create_match(db: AsyncSession, draft: Draft, principal: Session) -> Match:
    if draft.status != "CONFIRMED":
        raise HTTPException(409, "Confirm your XI first")
    team = await db.scalar(select(Team).where(Team.draft_id == draft.id))
    assert team
    existing = await db.scalar(select(Match).where(Match.team_id == team.id))
    if existing:
        raise HTTPException(409, "This XI already has a match; draft a new XI to play again")
    ids = await team_ids(db, team.id)
    await validate_order(db, draft, ids)
    catalog = list(
        (await db.scalars(select(Player).where(Player.catalog_id == draft.catalog_id))).all()
    )
    opponent = [p.id for p in opponent_players(catalog, secrets.SystemRandom())]
    ruleset = "v3.5" if draft.selection_ruleset in SIMPLE_SELECTIONS else "v3.0"
    state = engine_for(ruleset).initial_state(
        await engine_team(db, ids, ruleset), await engine_team(db, opponent, ruleset)
    )
    match = Match(
        team_id=team.id,
        session_id=None if principal.user_id else principal.id,
        user_id=principal.user_id,
        opponent=opponent,
        seed=secrets.token_hex(32),
        state=asdict(state),
        ruleset=ruleset,
    )
    db.add(match)
    draft.revision += 1
    await db.flush()
    await persist_scorecard(db, match, state)
    return match


async def persist_scorecard(
    db: AsyncSession, match: Match, state: GameState | legacy.GameState
) -> None:
    groups: list[
        tuple[type[BattingPerformance] | type[BowlingPerformance], list[dict[str, Any]]]
    ] = [
        (BattingPerformance, [asdict(entry) for entry in state.batting]),
        (BowlingPerformance, [asdict(entry) for entry in state.bowling]),
    ]
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"Scorecard upsert is unsupported on {dialect}")
    insert = postgres_insert if dialect == "postgresql" else sqlite_insert
    with timed("scorecard"):
        for entity, entries in groups:
            rows = [{"match_id": match.id, **values} for values in entries]
            statement = insert(entity).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=[entity.match_id, entity.player_id],
                set_={
                    key: getattr(statement.excluded, key)
                    for key in entries[0]
                    if key != "player_id"
                },
            )
            await db.execute(statement)


async def advance_match(
    db: AsyncSession,
    match: Match,
    decision: StrategyDecision | V2StrategyDecision | LegacyStrategyDecision,
    people: MatchPeople | None = None,
) -> list[dict[str, Any]]:
    if match.state["status"] != "LIVE":
        raise HTTPException(409, "This match has finished")
    seed = hmac.new(
        bytes.fromhex(match.seed),
        f"{match.id}:{match.revision}:{match.ruleset}".encode(),
        hashlib.sha256,
    ).digest()
    if people is None:
        people = await load_match_people(db, match)
    ids = people.ids
    if match.ruleset == "v1.0":
        if not isinstance(decision, LegacyStrategyDecision):
            raise HTTPException(422, "This saved match uses the original intent and risk controls")
        old_state = legacy.GameState.from_dict(match.state)
        transition: Transition | legacy.Transition = legacy.simulate_step(
            old_state,
            people.legacy_team(ids),
            people.legacy_team(match.opponent),
            legacy.Strategy(decision.intent, decision.riskFocus),
            legacy.decision_window(old_state.balls),
            legacy.RULESETS[match.ruleset],
            random.Random(seed),
        )
        row = Decision(
            match_id=match.id,
            revision=match.revision + 1,
            intent=decision.intent,
            risk_focus=decision.riskFocus,
        )
    else:
        engine = engine_for(match.ruleset)
        if (
            isinstance(decision, LegacyStrategyDecision)
            or decision.strategy.value not in engine.StrategyId.__members__
        ):
            raise HTTPException(
                422,
                "Choose Defensive, Balanced or Aggressive"
                if match.ruleset in THREE_MODE_RULESETS
                else "This saved match uses its original five plans",
            )
        state = engine.GameState.from_dict(match.state)
        rules = engine.RULESETS[match.ruleset]
        transition = engine.simulate_step(
            state,
            people.engine_team(ids, match.ruleset),
            people.engine_team(match.opponent, match.ruleset),
            engine.StrategyId(decision.strategy.value),
            engine.window_for(state, rules).max_legal_balls,
            rules,
            random.Random(seed),
        )
        row = Decision(
            match_id=match.id,
            revision=match.revision + 1,
            strategy=decision.strategy.value,
            context_summary=transition.events[0]["contextBefore"],
        )
    match.revision += 1
    db.add(row)
    new_events = []
    for sequence, event in enumerate(transition.events):
        db.add(
            MatchEvent(match_id=match.id, revision=match.revision, sequence=sequence, payload=event)
        )
        new_events.append({"revision": match.revision, "sequence": sequence, **event})
    match.state = asdict(transition.state)
    if transition.state.status != "LIVE":
        match.completed_at = now()
    await persist_scorecard(db, match, transition.state)
    await db.flush()
    return new_events


async def events_view(db: AsyncSession, match_id: str, after_revision: int = 0) -> list[dict]:
    events = (
        await db.scalars(
            select(MatchEvent)
            .where(MatchEvent.match_id == match_id, MatchEvent.revision > after_revision)
            .order_by(MatchEvent.revision, MatchEvent.sequence)
        )
    ).all()
    return [{"revision": e.revision, "sequence": e.sequence, **e.payload} for e in events]


async def match_view(
    db: AsyncSession,
    match: Match,
    people: MatchPeople | None = None,
    after_revision: int = 0,
    events: list[dict[str, Any]] | None = None,
) -> dict:
    if people is None:
        people = await load_match_people(db, match)
    ids = people.ids
    players = people.players
    display_profiles = people.profiles
    contextual: dict[str, Any] = {"context": None, "strategyAssessments": [], "upcomingBowlers": []}
    if match.ruleset == "v1.0":
        target = legacy.RULESETS[match.ruleset].target
        window_size = (
            legacy.decision_window(match.state["balls"]) if match.state["status"] == "LIVE" else 0
        )
    else:
        engine = engine_for(match.ruleset)
        rules = engine.RULESETS[match.ruleset]
        target = rules.target
        state = engine.GameState.from_dict(match.state)
        window_size = engine.window_for(state, rules).max_legal_balls
        if state.status == "LIVE":
            batters = {p.id: p for p in people.engine_team(ids, match.ruleset)}
            bowlers = {p.id: p for p in people.engine_team(match.opponent, match.ruleset)}
            batter = batters[state.batting[state.striker].player_id]
            partner = batters[state.batting[state.non_striker].player_id]
            bowler = bowlers[engine.current_bowler(state).player_id]
            contextual["context"] = engine.context_summary(
                state, engine.derive_context(state, batter, partner, bowler, rules), rules
            )
            for strategy in engine.StrategyId:
                outcomes = engine.distribution(state, batter, partner, bowler, strategy, rules)
                assessment = engine.assess(strategy, outcomes, rules)
                contextual["strategyAssessments"].append(
                    {
                        "strategy": strategy.value,
                        "scoring": assessment.scoring_band,
                        "wicketRisk": assessment.wicket_risk_band,
                        "boundary": assessment.boundary_band,
                        **(
                            {"wicketProbability": outcomes.wicket_probability}
                            if match.ruleset in THREE_MODE_RULESETS
                            else {}
                        ),
                    }
                )
            for over in range(state.balls // 6, (state.balls + window_size - 1) // 6 + 1):
                player_id = state.bowling[over % len(state.bowling)].player_id
                contextual["upcomingBowlers"].append(
                    {
                        **summary(
                            players[player_id],
                            display_profiles[player_id],
                            match.ruleset in SIMPLE_RULESETS,
                        ),
                        "style": bowlers[player_id].bowling_style.value,
                        "over": over + 1,
                    }
                )
    return {
        "id": match.id,
        "revision": match.revision,
        "rulesetVersion": match.ruleset,
        "target": target,
        "decisionWindow": window_size,
        **contextual,
        "state": {key: value for key, value in match.state.items() if key != "recent_approaches"},
        "team": [
            summary(players[i], display_profiles[i], match.ruleset in SIMPLE_RULESETS) for i in ids
        ],
        "opponent": [
            summary(players[i], display_profiles[i], match.ruleset in SIMPLE_RULESETS)
            for i in match.opponent
        ],
        "events": events if events is not None else await events_view(db, match.id, after_revision),
        "createdAt": match.created_at.replace(tzinfo=UTC).isoformat(),
    }
