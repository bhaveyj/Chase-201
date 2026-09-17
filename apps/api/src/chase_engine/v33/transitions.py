"""Spread fixed-approach scoring capacity across the innings, not a late wall."""

from dataclasses import asdict

from chase_engine.v31 import transitions as previous
from chase_engine.v31.transitions import current_bowler as current_bowler
from chase_engine.v31.types import Outcome, PlayerProfile, StrategyId
from chase_engine.v33.rules import DEFAULT_RULES, Ruleset
from chase_engine.v33.types import GameState

EXTRAS = (Outcome.WIDE, Outcome.NO_BALL)
SCORING = {runs: outcome for outcome, runs in previous.RUNS.items()}


def initial_state(user_team: list[PlayerProfile], opponent: list[PlayerProfile]) -> GameState:
    return GameState.from_dict(asdict(previous.initial_state(user_team, opponent)))


def permitted_outcome(
    state: GameState,
    outcome: Outcome,
    strategy: StrategyId | None,
    rules: Ruleset = DEFAULT_RULES,
) -> Outcome:
    if strategy is None:
        raise ValueError("Every delivery needs its batting approach")
    approaches = set(state.approaches_used)
    if outcome not in EXTRAS:
        approaches.add(strategy.value)
    if len(approaches) > 1:
        return outcome
    # Extras cannot count as a switch or release the next legal ball's capacity.
    only_approach = next(iter(approaches), strategy.value)
    total = min(
        rules.target - 1,
        rules.single_approach_totals[list(StrategyId).index(StrategyId(only_approach))],
    )
    legal_balls = min(rules.legal_balls, state.balls + int(outcome not in EXTRAS))
    headroom = min(total, rules.single_approach_headroom)
    ceiling = headroom + (total - headroom) * legal_balls // rules.legal_balls
    available = max(0, ceiling - state.runs)
    runs = 1 if outcome in EXTRAS else previous.RUNS.get(outcome, 0)
    if runs <= available:
        return outcome
    # Well-set fields turn a boundary attempt into runs that can be taken.
    # New scoring capacity opens on every legal ball, including the last ten.
    return SCORING[max(value for value in SCORING if value <= available)]


def apply_delivery(
    state: GameState,
    outcome: Outcome,
    rules: Ruleset = DEFAULT_RULES,
    *,
    strategy: StrategyId | None = None,
) -> dict:
    outcome = permitted_outcome(state, outcome, strategy, rules)
    delivery = previous.apply_delivery(state, outcome, rules)
    assert strategy is not None
    if outcome not in EXTRAS:
        if strategy.value not in state.approaches_used:
            state.approaches_used.append(strategy.value)
        state.recent_approaches = [*state.recent_approaches, strategy.value][
            -rules.repetition_window :
        ]
    return delivery
