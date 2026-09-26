import random
from dataclasses import replace

import pytest
from sqlalchemy import func, select
from test_api import draft, match, mutate

from chase201.catalog import CatalogImport, import_catalog, tradeoff_fictional_players
from chase201.models import CatalogVersion, Match
from chase201.tradeoffs import (
    DraftProfile,
    allocate,
    playstyle,
    shuffled_allocation,
    validate_allocation,
)
from chase_engine.engine import DEFAULT_RULES, StrategyId, distribution, initial_state
from chase_engine.types import PlayerProfile


@pytest.fixture(autouse=True)
def historical_catalog(monkeypatch):
    from chase201.config import get_settings

    monkeypatch.setattr(get_settings(), "catalog_version", "fictional-v3")


def catalog():
    return [
        DraftProfile(
            p.id, p.role, p.overallRating, (p.batting_control, p.batting_rotation, p.batting_power)
        )
        for p in tradeoff_fictional_players()
    ]


def test_complete_offer_tradeoffs_across_500_seeds():
    players = catalog()
    allocation = allocate(players)
    for seed in range(500):
        offers = shuffled_allocation(allocation, random.Random(seed))
        validate_allocation(players, offers)
    for p in players:
        assert all(1 <= a <= 100 for a in p.attributes)
        assert max(p.attributes) - min(p.attributes) >= 12
    for role in {p.role for p in players}:
        for star in (True, False):
            tier = [p for p in players if p.role == role and (p.overall_rating >= 90) == star]
            assert len({sum(p.attributes) for p in tier}) <= 1
    tail = [p for p in players if p.role == "BOWLER"]
    assert max(sum(p.attributes) for p in tail) < min(
        sum(p.attributes) for p in players if p.role != "BOWLER"
    )


def test_no_silent_relaxation_with_dominated_duplicate_or_missing_style():
    players = catalog()
    for attributes in ((70, 70, 70), (90, 70, 50)):
        broken = [
            replace(p, attributes=attributes) if p.role == "WICKETKEEPER" else p for p in players
        ]
        with pytest.raises(ValueError, match="No complete"):
            allocate(broken)
    allocation = allocate(players)
    allocation[1] = allocation[0]
    with pytest.raises(ValueError, match="disjoint"):
        validate_allocation(players, allocation)


def test_lower_rated_specialists_beat_higher_ovr_in_suitable_matchups():
    players = catalog()
    for role in {p.role for p in players}:
        pool = [p for p in players if p.role == role and p.overall_rating <= 85]

        def profile(p):
            return PlayerProfile(p.id, p.role, p.overall_rating, *p.attributes)

        team = [PlayerProfile(str(i), "BOWLER" if i > 5 else "BATTER") for i in range(11)]
        state = initial_state(team, team)
        for style, mode, metric, lower in (
            ("Anchor", StrategyId.DEFENSIVE, "wicket_probability", True),
            ("Hitter", StrategyId.AGGRESSIVE, "boundary_probability", False),
        ):
            assert any(
                (
                    getattr(distribution(state, profile(p), team[1], team[-1], mode), metric)
                    < getattr(distribution(state, profile(q), team[1], team[-1], mode), metric)
                )
                == lower
                for p in pool
                for q in pool
                if p.overall_rating < q.overall_rating
                and playstyle(p.attributes) == style
                and playstyle(q.attributes) != style
            ), (role, style)
    batter = team[0]
    assert distribution(state, batter, team[1], team[-1], StrategyId.BALANCED) == distribution(
        state,
        replace(batter, overall=100, bowling_control=100, bowling_threat=100),
        team[1],
        team[-1],
        StrategyId.BALANCED,
    )


