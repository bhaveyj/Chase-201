import hashlib
import hmac
import random
from dataclasses import asdict

import pytest
from test_api import match, mutate

from chase201.models import Decision, Match
from chase201.services import legacy_team, team_ids
from chase_engine import legacy


@pytest.mark.parametrize("desired", ["WICKET", "NO_BALL"])
@pytest.mark.parametrize("version", ["v2.0", "v2.1"])
async def test_v2_event_interruptions_persist_and_replay(client, database, desired, version):
    from chase201.services import engine_team
    from chase_engine.v2.engine import RULESETS, GameState, StrategyId, simulate_step

    m = await match(client)
    async with database() as db, db.begin():
        saved = await db.get(Match, m["id"])
        saved.ruleset = version
        saved.state = {k: v for k, v in saved.state.items() if k not in {"approaches_used", "recent_approaches"}}
        team = await engine_team(db, await team_ids(db, saved.team_id))
        opponent = await engine_team(db, saved.opponent)
        state = GameState.from_dict(saved.state)
        for candidate in range(2000):
            saved.seed = f"{candidate:064x}"
            seed = hmac.new(
                bytes.fromhex(saved.seed), f"{saved.id}:0:{saved.ruleset}".encode(), hashlib.sha256
            ).digest()
            expected = simulate_step(
                state, team, opponent, StrategyId.ATTACK, 12, RULESETS[version], random.Random(seed)
            )
            if expected.events[0]["interruption"] == desired:
                break
        else:
            pytest.fail("Could not find the deterministic interruption fixture")
    path = f"/api/v1/matches/{m['id']}/decisions"
    body = {"expectedRevision": 0, "strategy": "ATTACK"}
    response = await mutate(client, "POST", path, body, f"interruption-{desired}")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == asdict(expected.state)
    assert {key: result["events"][0][key] for key in expected.events[0]} == expected.events[0]
    assert result["events"][0]["deliveries"][-1]["outcome"] == desired
    assert result["context"] == expected.events[0]["contextAfter"]
    if desired == "NO_BALL":
        assert result["decisionWindow"] == 1
        assert all(a["wicketRisk"] == "None (free hit)" for a in result["strategyAssessments"])
    assert (await mutate(client, "POST", path, body, f"interruption-{desired}")).json() == result
    assert (await client.get(f"/api/v1/matches/{m['id']}")).json() == result


async def test_saved_v1_match_uses_exact_old_engine(client, database):
    m = await match(client)
    async with database() as db, db.begin():
        saved = await db.get(Match, m["id"])
        team = await legacy_team(db, await team_ids(db, saved.team_id))
        opponent = await legacy_team(db, saved.opponent)
        saved.ruleset = "v1.0"
        saved.state = asdict(legacy.initial_state(team, opponent))
        state = legacy.GameState.from_dict(saved.state)
        seed = hmac.new(
            bytes.fromhex(saved.seed), f"{saved.id}:0:v1.0".encode(), hashlib.sha256
        ).digest()
        expected = legacy.simulate_step(
            state, team, opponent, legacy.Strategy(), 18, legacy.Ruleset(), random.Random(seed)
        )
    path = f"/api/v1/matches/{m['id']}/decisions"
    before = (await client.get(f"/api/v1/matches/{m['id']}")).json()
    assert before["decisionWindow"] == 18 and before["context"] is None
    assert (
        await mutate(client, "POST", path, {"expectedRevision": 0, "strategy": "ATTACK"})
    ).status_code == 422
    body = {"expectedRevision": 0, "intent": "ROTATE", "riskFocus": "BALANCED"}
    response = await mutate(client, "POST", path, body, "saved-match-replay")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["rulesetVersion"] == "v1.0"
    assert {key: result["state"][key] for key in asdict(expected.state)} == asdict(expected.state)
    assert {key: result["events"][0][key] for key in expected.events[0]} == expected.events[0]
    assert (await mutate(client, "POST", path, body, "saved-match-replay")).json() == result
    async with database() as db:
        decision = await db.get(Decision, (m["id"], 1))
        assert decision.intent == "ROTATE" and decision.strategy is None


async def test_rejects_wrong_or_mixed_strategy_contract(client):
    m = await match(client)
    path = f"/api/v1/matches/{m['id']}/decisions"
    for payload in (
        {"strategy": "CHEAT"},
        {"intent": "ATTACK", "riskFocus": "BALANCED"},
        {"strategy": "ATTACK", "intent": "ATTACK", "riskFocus": "BALANCED"},
        {},
        {"strategy": "ATTACK", "pressure": "Low"},
    ):
        response = await mutate(client, "POST", path, {"expectedRevision": 0, **payload})
        assert response.status_code == 422
    assert (await client.get(f"/api/v1/matches/{m['id']}")).json()["revision"] == 0
