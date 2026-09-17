"""Enforce approach variation before scoring, preserving cricket accounting."""

from dataclasses import asdict

from chase_engine.v31 import transitions as previous
from chase_engine.v31.transitions import current_bowler as current_bowler
from chase_engine.v31.types import Outcome, PlayerProfile, StrategyId
from chase_engine.v32.rules import DEFAULT_RULES, Ruleset
from chase_engine.v32.types import GameState

EXTRAS = (Outcome.WIDE, Outcome.NO_BALL)


def initial_state(user_team: list[PlayerProfile], opponent: list[PlayerProfile]) -> GameState:
    return GameState.from_dict(asdict(previous.initial_state(user_team, opponent)))


def permitted_outcome(
    state: GameState,
    outcome: Outcome,
    strategy: StrategyId | None,
    rules: Ruleset = DEFAULT_RULES,
) -> Outcome:
    approaches = set(state.approaches_used)
    if strategy is not None and outcome not in EXTRAS:
        approaches.add(strategy.value)
    runs = 1 if outcome in EXTRAS else previous.RUNS.get(outcome, 0)
    # A single approach may reach 200, but cannot score the winning runs.
    # Redirect the entire scoring outcome to a dot before updating any ledger.
    if runs and state.runs + runs >= rules.target and len(approaches) < 2:
        return Outcome.DOT
    return outcome


def apply_delivery(
    state: GameState,
    outcome: Outcome,
    rules: Ruleset = DEFAULT_RULES,
    *,
    strategy: StrategyId | None = None,
) -> dict:
    outcome = permitted_outcome(state, outcome, strategy, rules)
    delivery = previous.apply_delivery(state, outcome, rules)
    if (
        strategy is not None
        and outcome not in EXTRAS
        and strategy.value not in state.approaches_used
    ):
        state.approaches_used.append(strategy.value)
    return delivery
