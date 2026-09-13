import copy
import hashlib
import json
import random
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chase_engine.context import derive_context, setness_label
from chase_engine.engine import (
    DEFAULT_RULES,
    StrategyId,
    distribution,
    initial_state,
    simulate_step,
    window_for,
)
from chase_engine.rules import RULESETS
from chase_engine.sampling import sample
from chase_engine.simulation import decision_window
from chase_engine.transitions import apply_delivery, current_bowler
from chase_engine.types import BowlingStyle, Outcome, PlayerProfile

ROLES = ["BATTER"] * 5 + ["WICKETKEEPER"] + ["ALL_ROUNDER"] * 2 + ["BOWLER"] * 3
TEAM = [
    PlayerProfile(str(i), role, 82, *([82 if role != "BOWLER" else 46] * 3), 80, 80)
    for i, role in enumerate(ROLES)
]
OPPONENT = [
    PlayerProfile(
        f"ai{i}", role, 80, 80, 80, 80, 80, 80, BowlingStyle.PACE if i % 2 else BowlingStyle.SPIN
    )
    for i, role in enumerate(ROLES)
]
RULES = DEFAULT_RULES


def profiles(state, team=TEAM, opponent=OPPONENT):
    return (
        team[state.striker],
        team[state.non_striker],
        next(p for p in opponent if p.id == current_bowler(state).player_id),
    )


def probabilities(state=None, strategy=StrategyId.BALANCED, batter=None, bowler=None, rules=RULES):
    state = state or initial_state(TEAM, OPPONENT)
    bat, partner, bowl = profiles(state)
    return distribution(state, batter or bat, partner, bowler or bowl, strategy, rules)


def assert_invariants(state):
    assert 0 <= state.runs <= RULES.target + 5
    assert 0 <= state.wickets <= 10 and 0 <= state.balls <= 120
    assert state.runs == sum(b.runs for b in state.batting) + state.wides + state.no_balls
    assert state.runs == sum(b.runs for b in state.bowling)
    assert (
        state.wickets == sum(b.out for b in state.batting) == sum(b.wickets for b in state.bowling)
    )
    assert state.balls == sum(b.balls for b in state.batting) == sum(b.balls for b in state.bowling)
    assert all(0 <= b.balls <= 24 for b in state.bowling)
    assert all(b.runs >= b.fours * 4 + b.sixes * 6 for b in state.batting)
    assert all(a != b for a, b in zip(state.over_bowlers, state.over_bowlers[1:], strict=False))
    assert state.striker != state.non_striker
    assert len(state.recent_outcomes) <= 6
    assert 0 <= state.partnership_runs <= state.runs
    assert 0 <= state.partnership_balls <= state.balls
    if state.status == "LIVE":
        assert not state.batting[state.striker].out and not state.batting[state.non_striker].out


def play(seed, strategy=StrategyId.BALANCED, rules=RULES):
    state = initial_state(TEAM, OPPONENT)
    rng = random.Random(seed)
    trace = []
    while state.status == "LIVE":
        before = copy.deepcopy(state)
        step = simulate_step(
            state, TEAM, OPPONENT, strategy, window_for(state, rules).max_legal_balls, rules, rng
        )
        assert state == before
        event = step.events[0]
        assert (
            sum(d["runs"] for d in event["deliveries"])
            == event["runs"]
            == step.state.runs - state.runs
        )
        assert sum(d["wickets"] for d in event["deliveries"]) == event["wickets"] <= 1
        assert event["strategy"] == strategy
        assert len(event["deliveries"]) == 1 if state.free_hit or state.balls >= 108 else True
        state = step.state
        assert_invariants(state)
        trace.append(asdict(step))
        assert len(trace) < 100
    return state, trace


@given(seed=st.integers(0, 100_000), strategy=st.sampled_from(list(StrategyId)))
@settings(max_examples=150, deadline=None)
def test_full_match_invariants(seed, strategy):
    play(seed, strategy)


def test_deterministic_replay():
    assert play(201) == play(201)
    assert play(201) != play(202)


@pytest.mark.parametrize(
    "balls,size",
    [
        (0, 12),
        (1, 11),
        (11, 1),
        (12, 12),
        (60, 12),
        (71, 1),
        (72, 6),
        (95, 1),
        (96, 3),
        (107, 1),
        (108, 1),
        (119, 1),
        (120, 0),
    ],
)
def test_schedule(balls, size):
    assert decision_window(balls) == size


def test_26_scheduled_decisions():
    balls, count = 0, 0
    while balls < 120:
        balls += decision_window(balls)
        count += 1
    assert count == 26


