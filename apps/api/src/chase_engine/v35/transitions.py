"""Cricket accounting and persisted legal-delivery approach history."""

from chase_engine.v31 import transitions as previous
from chase_engine.v31.transitions import current_bowler as current_bowler
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v33.transitions import initial_state as initial_state
from chase_engine.v33.types import GameState
from chase_engine.v35.rules import DEFAULT_RULES, Ruleset


def apply_delivery(
    state: GameState,
    outcome: Outcome,
    rules: Ruleset = DEFAULT_RULES,
    *,
    strategy: StrategyId | None = None,
) -> dict:
    if strategy is None:
        raise ValueError("A strategy is required to persist approach history")
    delivery = previous.apply_delivery(state, outcome, rules)
    if outcome not in (Outcome.WIDE, Outcome.NO_BALL):
        if strategy.value not in state.approaches_used:
            state.approaches_used.append(strategy.value)
        state.recent_approaches = [*state.recent_approaches, strategy.value][
            -rules.repetition_window :
        ]
    return delivery
