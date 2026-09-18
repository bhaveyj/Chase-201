from dataclasses import asdict

import pytest
from test_api import match, mutate

from chase201.models import Match
from chase201.services import engine_team, team_ids
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v33 import engine
from chase_engine.v33.transitions import apply_delivery


@pytest.mark.parametrize(
    "strategy,maximum",
    [(StrategyId.DEFENSIVE, 150), (StrategyId.BALANCED, 180), (StrategyId.AGGRESSIVE, 185)],
)
async def test_final_ten_balls_keep_scoring_and_remain_bounded_after_reload(
    client, database, monkeypatch, strategy, maximum
):
    view = await match(client)
    assert view["rulesetVersion"] == "v3.5"
    async with database() as db, db.begin():
        saved = await db.get(Match, view["id"])
        saved.ruleset = "v3.3"
        state = engine.initial_state(
            await engine_team(db, await team_ids(db, saved.team_id), "v3.3"),
            await engine_team(db, saved.opponent, "v3.3"),
        )
        for _ in range(110):
            apply_delivery(state, Outcome.SIX, strategy=strategy)
        saved.state = asdict(state)
    path = f"/api/v1/matches/{view['id']}"
    monkeypatch.setattr("chase_engine.v33.simulation.sample", lambda *args: Outcome.SIX)
    runs = []
    for ball in range(110, 120):
        before = (await client.get(path)).json()
        body = {"expectedRevision": before["revision"], "strategy": strategy.value}
        key = f"ball-{ball}"
        result = await mutate(client, "POST", f"{path}/decisions", body, key)
        assert result.status_code == 200, result.text
        view = result.json()
        runs.append(view["state"]["runs"] - before["state"]["runs"])
        assert (await mutate(client, "POST", f"{path}/decisions", body, key)).json() == view
        async with database() as db:
            saved = await db.get(Match, view["id"])
            assert saved.state["recent_approaches"] == [strategy.value] * 24
    assert view["state"]["runs"] == maximum
    assert view["state"]["status"] == "LOST"
    assert sum(runs) >= 7
    if strategy == StrategyId.BALANCED:
        assert all(value > 0 for value in runs)