class Draws:
    def __init__(self, *values):
        self.values = iter(values)

    def random(self):
        return next(self.values)


def force(state, outcome, strategy=StrategyId.BALANCED):
    p = probabilities(state, strategy)
    if outcome == Outcome.WIDE:
        return Draws(p.legality[0] + p.legality[1] / 2)
    if outcome == Outcome.NO_BALL:
        return Draws(1 - p.legality[2] / 2)
    i = list(Outcome).index(outcome)
    return Draws(0, sum(p.legal[:i]) + p.legal[i] / 2)


def step_once(state, outcome):
    return simulate_step(
        state, TEAM, OPPONENT, StrategyId.BALANCED, 1, RULES, force(state, outcome)
    )


def test_three_rotates_strike_and_reconciles():
    state = initial_state(TEAM, OPPONENT)
    state = step_once(state, Outcome.THREE).state
    assert state.runs == 3 and state.batting[0].runs == 3 and state.striker == 1
    assert state.partnership_runs == 3 and state.partnership_balls == 1
    assert_invariants(state)
    for _ in range(4):
        apply_delivery(state, Outcome.DOT)
    striker = state.striker
    apply_delivery(state, Outcome.THREE)
    assert state.striker == striker  # odd runs plus end-of-over rotation
    assert_invariants(state)


@pytest.mark.parametrize(
    "outcome,reason", [(Outcome.WICKET, "WICKET"), (Outcome.NO_BALL, "NO_BALL")]
)
def test_window_interruptions(outcome, reason):
    state = initial_state(TEAM, OPPONENT)
    result = simulate_step(
        state, TEAM, OPPONENT, StrategyId.BALANCED, 12, RULES, force(state, outcome)
    )
    assert len(result.events[0]["deliveries"]) == 1
    assert result.events[0]["interruption"] == reason
    assert result.state.balls == (1 if outcome == Outcome.WICKET else 0)
    if outcome == Outcome.NO_BALL:
        assert window_for(result.state).max_legal_balls == 1
    assert_invariants(result.state)


def test_wide_keeps_free_hit_and_free_hit_is_one_delivery():
    state = initial_state(TEAM, OPPONENT)
    state = step_once(state, Outcome.NO_BALL).state
    state = step_once(state, Outcome.WIDE).state
    assert state.free_hit and state.balls == 0 and state.no_balls == state.wides == 1
    assert probabilities(state).wicket_probability == 0
    assert step_once(state, Outcome.SIX).events[0]["kind"] == "DELIVERY"
    state = step_once(state, Outcome.ONE).state
    assert not state.free_hit and state.balls == 1 and state.striker == 1
    assert_invariants(state)


def test_buffer_partnership_and_new_batter_setness():
    state = initial_state(TEAM, OPPONENT)
    for _ in range(34):
        apply_delivery(state, Outcome.TWO)
    context = derive_context(state, *profiles(state))
    assert context.striker_setness == 1
    assert context.partnership_stability > 0.5
    apply_delivery(state, Outcome.WIDE)
    assert state.partnership_runs == 69 and state.partnership_balls == 34
    apply_delivery(state, Outcome.WICKET)
    assert state.partnership_runs == state.partnership_balls == 0
    assert state.last_wicket_ball == 35
    assert state.batting[state.striker].balls == 0
    assert derive_context(state, *profiles(state)).striker_setness == 0
    assert state.recent_outcomes == ["TWO"] * 4 + ["WIDE", "WICKET"]
    assert (
        setness_label(0) == "New" and setness_label(6) == "Settling" and setness_label(15) == "Set"
    )
    assert_invariants(state)


def finish_state(runs=200, balls=119):
    state = initial_state(TEAM, OPPONENT)
    for i in range(balls):
        # legal, internally reconciled prefix with exact requested score
        value = runs // balls + (i < runs % balls)
        apply_delivery(state, (Outcome.DOT, Outcome.ONE, Outcome.TWO, Outcome.THREE)[value])
    return state


def test_tie_target_tenth_wicket_and_completion():
    state = finish_state()
    assert step_once(state, Outcome.DOT).state.status == "TIED"
    won = step_once(state, Outcome.ONE).state
    assert won.status == "WON" and won.runs == 201
    assert step_once(state, Outcome.WIDE).state.balls == 119
    assert step_once(state, Outcome.SIX).state.runs == 206
    with pytest.raises(ValueError):
        step_once(won, Outcome.DOT)
    state = initial_state(TEAM, OPPONENT)
    for _ in range(10):
        apply_delivery(state, Outcome.WICKET)
    assert state.status == "LOST" and state.balls == 10 and state.next_batter == 11
    assert_invariants(state)


