import copy
import random
from dataclasses import asdict, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_engine_v31 import OPPONENT, TEAM, assert_invariants

from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v32 import engine
from chase_engine.v32.transitions import apply_delivery, current_bowler


def near_target(strategy, runs=200):
    state = engine.initial_state(TEAM, OPPONENT)
    for _ in range(runs // 6):
        apply_delivery(state, Outcome.SIX, strategy=strategy)
    for _ in range(runs % 6):
        apply_delivery(state, Outcome.ONE, strategy=strategy)
    return state


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize("runs", range(195, 201))
@pytest.mark.parametrize("outcome", list(Outcome))
def test_no_scoring_path_can_win_with_one_approach(strategy, runs, outcome):
    state = near_target(strategy, runs)
    delivery = apply_delivery(state, outcome, strategy=strategy)
    assert state.status != "WON"
    assert state.runs < 201
    assert_invariants(state)
    assert delivery["runs"] == state.runs - runs


@pytest.mark.parametrize("strategy", list(StrategyId))
def test_even_unbroken_sixes_and_the_strongest_batters_cannot_win(monkeypatch, strategy):
    monkeypatch.setattr("chase_engine.v32.simulation.sample", lambda *args: Outcome.SIX)
    strongest = [replace(p, batting=100) for p in TEAM]
    state = engine.initial_state(strongest, OPPONENT)
    while state.status == "LIVE":
        state = engine.simulate_step(
            state,
            strongest,
            OPPONENT,
            strategy,
            engine.window_for(state).max_legal_balls,
            engine.DEFAULT_RULES,
            random.Random(0),
        ).state
        assert_invariants(state)
    assert state.status == "LOST"
    assert state.runs == 198
    assert state.balls == 120


@given(seed=st.integers(0, 1_000_000), strategy=st.sampled_from(list(StrategyId)))
@settings(max_examples=75, deadline=None)
def test_fixed_approach_never_wins_and_survives_reload(seed, strategy):
    state = engine.initial_state(TEAM, OPPONENT)
    rng = random.Random(seed)
    while state.status == "LIVE":
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
        state = engine.GameState.from_dict(asdict(transition.state))
        assert_invariants(state)
    assert state.status in {"LOST", "TIED"}
    assert state.approaches_used == [strategy.value]


@pytest.mark.parametrize("strategy", list(StrategyId))
def test_second_approach_must_face_a_legal_delivery(strategy):
    state = near_target(strategy, 190)
    other = next(s for s in StrategyId if s != strategy)
    apply_delivery(state, Outcome.WIDE, strategy=other)
    apply_delivery(state, Outcome.NO_BALL, strategy=other)
    assert state.approaches_used == [strategy.value]
    apply_delivery(state, Outcome.DOT, strategy=other)
    assert state.approaches_used == [strategy.value, other.value]
    apply_delivery(state, Outcome.SIX, strategy=strategy)
    apply_delivery(state, Outcome.SIX, strategy=strategy)
    assert state.status == "WON"
    assert_invariants(state)


@pytest.mark.parametrize("strategy", list(StrategyId))
@pytest.mark.parametrize("free_hit", [False, True])
def test_assessments_match_enforced_outcomes_and_switching_can_win(strategy, free_hit):
    state = near_target(strategy)
    state.free_hit = free_hit
    profiles = (
        TEAM[state.striker],
        TEAM[state.non_striker],
        next(p for p in OPPONENT if p.id == current_bowler(state).player_id),
    )
    risk = engine.distribution(state, *profiles, strategy)
    assert risk.expected_runs == 0
    assert risk.boundary_probability == 0
    assert risk.legality == (1, 0, 0)
    assert sum(risk.legal) == pytest.approx(1)
    if free_hit:
        assert risk.wicket_probability == 0
    other = next(s for s in StrategyId if s != strategy)
    assert engine.distribution(state, *profiles, other).expected_runs > 0
    apply_delivery(state, Outcome.ONE, strategy=other)
    assert state.status == "WON"
    assert_invariants(state)