async def test_import_is_validated_before_activation_and_is_immutable(database):
    async with database() as db, db.begin():
        original = await db.scalar(select(func.count()).select_from(CatalogVersion))
        broken = [
            p.model_copy(
                update={"batting_control": 75, "batting_rotation": 75, "batting_power": 75}
            )
            for p in tradeoff_fictional_players()
        ]
        with pytest.raises(ValueError):
            await import_catalog(
                db, CatalogImport(version="invalid", source="test", license="test", players=broken)
            )
        assert await db.get(CatalogVersion, "invalid") is None
        assert await db.scalar(select(func.count()).select_from(CatalogVersion)) == original
        with pytest.raises(ValueError, match="immutable"):
            await import_catalog(
                db,
                CatalogImport(
                    version="fictional-v3",
                    source="test",
                    license="test",
                    players=tradeoff_fictional_players(),
                ),
            )


async def test_active_contract_rejects_all_old_modes_and_keeps_three_after_reload(client):
    m = await match(client)
    path = f"/api/v1/matches/{m['id']}/decisions"
    for old in ("PRESERVE", "ROTATE", "ATTACK", "ALL_OUT"):
        response = await mutate(client, "POST", path, {"expectedRevision": 0, "strategy": old})
        assert response.status_code == 422
    for mode in StrategyId:
        response = await mutate(
            client, "POST", path, {"expectedRevision": m["revision"], "strategy": mode.value}
        )
        assert response.status_code == 200, response.text
        m = response.json()
        assert m["rulesetVersion"] == DEFAULT_RULES.version
        assert [a["strategy"] for a in m["strategyAssessments"]] == list(StrategyId)
        assert m["events"][-1]["strategy"] == mode.value
        full = (await client.get(f"/api/v1/matches/{m['id']}")).json()
        assert {key: value for key, value in full.items() if key != "events"} == {
            key: value for key, value in m.items() if key != "events"
        }
        assert full["events"][-1] == m["events"][-1]


async def test_draft_profiles_match_the_immutable_simulation_values(client):
    d = await draft(client)
    players = {f"fictional-v3:{p.id}": p for p in catalog()}
    for slot in d["slots"]:
        for p in slot["options"]:
            attributes = players[p["id"]].attributes
            assert [p["battingControl"], p["battingRotation"], p["battingPower"]] == list(
                attributes
            )
            assert p["battingPlaystyle"] == playstyle(attributes)


async def test_invalid_active_allocation_cannot_create_a_partial_draft(client, database):
    from test_api import guest

    from chase201.models import Draft, SimulationProfile

    session = await guest(client)
    async with database() as db, db.begin():
        version = await db.get(CatalogVersion, "fictional-v3")
        profile = await db.get(SimulationProfile, version.offer_allocation[0][0])
        profile.batting_control = profile.batting_rotation = profile.batting_power = 100
    response = await mutate(
        client, "POST", "/api/v1/drafts", {"expectedRevision": session["revision"]}
    )
    assert response.status_code == 503
    async with database() as db:
        assert await db.scalar(select(func.count()).select_from(Draft)) == 0
    assert (await client.get("/api/v1/session")).json()["revision"] == session["revision"]


@pytest.mark.parametrize("free", [True, False])
async def test_v3_interruptions_expose_only_three_modes(client, database, free):
    from dataclasses import asdict

    from chase201.services import engine_team, team_ids
    from chase_engine.transitions import apply_delivery
    from chase_engine.types import Outcome

    m = await match(client)
    async with database() as db, db.begin():
        saved = await db.get(Match, m["id"])
        state = initial_state(
            await engine_team(db, await team_ids(db, saved.team_id)),
            await engine_team(db, saved.opponent),
        )
        apply_delivery(state, Outcome.NO_BALL if free else Outcome.WICKET)
        saved.state = asdict(state)
    resumed = (await client.get(f"/api/v1/matches/{m['id']}")).json()
    assert [a["strategy"] for a in resumed["strategyAssessments"]] == list(StrategyId)
    if free:
        assert resumed["decisionWindow"] == 1
        assert all(a["wicketRisk"] == "None (free hit)" for a in resumed["strategyAssessments"])
