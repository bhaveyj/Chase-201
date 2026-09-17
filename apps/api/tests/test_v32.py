from dataclasses import asdict

import pytest
from test_api import match, mutate

from chase201.models import Match
from chase201.services import engine_team, team_ids
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v32 import engine
from chase_engine.v32.transitions import apply_delivery


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize("switch", [False, True])
async def test_variation_is_persisted_and_enforced_by_api(
    client, database, monkeypatch, strategy, switch
):
    view = await match(client)
    assert view["rulesetVersion"] == "v3.4"
    async with database() as db, db.begin():
        saved = await db.get(Match, view["id"])
        saved.ruleset = "v3.2"
        state = engine.initial_state(
            await engine_team(db, await team_ids(db, saved.team_id), "v3.2"),
            await engine_team(db, saved.opponent, "v3.2"),
        )
        for _ in range(33):
            apply_delivery(state, Outcome.SIX, strategy=strategy)
        apply_delivery(state, Outcome.TWO, strategy=strategy)
        while state.balls < 119:
            apply_delivery(state, Outcome.DOT, strategy=strategy)
        saved.state = asdict(state)
    path = f"/api/v1/matches/{view['id']}"
    reloaded = (await client.get(path)).json()
    assert reloaded["state"]["approaches_used"] == [strategy.value]
    monkeypatch.setattr("chase_engine.v32.simulation.sample", lambda *args: Outcome.SIX)
    selected = next(s for s in StrategyId if s != strategy) if switch else strategy
    body = {"expectedRevision": 0, "strategy": selected.value}
    result = await mutate(client, "POST", f"{path}/decisions", body, "last-ball")
    assert result.status_code == 200, result.text
    final = result.json()
    assert final["state"]["status"] == ("WON" if switch else "TIED")
    assert final["state"]["runs"] == (206 if switch else 200)
    assert final["state"]["approaches_used"] == (
        [strategy.value, selected.value] if switch else [strategy.value]
    )
    replay = await mutate(client, "POST", f"{path}/decisions", body, "last-ball")
    assert replay.json() == final
    assert (await client.get(path)).json()["state"] == final["state"]
