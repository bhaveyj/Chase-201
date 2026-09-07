import hashlib
import hmac
import json
import random
import secrets
from collections import Counter
from dataclasses import asdict
from datetime import UTC, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chase201.catalog import COMPOSITION, ROLES
from chase201.config import get_settings
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
)
from chase_engine.engine import (
    RULESETS,
    GameState,
    Strategy,
    decision_window,
    initial_state,
    simulate_step,
)
from chase_engine.engine import Player as EnginePlayer


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


def summary(player: Player) -> dict[str, Any]:
    return {
        "id": player.id,
        "name": player.name,
        "role": player.role,
        "overallRating": player.overall_rating,
    }


async def draft_view(db: AsyncSession, draft: Draft) -> dict:
    slots = (
        await db.scalars(
            select(DraftSlot).where(DraftSlot.draft_id == draft.id).order_by(DraftSlot.position)
        )
    ).all()
    offers = (
        await db.execute(
            select(DraftOffer.slot_id, Player)
            .join(Player, Player.id == DraftOffer.player_id)
            .join(DraftSlot, DraftSlot.id == DraftOffer.slot_id)
            .where(DraftSlot.draft_id == draft.id)
            .order_by(Player.id)
        )
    ).all()
    choices = {
        slot_id: player_id
        for slot_id, player_id in (
            await db.execute(
                select(Selection.slot_id, Selection.player_id).where(Selection.draft_id == draft.id)
            )
        ).all()
    }
    match_id = await db.scalar(
        select(Match.id).join(Team, Team.id == Match.team_id).where(Team.draft_id == draft.id)
    )
    return {
        "id": draft.id,
        "revision": draft.revision,
        "status": draft.status,
        "catalogVersion": draft.catalog_id,
        "battingOrder": draft.batting_order,
        "matchId": match_id,
        "slots": [
            {
                "id": slot.id,
                "role": slot.role,
                "position": slot.position,
                "options": [summary(p) for slot_id, p in offers if slot_id == slot.id],
                "selectedPlayerId": choices.get(slot.id),
            }
            for slot in slots
        ],
    }


async def create_draft(db: AsyncSession, principal: Session, expected: int) -> Draft:
    check_revision(principal, expected)
    version = await db.get(CatalogVersion, get_settings().catalog_version)
    if not version or (get_settings().environment == "production" and not version.approved):
        raise HTTPException(503, "The player catalog is not ready")
    draft = Draft(
        session_id=None if principal.user_id else principal.id,
        user_id=principal.user_id,
        catalog_id=version.id,
    )
    db.add(draft)
    await db.flush()
    catalog = list((await db.scalars(select(Player).where(Player.catalog_id == version.id))).all())
    pools = {role: [p for p in catalog if p.role == role] for role in COMPOSITION}
    rng = secrets.SystemRandom()
    for pool in pools.values():
        rng.shuffle(pool)
    for position, role in enumerate(ROLES):
        slot = DraftSlot(draft_id=draft.id, position=position, role=role)
        db.add(slot)
        await db.flush()
        if len(pools[role]) < 5:
            raise HTTPException(503, "Catalog has insufficient options")
        for _ in range(5):
            db.add(DraftOffer(slot_id=slot.id, player_id=pools[role].pop().id))
    principal.revision += 1
    await db.flush()
    return draft


async def select_player(db: AsyncSession, draft: Draft, slot_id: str, player_id: str) -> None:
    slot = await db.get(DraftSlot, slot_id)
    offer = await db.get(DraftOffer, (slot_id, player_id))
    player = await db.get(Player, player_id)
    if not slot or slot.draft_id != draft.id or not offer or not player or player.role != slot.role:
        raise HTTPException(422, "Choose a player from this slot's five options")
    duplicate = await db.scalar(
        select(Selection).where(
            Selection.draft_id == draft.id,
            Selection.player_id == player_id,
            Selection.slot_id != slot_id,
        )
    )
    if duplicate:
        raise HTTPException(422, "A player can only be selected once")
    choice = await db.get(Selection, slot_id)
    if choice:
        choice.player_id = player_id
    else:
        db.add(Selection(slot_id=slot_id, draft_id=draft.id, player_id=player_id))
    draft.batting_order = []


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
    for choice, slot, player in rows:
        if slot.role != player.role or not await db.get(DraftOffer, (slot.id, choice.player_id)):
            raise HTTPException(422, "Selected player does not belong to the slot's offers")


async def confirm_team(db: AsyncSession, draft: Draft) -> None:
    await validate_order(db, draft, draft.batting_order)
    team = Team(draft_id=draft.id)
    db.add(team)
    await db.flush()
    for position, player_id in enumerate(draft.batting_order):
        db.add(TeamMember(team_id=team.id, player_id=player_id, position=position))
    draft.status = "CONFIRMED"


