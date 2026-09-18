from dataclasses import asdict

import pytest
from test_api import match, mutate

from chase201.models import Match
from chase201.services import engine_team, team_ids
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v35 import engine
from chase_engine.v35.transitions import apply_delivery


@pytest.mark.parametrize("outcome", [Outcome.FOUR, Outcome.SIX, Outcome.WIDE, Outcome.NO_BALL])
async def test_aggressive_winning_outcomes_survive_api_reload_and_retry(
    client, database, monkeypatch, outcome
):
    view = await match(client)
    assert view["rulesetVersion"] == "v3.5"
    async with database() as db, db.begin():
        saved = await db.get(Match, view["id"])
        state = engine.initial_state(
            await engine_team(db, await team_ids(db, saved.team_id), "v3.5"),
            await engine_team(db, saved.opponent, "v3.5"),
        )
        for _ in range(33):
            apply_delivery(state, Outcome.SIX, strategy=StrategyId.AGGRESSIVE)
        apply_delivery(state, Outcome.TWO, strategy=StrategyId.AGGRESSIVE)
        while state.balls < 119:
            apply_delivery(state, Outcome.DOT, strategy=StrategyId.AGGRESSIVE)
        saved.state = asdict(state)
    path = f"/api/v1/matches/{view['id']}"
    reloaded = (await client.get(path)).json()
    assert reloaded["state"]["runs"] == 200
    assert reloaded["state"]["approaches_used"] == ["AGGRESSIVE"]
    assert (
        next(a for a in reloaded["strategyAssessments"] if a["strategy"] == "AGGRESSIVE")["scoring"]
        != "Very low"
    )
    monkeypatch.setattr("chase_engine.v35.simulation.sample", lambda *args: outcome)
    body = {"expectedRevision": 0, "strategy": "AGGRESSIVE"}
    response = await mutate(client, "POST", f"{path}/decisions", body, "winning-ball")
    assert response.status_code == 200, response.text
    final = response.json()
    assert final["state"]["status"] == "WON"
    assert final["events"][-1]["deliveries"][-1]["outcome"] == outcome.value
    assert final["state"]["runs"] == 200 + {Outcome.FOUR: 4, Outcome.SIX: 6}.get(outcome, 1)
    assert (await mutate(client, "POST", f"{path}/decisions", body, "winning-ball")).json() == final
    assert (await client.get(path)).json() == final