def test_strategy_outcome_shapes_and_extras_independence():
    p = {strategy: probabilities(strategy=strategy) for strategy in StrategyId}
    preserve, rotate, balanced, attack, all_out = (p[s] for s in StrategyId)
    assert (
        preserve.wicket_probability
        < rotate.wicket_probability
        < balanced.wicket_probability
        < attack.wicket_probability
        < all_out.wicket_probability
    )
    assert (
        preserve.boundary_probability
        < rotate.boundary_probability
        < balanced.boundary_probability
        < attack.boundary_probability
        < all_out.boundary_probability
    )
    assert sum(rotate.legal[1:4]) == max(sum(d.legal[1:4]) for d in p.values())
    assert all_out.legal[5] > attack.legal[5] > balanced.legal[5]
    assert all_out.legal[0] > attack.legal[0] > balanced.legal[0] > rotate.legal[0]
    assert len({d.legality for d in p.values()}) == 1
    assert all(d.legal[3] > 0 for d in p.values())


def test_attributes_and_matchups():
    base = TEAM[0]
    strong_control = replace(base, batting_control=95)
    weak_control = replace(base, batting_control=45)
    strong_bowler = replace(OPPONENT[-1], bowling_threat=95, bowling_control=95)
    weak_bowler = replace(strong_bowler, bowling_threat=45, bowling_control=45)
    assert (
        probabilities(batter=strong_control, bowler=strong_bowler).wicket_probability
        < probabilities(batter=weak_control, bowler=strong_bowler).wicket_probability
    )
    power = replace(base, batting_power=95)
    assert (
        probabilities(
            batter=power, bowler=weak_bowler, strategy=StrategyId.ATTACK
        ).boundary_probability
        > probabilities(
            batter=replace(power, batting_power=45), bowler=weak_bowler, strategy=StrategyId.ATTACK
        ).boundary_probability
    )
    assert (
        probabilities(batter=weak_control, bowler=strong_bowler).expected_runs
        < probabilities(batter=strong_control, bowler=weak_bowler).expected_runs
    )
    assert (
        probabilities(bowler=strong_bowler).legality[1]
        < probabilities(bowler=weak_bowler).legality[1]
    )
    assert probabilities(
        bowler=replace(strong_bowler, bowling_style=BowlingStyle.PACE)
    ) != probabilities(bowler=replace(strong_bowler, bowling_style=BowlingStyle.SPIN))
    specialist = replace(base, batting_rotation=95)
    rotate_gain = probabilities(batter=specialist, strategy=StrategyId.ROTATE).probability(
        Outcome.TWO
    ) - probabilities(batter=base, strategy=StrategyId.ROTATE).probability(Outcome.TWO)
    attack_gain = probabilities(batter=specialist, strategy=StrategyId.ATTACK).probability(
        Outcome.TWO
    ) - probabilities(batter=base, strategy=StrategyId.ATTACK).probability(Outcome.TWO)
    assert rotate_gain > attack_gain


def test_context_changes_repeated_plan_without_repetition_penalty():
    state = initial_state(TEAM, OPPONENT)
    original = probabilities(state, StrategyId.ATTACK)
    productive = copy.deepcopy(state)
    for _ in range(6):
        apply_delivery(state, Outcome.DOT)
        apply_delivery(productive, Outcome.TWO)
    assert probabilities(state, StrategyId.ATTACK) != original
    assert (
        probabilities(state, StrategyId.ATTACK).wicket_probability
        > probabilities(productive, StrategyId.ATTACK).wicket_probability
    )
    low, high = replace(RULES, target=100), replace(RULES, target=280)
    assert (
        probabilities(rules=high).wicket_probability > probabilities(rules=low).wicket_probability
    )
    assert (
        derive_context(state, *profiles(state), high).pressure
        > derive_context(state, *profiles(state), low).pressure
    )
    unset = copy.deepcopy(state)
    settled = copy.deepcopy(state)
    settled.batting[settled.striker].balls = 15
    assert (
        probabilities(settled, StrategyId.ATTACK).wicket_probability
        < probabilities(unset, StrategyId.ATTACK).wicket_probability
    )
    tail = copy.deepcopy(state)
    for _ in range(8):
        apply_delivery(tail, Outcome.WICKET)
    assert (
        probabilities(tail, StrategyId.ATTACK).expected_runs
        < probabilities(state, StrategyId.ATTACK).expected_runs
    )
    assert (
        probabilities(tail, StrategyId.PRESERVE).wicket_probability
        < probabilities(tail, StrategyId.ALL_OUT).wicket_probability
    )


