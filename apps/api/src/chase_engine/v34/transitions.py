"""Cricket accounting with only the winning-run guard for a single approach."""

from chase_engine.v31 import transitions as previous
from chase_engine.v31.transitions import current_bowler as current_bowler
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v32.transitions import permitted_outcome as permitted_outcome
from chase_engine.v33.transitions import initial_state as initial_state
from chase_engine.v33.types import GameState
from chase_engine.v34.rules import DEFAULT_RULES, Ruleset

EXTRAS = (Outcome.WIDE, Outcome.NO_BALL)


def apply_delivery(
    state: GameState,
    outcome: Outcome,
    rules: Ruleset = DEFAULT_RULES,
    *,
    strategy: StrategyId | None = None,
) -> dict:
    if strategy is None:
        raise ValueError("Every delivery needs its batting approach")
    outcome = permitted_outcome(state, outcome, strategy, rules)
    delivery = previous.apply_delivery(state, outcome, rules)
    if outcome not in EXTRAS:
        if strategy.value not in state.approaches_used:
            state.approaches_used.append(strategy.value)
        state.recent_approaches = [*state.recent_approaches, strategy.value][
            -rules.repetition_window :
        ]
    return delivery
