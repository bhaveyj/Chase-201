import copy
import random
from dataclasses import asdict, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_engine_v31 import OPPONENT, TEAM, assert_invariants, profiles

from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v34 import engine
from chase_engine.v34.transitions import apply_delivery


def play(seed, strategy, team=TEAM, reload=False):
    state = engine.initial_state(team, OPPONENT)
    rng = random.Random(seed)
    events = []
    while state.status == "LIVE":
        before = copy.deepcopy(state)
        transition = engine.simulate_step(
            state,
            team,
            OPPONENT,
            strategy,
            engine.window_for(state).max_legal_balls,
            engine.DEFAULT_RULES,
            rng,
        )
        assert state == before
        state = transition.state
        if reload:
            state = engine.GameState.from_dict(asdict(state))
        assert_invariants(state)
        events.extend(transition.events)
    return state, events


@pytest.mark.parametrize("strategy", list(StrategyId))
def test_batting_ratings_cannot_change_context_assessments_or_replays(strategy):
    low = [replace(p, batting=1) for p in TEAM]
    high = [replace(p, batting=100) for p in TEAM]
    state = engine.initial_state(TEAM, OPPONENT)
    for _ in range(30):
        apply_delivery(state, Outcome.ONE, strategy=strategy)
    assert engine.derive_context(state, *profiles(state, team=low)) == engine.derive_context(
        state, *profiles(state, team=high)
    )
    assert engine.distribution(state, *profiles(state, team=low), strategy) == engine.distribution(
        state, *profiles(state, team=high), strategy
    )
    assert play(321, strategy, low) == play(321, strategy, high, reload=True)


@given(seed=st.integers(0, 1_000_000), strategy=st.sampled_from(list(StrategyId)))
@settings(max_examples=75, deadline=None)
def test_fixed_approaches_never_win_and_reload_preserves_outcomes(seed, strategy):
    state, events = play(seed, strategy, reload=True)
    assert state.status in {"LOST", "TIED"}
    assert state.runs < 201
    assert state.approaches_used == [strategy.value]
    assert len(state.recent_approaches) <= 24
    assert (state, events) == play(seed, strategy)


@pytest.mark.parametrize("strategy", [StrategyId.DEFENSIVE, StrategyId.BALANCED])
def test_spamming_has_varied_scoring_in_both_opening_and_final_three_overs(strategy):
    early, late, traces = set(), set(), set()
    for seed in range(30):
        _, events = play(seed, strategy)
        trace = []
        for event in events:
            for delivery in event["deliveries"]:
                trace.append(delivery["outcome"])
                if delivery["fromBall"] < 18:
                    early.add(delivery["outcome"])
                if delivery["fromBall"] >= 102:
                    late.add(delivery["outcome"])
        traces.add(tuple(trace))
    for outcomes in (early, late):
        assert {"DOT", "ONE", "TWO", "FOUR", "SIX", "WICKET"} <= outcomes
    assert len(traces) == 30


@pytest.mark.parametrize("strategy", [StrategyId.DEFENSIVE, StrategyId.BALANCED])
def test_late_boundaries_are_sampled_without_conversion_to_a_single(strategy):
    state = engine.initial_state(TEAM, OPPONENT)
    for i in range(110):
        apply_delivery(state, Outcome.TWO if i < 85 else Outcome.DOT, strategy=strategy)
    outcomes = engine.distribution(state, *profiles(state), strategy)
    assert outcomes.probability(Outcome.DOT) > 0
    assert outcomes.probability(Outcome.ONE) > 0
    assert outcomes.probability(Outcome.FOUR) > 0
    assert outcomes.probability(Outcome.SIX) > 0
    assert apply_delivery(state, Outcome.SIX, strategy=strategy)["runs"] == 6


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize("outcome", list(Outcome))
def test_single_approach_guard_covers_boundaries_extras_and_free_hits(strategy, outcome):
    state = engine.initial_state(TEAM, OPPONENT)
    for _ in range(33):
        apply_delivery(state, Outcome.SIX, strategy=strategy)
    apply_delivery(state, Outcome.TWO, strategy=strategy)
    distribution = engine.distribution(state, *profiles(state), strategy)
    assert distribution.expected_runs == 0
    assert distribution.boundary_probability == 0
    apply_delivery(state, outcome, strategy=strategy)
    assert state.status != "WON"
    assert state.runs == 200
    assert_invariants(state)


def test_legal_switch_can_win_but_extras_do_not_qualify_and_free_hits_remain_safe():
    state = engine.initial_state(TEAM, OPPONENT)
    apply_delivery(state, Outcome.NO_BALL, strategy=StrategyId.DEFENSIVE)
    assert state.approaches_used == []
    for strategy in StrategyId:
        outcomes = engine.distribution(state, *profiles(state), strategy)
        assert outcomes.wicket_probability == 0
        assert sum(outcomes.legal) == pytest.approx(1)
        assert sum(outcomes.legality) == pytest.approx(1)
    apply_delivery(state, Outcome.DOT, strategy=StrategyId.BALANCED)
    apply_delivery(state, Outcome.WIDE, strategy=StrategyId.DEFENSIVE)
    assert state.approaches_used == ["BALANCED"]
    apply_delivery(state, Outcome.DOT, strategy=StrategyId.DEFENSIVE)
    while state.status == "LIVE":
        apply_delivery(state, Outcome.SIX, strategy=StrategyId.BALANCED)
    assert state.status == "WON"
    assert_invariants(state)
