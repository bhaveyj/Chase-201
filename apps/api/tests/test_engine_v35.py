import copy
import random
from dataclasses import asdict, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_engine_v31 import OPPONENT, TEAM, assert_invariants, profiles

from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v35 import engine
from chase_engine.v35.transitions import apply_delivery


def near_target(strategy, balls=108, score=197):
    state = engine.initial_state(TEAM, OPPONENT)
    for _ in range(score // 6):
        apply_delivery(state, Outcome.SIX, strategy=strategy)
    for _ in range(score % 6):
        apply_delivery(state, Outcome.ONE, strategy=strategy)
    while state.balls < balls:
        apply_delivery(state, Outcome.DOT, strategy=strategy)
    return state


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize(
    "outcome",
    [
        Outcome.ONE,
        Outcome.TWO,
        Outcome.THREE,
        Outcome.FOUR,
        Outcome.SIX,
        Outcome.WIDE,
        Outcome.NO_BALL,
    ],
)
def test_single_approach_keeps_winning_scoring_outcome_on_last_ball(strategy, outcome):
    state = near_target(strategy, balls=119, score=200)
    distribution = engine.distribution(state, *profiles(state), strategy)
    assert distribution.probability(outcome) > 0
    delivery = apply_delivery(state, outcome, strategy=strategy)
    assert delivery["outcome"] == outcome.value
    assert delivery["runs"] == {Outcome.FOUR: 4, Outcome.SIX: 6}.get(
        outcome, 3 if outcome == Outcome.THREE else 2 if outcome == Outcome.TWO else 1
    )
    assert state.status == "WON"
    assert state.approaches_used == [strategy.value]
    assert_invariants(state)


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize("free_hit", [False, True])
def test_reported_stall_at_197_retains_all_scoring_probabilities(strategy, free_hit):
    state = near_target(strategy)
    if free_hit:
        apply_delivery(state, Outcome.NO_BALL, strategy=strategy)
    probabilities = engine.distribution(state, *profiles(state), strategy)
    assert all(
        probabilities.probability(outcome) > 0 for outcome in Outcome if outcome != Outcome.WICKET
    )
    assert (probabilities.wicket_probability == 0) == free_hit
    for outcome in Outcome:
        if free_hit and outcome == Outcome.WICKET:
            continue
        branch = copy.deepcopy(state)
        delivery = apply_delivery(branch, outcome, strategy=strategy)
        assert delivery["outcome"] == outcome.value
        assert_invariants(branch)


def test_repeated_aggressive_adapts_early_and_token_switch_does_not_reset_it():
    state = engine.initial_state(TEAM, OPPONENT)
    before = engine.distribution(state, *profiles(state), StrategyId.AGGRESSIVE)
    for _ in range(18):
        apply_delivery(state, Outcome.ONE, strategy=StrategyId.AGGRESSIVE)
    repeated = engine.distribution(state, *profiles(state), StrategyId.AGGRESSIVE)
    no_history = replace(state, recent_approaches=[])
    unadapted = engine.distribution(no_history, *profiles(no_history), StrategyId.AGGRESSIVE)
    assert repeated.boundary_probability < unadapted.boundary_probability
    assert repeated.wicket_probability > unadapted.wicket_probability
    assert repeated != before
    apply_delivery(state, Outcome.DOT, strategy=StrategyId.BALANCED)
    assert state.recent_approaches.count("AGGRESSIVE") == 18
    assert engine.distribution(
        state, *profiles(state), StrategyId.AGGRESSIVE
    ) != engine.distribution(
        replace(state, recent_approaches=[]), *profiles(state), StrategyId.AGGRESSIVE
    )


@given(seed=st.integers(0, 1_000_000), strategy=st.sampled_from(list(StrategyId)))
@settings(max_examples=60, deadline=None)
def test_random_chases_replay_with_cricket_accounting_and_ordered_risks(seed, strategy):
    states = []
    for reload in (False, True):
        state = engine.initial_state(TEAM, OPPONENT)
        rng = random.Random(seed)
        events = []
        while state.status == "LIVE":
            risks = [
                engine.distribution(state, *profiles(state), s).wicket_probability
                for s in StrategyId
            ]
            if state.free_hit:
                assert risks == [0, 0, 0]
            else:
                assert 0 < risks[0] < risks[1] < risks[2] < 1
            before = copy.deepcopy(state)
            transition = engine.simulate_step(
                state,
                TEAM,
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
            assert len(state.recent_approaches) <= 24
            events.extend(transition.events)
        assert (state.status == "WON") == (state.runs >= 201)
        states.append((state, events))
    assert states[0] == states[1]


def test_batting_ratings_still_do_not_change_scoring_or_context():
    state = near_target(StrategyId.AGGRESSIVE)
    low = [replace(p, batting=1) for p in TEAM]
    high = [replace(p, batting=100) for p in TEAM]
    for strategy in StrategyId:
        assert engine.distribution(
            state, *profiles(state, team=low), strategy
        ) == engine.distribution(state, *profiles(state, team=high), strategy)
    assert engine.derive_context(state, *profiles(state, team=low)) == engine.derive_context(
        state, *profiles(state, team=high)
    )