async def engine_team(db: AsyncSession, ids: list[str]) -> list[EnginePlayer]:
    rows = (
        await db.execute(
            select(Player, SimulationProfile)
            .join(SimulationProfile, SimulationProfile.player_id == Player.id)
            .where(Player.id.in_(ids))
        )
    ).all()
    profiles = {
        p.id: EnginePlayer(p.id, profile.batting, profile.bowling, p.role) for p, profile in rows
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
    catalog = list(
        (await db.scalars(select(Player).where(Player.catalog_id == draft.catalog_id))).all()
    )
    opponent: list[str] = []
    # A stratified draw takes players nearest the catalog median, with random tie breaks.
    rng = secrets.SystemRandom()
    for role, count in COMPOSITION.items():
        pool = [p for p in catalog if p.role == role]
        median = sorted(p.overall_rating for p in pool)[len(pool) // 2]
        rng.shuffle(pool)
        pool.sort(key=lambda p: abs(p.overall_rating - median))
        opponent.extend(p.id for p in rng.sample(pool[: max(count * 2, 5)], count))
    ids = await team_ids(db, team.id)
    state = initial_state(await engine_team(db, ids), await engine_team(db, opponent))
    match = Match(
        team_id=team.id,
        session_id=None if principal.user_id else principal.id,
        user_id=principal.user_id,
        opponent=opponent,
        seed=secrets.token_hex(32),
        state=asdict(state),
    )
    db.add(match)
    draft.revision += 1
    await db.flush()
    await persist_scorecard(db, match, state)
    return match


async def persist_scorecard(db: AsyncSession, match: Match, state: GameState) -> None:
    groups: list[
        tuple[type[BattingPerformance] | type[BowlingPerformance], list[dict[str, Any]]]
    ] = [
        (BattingPerformance, [asdict(entry) for entry in state.batting]),
        (BowlingPerformance, [asdict(entry) for entry in state.bowling]),
    ]
    for entity, entries in groups:
        for values in entries:
            row = await db.get(entity, (match.id, values["player_id"]))
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                db.add(entity(match_id=match.id, **values))


async def advance_match(db: AsyncSession, match: Match, intent: str, risk: str) -> None:
    if match.state["status"] != "LIVE":
        raise HTTPException(409, "This match has finished")
    state = GameState.from_dict(match.state)
    rules = RULESETS[match.ruleset]
    seed = hmac.new(
        bytes.fromhex(match.seed),
        f"{match.id}:{match.revision}:{match.ruleset}".encode(),
        hashlib.sha256,
    ).digest()
    transition = simulate_step(
        state,
        await engine_team(db, await team_ids(db, match.team_id)),
        await engine_team(db, match.opponent),
        Strategy(intent, risk),  # type: ignore[arg-type]
        decision_window(state.balls),
        rules,
        random.Random(seed),
    )
    match.revision += 1
    db.add(Decision(match_id=match.id, revision=match.revision, intent=intent, risk_focus=risk))
    for sequence, event in enumerate(transition.events):
        db.add(
            MatchEvent(match_id=match.id, revision=match.revision, sequence=sequence, payload=event)
        )
    match.state = asdict(transition.state)
    if transition.state.status != "LIVE":
        match.completed_at = now()
    await persist_scorecard(db, match, transition.state)
    await db.flush()


async def events_view(db: AsyncSession, match_id: str, after_revision: int = 0) -> list[dict]:
    events = (
        await db.scalars(
            select(MatchEvent)
            .where(MatchEvent.match_id == match_id, MatchEvent.revision > after_revision)
            .order_by(MatchEvent.revision, MatchEvent.sequence)
        )
    ).all()
    return [{"revision": e.revision, "sequence": e.sequence, **e.payload} for e in events]


async def match_view(db: AsyncSession, match: Match) -> dict:
    ids = await team_ids(db, match.team_id)
    players = {
        p.id: p
        for p in (
            await db.scalars(select(Player).where(Player.id.in_([*ids, *match.opponent])))
        ).all()
    }
    return {
        "id": match.id,
        "revision": match.revision,
        "rulesetVersion": match.ruleset,
        "target": RULESETS[match.ruleset].target,
        "decisionWindow": decision_window(match.state["balls"])
        if match.state["status"] == "LIVE"
        else 0,
        "state": match.state,
        "team": [summary(players[i]) for i in ids],
        "opponent": [summary(players[i]) for i in match.opponent],
        "events": await events_view(db, match.id),
        "createdAt": match.created_at.replace(tzinfo=UTC).isoformat(),
    }
