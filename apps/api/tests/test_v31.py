import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean

import pytest
from sqlalchemy import select
from test_api import draft, match

from chase201.catalog import (
    CatalogImport,
    import_catalog,
    simple_fictional_players,
    tradeoff_fictional_players,
)
from chase201.draft_rules import ROLES, SIMPLE_SELECTION, draft_offers, rating_band
from chase201.models import CatalogVersion, Match, Player, SimulationProfile
from chase201.services import engine_team, team_ids
from chase_engine import engine as frozen
from chase_engine.v31 import engine
from chase_engine.v31.transitions import apply_delivery, current_bowler
from chase_engine.v31.types import Outcome
from chase_engine.v32 import engine as v32_engine
from chase_engine.v33 import engine as v33_engine
from chase_engine.v34 import engine as current_engine


def test_v30_golden_replays_remain_exact():
    fixture = json.loads((Path(__file__).parent / "fixtures/v3-replays.json").read_text())
    team = [frozen.PlayerProfile(**p) for p in fixture["team"]]
    opponent = [frozen.PlayerProfile(**p) for p in fixture["opponent"]]
    for row in fixture["replays"]:
        state = frozen.initial_state(team, opponent)
        rng = random.Random(row["seed"])
        trace = []
        while state.status == "LIVE":
            step = frozen.simulate_step(
                state,
                team,
                opponent,
                frozen.StrategyId(row["strategy"]),
                frozen.window_for(state).max_legal_balls,
                frozen.RULESETS["v3.0"],
                rng,
            )
            trace.append(asdict(step))
            state = step.state
        assert asdict(state) == row["state"]
        assert (
            hashlib.sha256(
                json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == row["traceSha256"]
        )


def test_simple_catalog_strength_variation_and_unchanged_bowling():
    cohorts = defaultdict(list)
    expected = {
        ("BATTER", False): 80,
        ("BATTER", True): 86,
        ("WICKETKEEPER", False): 78,
        ("ALL_ROUNDER", False): 77,
        ("ALL_ROUNDER", True): 83,
        ("BOWLER", False): 44,
    }
    for old, new in zip(tradeoff_fictional_players(), simple_fictional_players(), strict=True):
        assert (
            old.id,
            old.name,
            old.role,
            old.overallRating,
            old.bowling,
            old.bowling_control,
            old.bowling_threat,
            old.bowling_style,
        ) == (
            new.id,
            new.name,
            new.role,
            new.overallRating,
            new.bowling,
            new.bowling_control,
            new.bowling_threat,
            new.bowling_style,
        )
        cohorts[new.role, new.overallRating >= 90].append(new.batting)
    for key, values in cohorts.items():
        assert mean(values) == expected[key]
        assert values == [expected[key] + (-3, -1, 0, 1, 3)[i % 5] for i in range(len(values))]


def test_simple_offers_unique_and_legal_over_500_seeds():
    players = [
        Player(id=p.id, role=p.role, overall_rating=p.overallRating)
        for p in simple_fictional_players()
    ]
    for seed in range(500):
        offers = draft_offers(players, random.Random(seed))
        assert len(offers) == 11
        assert len({p.id for group in offers for p in group}) == 55
        for position, group in enumerate(offers):
            band = rating_band(position, SIMPLE_SELECTION)
            assert len(group) == 5
            assert all(
                p.role == ROLES[position] and band.minimum <= p.overall_rating <= band.maximum
                for p in group
            )


async def test_simple_import_needs_rating_capacity_but_no_archetypes(database):
    async with database() as db, db.begin():
        players = [
            p.model_copy(
                update={"batting_control": None, "batting_rotation": None, "batting_power": None}
            )
            for p in simple_fictional_players()
        ]
        data = CatalogImport(
            version="simple-import",
            source="test",
            license="test",
            selectionRuleset=SIMPLE_SELECTION,
            players=players,
        )
        await import_catalog(db, data)
        assert (await db.get(CatalogVersion, "simple-import")).selection_ruleset == SIMPLE_SELECTION
        with pytest.raises(ValueError, match="immutable"):
            await import_catalog(db, data)
        invalid = data.model_copy(
            update={
                "version": "invalid-simple",
                "players": [p.model_copy(update={"overallRating": 85}) for p in players],
            }
        )
        with pytest.raises(ValueError, match="five disjoint"):
            await import_catalog(db, invalid)
        assert await db.get(CatalogVersion, "invalid-simple") is None


async def test_simple_cards_expose_only_ovr(client):
    view = await draft(client)
    assert view["catalogVersion"] == "fictional-v4"
    assert view["selectionRuleset"] == SIMPLE_SELECTION
    source = {f"fictional-v4:{p.id}": p for p in simple_fictional_players()}
    for slot in view["slots"]:
        for player in slot["options"]:
            assert set(player) == {"id", "name", "role", "overallRating"}
            assert player["overallRating"] == source[player["id"]].overallRating


@pytest.mark.parametrize("version", ["v3.0", "v3.1", "v3.2", "v3.3", "v3.4"])
@pytest.mark.parametrize("free_hit", [False, True])
async def test_three_mode_api_probabilities_are_exact_and_zero_on_free_hits(
    client, database, monkeypatch, version, free_hit
):
    from chase201.config import get_settings

    monkeypatch.setattr(
        get_settings(), "catalog_version", "fictional-v3" if version == "v3.0" else "fictional-v4"
    )
    view = await match(client)
    if version in {"v3.1", "v3.2", "v3.3"}:
        async with database() as db, db.begin():
            saved = await db.get(Match, view["id"])
            saved.ruleset = version
            saved.state = {
                k: v
                for k, v in saved.state.items()
                if (version == "v3.3" or k != "recent_approaches")
                and (version != "v3.1" or k != "approaches_used")
            }
        view = (await client.get(f"/api/v1/matches/{view['id']}")).json()
    assert view["rulesetVersion"] == version
    selected_engine = {
        "v3.0": frozen,
        "v3.1": engine,
        "v3.2": v32_engine,
        "v3.3": v33_engine,
        "v3.4": current_engine,
    }[version]
    async with database() as db, db.begin():
        saved = await db.get(Match, view["id"])
        state = selected_engine.GameState.from_dict(saved.state)
        if free_hit:
            apply_delivery(state, Outcome.NO_BALL)
            saved.state = asdict(state)
        team = await engine_team(db, await team_ids(db, saved.team_id), version)
        opponent = await engine_team(db, saved.opponent, version)
        bowler = next(p for p in opponent if p.id == current_bowler(state).player_id)
        expected = [
            selected_engine.distribution(
                state, team[state.striker], team[state.non_striker], bowler, s
            ).wicket_probability
            for s in selected_engine.StrategyId
        ]
    result = (await client.get(f"/api/v1/matches/{view['id']}")).json()
    actual = [a["wicketProbability"] for a in result["strategyAssessments"]]
    assert actual == expected
    assert all(0 <= p <= 1 for p in actual)
    if free_hit:
        assert actual == [0, 0, 0]
    else:
        assert actual[0] < actual[1] < actual[2]


async def test_v31_ignores_legacy_attributes_in_storage(client, database):
    view = await match(client)
    async with database() as db, db.begin():
        rows = (
            await db.scalars(
                select(SimulationProfile).where(
                    SimulationProfile.player_id.in_([p["id"] for p in view["team"]])
                )
            )
        ).all()
        for profile in rows:
            profile.batting_control = 1
            profile.batting_rotation = 100
            profile.batting_power = 1
    after = (await client.get(f"/api/v1/matches/{view['id']}")).json()
    assert after == view


async def test_saved_tradeoff_draft_starts_v30_after_catalog_switch(client, monkeypatch):
    from test_api import filled_draft, mutate

    from chase201.config import get_settings

    monkeypatch.setattr(get_settings(), "catalog_version", "fictional-v3")
    saved = await filled_draft(client)
    monkeypatch.setattr(get_settings(), "catalog_version", "fictional-v4")
    response = await mutate(
        client,
        "PUT",
        f"/api/v1/drafts/{saved['id']}/batting-order",
        {
            "expectedRevision": saved["revision"],
            "playerIds": [slot["selectedPlayerId"] for slot in saved["slots"]],
        },
    )
    assert response.status_code == 200
    saved = response.json()
    response = await mutate(
        client,
        "POST",
        f"/api/v1/drafts/{saved['id']}/confirm",
        {
            "expectedRevision": saved["revision"],
        },
    )
    assert response.status_code == 200
    saved = response.json()
    response = await mutate(
        client,
        "POST",
        "/api/v1/matches",
        {
            "expectedRevision": saved["revision"],
            "draftId": saved["id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["rulesetVersion"] == "v3.0"
    assert all("battingControl" in p for p in response.json()["team"])
    assert (await client.get(f"/api/v1/drafts/{saved['id']}")).json()["slots"] == saved["slots"]


async def test_old_v30_idempotency_receipt_needs_no_probability_backfill(
    client, database, monkeypatch
):
    import copy

    from test_api import mutate

    from chase201.config import get_settings
    from chase201.models import Idempotency

    monkeypatch.setattr(get_settings(), "catalog_version", "fictional-v3")
    view = await match(client)
    path = f"/api/v1/matches/{view['id']}/decisions"
    body = {"expectedRevision": 0, "strategy": "BALANCED"}
    original = await mutate(client, "POST", path, body, "v30-before-probability")
    assert original.status_code == 200
    async with database() as db, db.begin():
        receipt = await db.scalar(
            select(Idempotency).where(Idempotency.key == "v30-before-probability")
        )
        historical = copy.deepcopy(receipt.response)
        for assessment in historical["strategyAssessments"]:
            assessment.pop("wicketProbability")
        receipt.response = historical
    replay = await mutate(client, "POST", path, body, "v30-before-probability")
    assert replay.status_code == 200
    assert replay.json()["state"] == original.json()["state"]
    assert replay.json()["events"] == original.json()["events"]
    assert all(a["wicketProbability"] is None for a in replay.json()["strategyAssessments"])
    async with database() as db:
        receipt = await db.scalar(
            select(Idempotency).where(Idempotency.key == "v30-before-probability")
        )
        assert receipt.response == historical
