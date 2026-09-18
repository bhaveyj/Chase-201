from dataclasses import asdict

import pytest
from sqlalchemy import select
from test_api import match, mutate

from chase201.models import Match, SimulationProfile
from chase201.services import engine_team, team_ids
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v34 import engine
from chase_engine.v34.transitions import apply_delivery


async def test_batting_rating_is_absent_and_cannot_influence_live_game(client, database):
    view = await match(client)
    assert view["rulesetVersion"] == "v3.5"
    assert all("battingRating" not in p for p in view["team"] + view["opponent"])
    async with database() as db, db.begin():
        rows = (await db.scalars(select(SimulationProfile))).all()
        for i, profile in enumerate(rows):
            profile.batting = 1 if i % 2 else 100
            profile.batting_control = profile.batting_rotation = profile.batting_power = 1
        assert all(
            p.batting == 75 for p in await engine_team(db, [p["id"] for p in view["team"]], "v3.4")
        )
    assert (await client.get(f"/api/v1/matches/{view['id']}")).json() == view


@pytest.mark.parametrize("switch", [False, True])
async def test_last_ball_guard_assessments_reload_and_idempotency(
    client, database, monkeypatch, switch
):
    view = await match(client)
    async with database() as db, db.begin():
        saved = await db.get(Match, view["id"])
        saved.ruleset = "v3.4"
        state = engine.initial_state(
            await engine_team(db, await team_ids(db, saved.team_id), "v3.4"),
            await engine_team(db, saved.opponent, "v3.4"),
        )
        for _ in range(33):
            apply_delivery(state, Outcome.SIX, strategy=StrategyId.BALANCED)
        apply_delivery(state, Outcome.TWO, strategy=StrategyId.BALANCED)
        while state.balls < 119:
            apply_delivery(state, Outcome.DOT, strategy=StrategyId.BALANCED)
        saved.state = asdict(state)
    path = f"/api/v1/matches/{view['id']}"
    reloaded = (await client.get(path)).json()
    assert reloaded["state"]["approaches_used"] == ["BALANCED"]
    assert "recent_approaches" not in reloaded["state"]
    assert (
        next(a for a in reloaded["strategyAssessments"] if a["strategy"] == "BALANCED")["scoring"]
        == "Very low"
    )
    monkeypatch.setattr("chase_engine.v34.simulation.sample", lambda *args: Outcome.SIX)
    body = {"expectedRevision": 0, "strategy": "AGGRESSIVE" if switch else "BALANCED"}
    result = await mutate(client, "POST", f"{path}/decisions", body, "last-ball")
    assert result.status_code == 200, result.text
    final = result.json()
    assert final["state"]["status"] == ("WON" if switch else "TIED")
    assert final["state"]["runs"] == (206 if switch else 200)
    assert (await mutate(client, "POST", f"{path}/decisions", body, "last-ball")).json() == final
    assert (await client.get(path)).json() == final
