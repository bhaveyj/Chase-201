import copy
import random
from dataclasses import asdict
from statistics import mean

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chase_engine.engine import (
    Player,
    Ruleset,
    Strategy,
    _probabilities,
    decision_window,
    initial_state,
    simulate_step,
)

ROLES = ["BATTER"] * 5 + ["WICKETKEEPER"] + ["ALL_ROUNDER"] * 2 + ["BOWLER"] * 3
TEAM = [
    Player(
        str(i),
        82 if role != "BOWLER" else 46,
        80 if role in {"BOWLER", "ALL_ROUNDER"} else 30,
        role,
    )
    for i, role in enumerate(ROLES)
]
OPPONENT = [Player(f"ai{i}", 80, 80, role) for i, role in enumerate(ROLES)]
RULES = Ruleset()


def assert_invariants(s):
    assert 0 <= s.runs <= 206
    assert 0 <= s.wickets <= 10
    assert 0 <= s.balls <= 120
    assert s.runs == sum(b.runs for b in s.batting) + s.wides + s.no_balls
    assert s.runs == sum(b.runs for b in s.bowling)
    assert s.wickets == sum(b.out for b in s.batting) == sum(b.wickets for b in s.bowling)
    assert s.balls == sum(b.balls for b in s.batting) == sum(b.balls for b in s.bowling)
    assert all(0 <= b.balls <= 24 for b in s.bowling)
    assert all(b.runs >= b.fours * 4 + b.sixes * 6 for b in s.batting)
    assert all(a != b for a, b in zip(s.over_bowlers, s.over_bowlers[1:], strict=False))
    assert 0 <= s.striker <= 10 and 0 <= s.non_striker <= 10 and s.striker != s.non_striker
    if s.status == "LIVE":
        assert not s.batting[s.striker].out and not s.batting[s.non_striker].out
        assert s.runs < 201 and s.balls < 120 and s.wickets < 10


def play(seed, strategy=Strategy()):
    s = initial_state(TEAM, OPPONENT)
    revision = 0
    while s.status == "LIVE":
        before = copy.deepcopy(s)
        result = simulate_step(
            s,
            TEAM,
            OPPONENT,
            strategy,
            decision_window(s.balls),
            RULES,
            random.Random(seed * 1000 + revision),
        )
        assert s == before
        assert result.events[0]["runs"] == result.state.runs - s.runs
        assert result.events[0]["kind"] == ("DELIVERY" if s.balls >= 108 else "AGGREGATE")
        s = result.state
        assert_invariants(s)
        revision += 1
        assert revision < 80
    return s


@given(
    seed=st.integers(min_value=0, max_value=100_000),
    intent=st.sampled_from(["DEFEND", "ROTATE", "ATTACK"]),
    risk=st.sampled_from(["PROTECT_WICKETS", "BALANCED", "MAXIMIZE_RUNS"]),
)
@settings(max_examples=150, deadline=None)
def test_full_match_invariants(seed, intent, risk):
    play(seed, Strategy(intent, risk))


def test_determinism_and_input_immutability():
    assert asdict(play(201)) == asdict(play(201))
    assert asdict(play(201)) != asdict(play(202))


@pytest.mark.parametrize(
    "balls,window",
    [
        (0, 18),
        (18, 18),
        (36, 12),
        (60, 12),
        (72, 6),
        (90, 6),
        (96, 3),
        (105, 3),
        (108, 1),
        (119, 1),
        (120, 0),
    ],
)
def test_windows(balls, window):
    assert decision_window(balls) == window


class Constant:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def at_finish(runs=180, balls=119):
    s = initial_state(TEAM, OPPONENT)
    s.runs = s.batting[0].runs = runs
    s.balls = s.batting[0].balls = balls
    for i, bowler in enumerate(s.bowling):
        bowler.balls = sum(
            min(6, balls - over * 6)
            for over in range(balls // 6 + int(balls % 6 > 0))
            if over % 5 == i
        )
    s.bowling[0].runs = runs
    s.over_bowlers = [s.bowling[i % 5].player_id for i in range(balls // 6 + int(balls % 6 > 0))]
    return s


def outcome_rng(s, outcome):
    bowler = next(p for p in OPPONENT if p.id == s.bowling[s.balls // 6 % 5].player_id)
    probs = _probabilities(s, TEAM[s.striker], bowler, Strategy(), RULES)
    return Constant(sum(probs[:outcome]) + probs[outcome] / 2)


def test_tie_and_exact_target_and_immediate_finish():
    s = at_finish(200)
    tie = simulate_step(s, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(s, 0)).state
    assert tie.status == "TIED" and tie.balls == 120
    win = simulate_step(s, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(s, 4)).state
    assert win.status == "WON" and win.runs == 201
    with pytest.raises(ValueError):
        simulate_step(win, TEAM, OPPONENT, Strategy(), 1, RULES, random.Random(1))
    s = at_finish(200, 108)
    win = simulate_step(s, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(s, 6)).state
    assert win.status == "WON" and win.runs == 201 and win.balls == 108
    assert_invariants(win)


def test_wides_no_balls_free_hits_and_strike():
    s = at_finish(150, 114)
    nb = simulate_step(s, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(s, 7)).state
    assert nb.free_hit and nb.no_balls == 1 and nb.balls == s.balls
    wide = simulate_step(nb, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(nb, 6)).state
    assert wide.free_hit and wide.wides == 1 and wide.balls == s.balls
    single = simulate_step(wide, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(wide, 4)).state
    assert single.striker == s.non_striker and single.non_striker == s.striker
    assert not single.free_hit and single.balls == 115
    assert_invariants(single)
    for seed in range(80):
        assert (
            simulate_step(
                nb,
                TEAM,
                OPPONENT,
                Strategy("ATTACK", "MAXIMIZE_RUNS"),
                1,
                RULES,
                random.Random(seed),
            ).state.wickets
            == 0
        )


def test_tenth_wicket_ends_immediately():
    s = at_finish(170, 115)
    s.wickets = 9
    s.striker, s.non_striker, s.next_batter = 9, 10, 11
    for b in s.batting[:9]:
        b.out = True
    s.bowling[0].wickets = 9
    result = simulate_step(s, TEAM, OPPONENT, Strategy(), 1, RULES, outcome_rng(s, 5)).state
    assert result.status == "LOST" and result.wickets == 10 and result.balls == 116
    assert_invariants(result)


def test_strategy_changes_scoring_and_wicket_risk():
    # Compare a fixed powerplay horizon to avoid chase completion censoring aggression.
    outcomes = {}
    for strategy in [
        Strategy("DEFEND", "PROTECT_WICKETS"),
        Strategy(),
        Strategy("ATTACK", "MAXIMIZE_RUNS"),
    ]:
        samples = [
            simulate_step(
                initial_state(TEAM, OPPONENT),
                TEAM,
                OPPONENT,
                strategy,
                18,
                RULES,
                random.Random(seed),
            ).state
            for seed in range(1200)
        ]
        outcomes[strategy.intent] = (
            mean(s.runs for s in samples),
            mean(s.wickets for s in samples),
        )
    assert outcomes["DEFEND"][0] + 4 < outcomes["ROTATE"][0] < outcomes["ATTACK"][0] - 4
    assert outcomes["DEFEND"][1] < outcomes["ROTATE"][1] < outcomes["ATTACK"][1]


def test_balanced_strategy_calibration():
    wins = sum(play(seed).status == "WON" for seed in range(400))
    assert 0.30 < wins / 400 < 0.70, f"Balanced win rate: {wins / 400:.1%}"