@given(
    control=st.floats(1, 100), power=st.floats(1, 100), threat=st.floats(1, 100), free=st.booleans()
)
@settings(max_examples=80, deadline=None)
def test_probability_safety(control, power, threat, free):
    state = initial_state(TEAM, OPPONENT)
    state.free_hit = free
    for strategy in StrategyId:
        p = probabilities(
            state,
            strategy,
            replace(TEAM[0], batting_control=control, batting_power=power),
            replace(OPPONENT[-1], bowling_threat=threat),
        )
        assert sum(p.legal) == pytest.approx(1)
        assert sum(p.legality) == pytest.approx(1)
        assert all(0 <= value <= 1 for value in (*p.legal, *p.legality))
        assert p.legal[-1] <= RULES.wicket_probability_max
        assert not free or p.wicket_probability == 0
        assert sum(p.probability(o) for o in Outcome) == pytest.approx(1)


def test_invalid_rng_and_immutable_rules():
    with pytest.raises(ValueError):
        sample(probabilities(), Draws(float("nan")))
    with pytest.raises(FrozenInstanceError):
        RULES.target = 10
    with pytest.raises(TypeError):
        RULESETS["v2.0"] = replace(RULES, target=10)


def test_each_delivery_recalculates_matchup_and_changes_bowler(monkeypatch):
    from chase_engine import simulation

    calls = []
    original = simulation.distribution

    def observe(state, batter, partner, bowler, strategy, rules):
        calls.append((state.balls, batter.id, bowler.id, state.partnership_runs))
        return original(state, batter, partner, bowler, strategy, rules)

    monkeypatch.setattr(simulation, "distribution", observe)
    monkeypatch.setattr(simulation, "sample", lambda *_: Outcome.ONE)
    state = initial_state(TEAM, OPPONENT)
    result = simulate_step(state, TEAM, OPPONENT, StrategyId.ROTATE, 12, RULES, random.Random(1))
    assert [c[0] for c in calls] == list(range(12))
    assert len({c[1] for c in calls}) == 2
    assert calls[0][2] != calls[6][2]
    assert [c[3] for c in calls] == list(range(12))
    assert result.events[0]["interruption"] == "WINDOW_END"
    assert result.state.balls == 12 and result.state.runs == 12
    assert_invariants(result.state)


def test_v1_seed_fixtures_preserved():
    import importlib.util

    script = Path(__file__).parents[1] / "scripts/baseline.py"
    spec = importlib.util.spec_from_file_location("baseline", script)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    reference = json.loads((Path(__file__).parents[3] / "docs/legacy-baseline.json").read_text())
    actual = baseline.characterize(3)
    assert [p["replaySHA256"] for p in actual["policies"]] == [
        p["replaySHA256"] for p in reference["policies"]
    ]


@pytest.mark.parametrize("version,filename", [("v2.0", "v2-replay.json"), ("v2.1", "v21-replay.json")])
def test_v2_frozen_replay_fixtures(version, filename):
    fixture = Path(__file__).parent / "fixtures" / filename
    actual = {
        strategy.value: hashlib.sha256(
            json.dumps(play(201, strategy, RULESETS[version])[1], sort_keys=True).encode()
        ).hexdigest()
        for strategy in StrategyId
    }
    assert actual == json.loads(fixture.read_text())


def test_all_out_still_has_value_when_only_a_six_will_win():
    state = initial_state(TEAM, OPPONENT)
    state.balls = 119
    state.runs = 195
    plans = {s: probabilities(state, s) for s in StrategyId}
    assert plans[StrategyId.ALL_OUT].probability(Outcome.SIX) == max(
        p.probability(Outcome.SIX) for p in plans.values()
    )
    state.free_hit = True
    for plan in StrategyId:
        assert probabilities(state, plan).wicket_probability == 0


def test_strong_set_batters_cannot_restore_the_old_all_out_six_boost():
    state = initial_state(TEAM, OPPONENT)
    for _ in range(30):
        apply_delivery(state, Outcome.ONE)
    star = replace(TEAM[0], batting_control=100, batting_power=100)
    old = probabilities(state, StrategyId.ALL_OUT, batter=star, rules=RULESETS["v2.0"])
    new = probabilities(state, StrategyId.ALL_OUT, batter=star)
    assert new.legal[5] < old.legal[5] * 0.8
    assert new.wicket_probability > old.wicket_probability
