import copy
import random
from dataclasses import asdict, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_engine_v31 import OPPONENT, TEAM, assert_invariants

from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v33 import engine
from chase_engine.v33.transitions import apply_delivery, current_bowler


def probabilities(state, strategy):
    return engine.distribution(
        state,
        TEAM[state.striker],
        TEAM[state.non_striker],
        next(p for p in OPPONENT if p.id == current_bowler(state).player_id),
        strategy,
    )


@pytest.mark.parametrize(
    "strategy,maximum",
    [(StrategyId.DEFENSIVE, 150), (StrategyId.BALANCED, 180), (StrategyId.AGGRESSIVE, 185)],
)
def test_forced_boundaries_never_exceed_limits_or_create_a_late_dot_wall(
    monkeypatch, strategy, maximum
):
    monkeypatch.setattr("chase_engine.v33.simulation.sample", lambda *args: Outcome.SIX)
    team = [replace(p, batting=100) for p in TEAM]
    state = engine.initial_state(team, OPPONENT)
    last_ten = []
    while state.status == "LIVE":
        before = copy.deepcopy(state)
        if state.balls >= 110:
            # Even at the highest possible score, scoring opportunities remain.
            if strategy == StrategyId.BALANCED:
                assert probabilities(state, strategy).expected_runs > 0
        step = engine.simulate_step(
            state,
            team,
            OPPONENT,
            strategy,
            engine.window_for(state).max_legal_balls,
            engine.DEFAULT_RULES,
            random.Random(0),
        )
        assert state == before
        state = engine.GameState.from_dict(asdict(step.state))
        assert_invariants(state)
        if state.status == "LIVE":
            assert state.runs < maximum
        last_ten.extend(d["runs"] for d in step.events[0]["deliveries"] if d["fromBall"] >= 110)
    assert state.status == "LOST"
    assert state.runs == maximum
    assert sum(last_ten) >= 7
    assert sum(runs > 0 for runs in last_ten) >= 7
    if strategy == StrategyId.BALANCED:
        assert all(runs > 0 for runs in last_ten)


@given(seed=st.integers(0, 1_000_000), strategy=st.sampled_from(list(StrategyId)))
@settings(max_examples=75, deadline=None)
def test_random_fixed_approaches_stay_bounded_through_reload(seed, strategy):
    state = engine.initial_state(TEAM, OPPONENT)
    rng = random.Random(seed)
    while state.status == "LIVE":
        state = engine.simulate_step(
            state,
            TEAM,
            OPPONENT,
            strategy,
            engine.window_for(state).max_legal_balls,
            engine.DEFAULT_RULES,
            rng,
        ).state
        state = engine.GameState.from_dict(asdict(state))
        assert_invariants(state)
        assert (
            state.runs
            <= engine.DEFAULT_RULES.single_approach_totals[list(StrategyId).index(strategy)]
        )
        assert len(state.recent_approaches) <= 24
    assert state.status == "LOST"


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize("outcome", [Outcome.WIDE, Outcome.NO_BALL, Outcome.SIX, Outcome.FOUR])
def test_extreme_extras_and_boundaries_cannot_bypass_pacing(strategy, outcome):
    state = engine.initial_state(TEAM, OPPONENT)
    for _ in range(1000):
        if state.status != "LIVE":
            break
        apply_delivery(state, outcome, strategy=strategy)
        assert_invariants(state)
    assert state.status == "LOST"
    assert (
        state.runs <= engine.DEFAULT_RULES.single_approach_totals[list(StrategyId).index(strategy)]
    )


def test_a_token_switch_does_not_reset_bowler_adaptation():
    state = engine.initial_state(TEAM, OPPONENT)
    for _ in range(36):
        apply_delivery(state, Outcome.DOT, strategy=StrategyId.BALANCED)
    apply_delivery(state, Outcome.DOT, strategy=StrategyId.DEFENSIVE)
    state = engine.GameState.from_dict(asdict(state))
    assert state.recent_approaches.count("BALANCED") == 23
    fresh = copy.deepcopy(state)
    fresh.recent_approaches = []
    assert (
        probabilities(state, StrategyId.BALANCED).expected_runs
        < probabilities(fresh, StrategyId.BALANCED).expected_runs
    )


def test_extras_do_not_count_as_switches_and_free_hits_stay_safe():
    state = engine.initial_state(TEAM, OPPONENT)
    apply_delivery(state, Outcome.DOT, strategy=StrategyId.BALANCED)
    apply_delivery(state, Outcome.NO_BALL, strategy=StrategyId.AGGRESSIVE)
    assert state.approaches_used == ["BALANCED"]
    assert state.recent_approaches == ["BALANCED"]
    for strategy in StrategyId:
        outcomes = probabilities(state, strategy)
        assert outcomes.wicket_probability == 0
        assert sum(outcomes.legal) == pytest.approx(1)
        assert sum(outcomes.legality) == pytest.approx(1)
    apply_delivery(state, Outcome.SIX, strategy=StrategyId.AGGRESSIVE)
    assert state.approaches_used == ["BALANCED", "AGGRESSIVE"]
    while state.status == "LIVE":
        apply_delivery(state, Outcome.SIX, strategy=StrategyId.BALANCED)
    assert state.status == "WON"
    assert_invariants(state)
