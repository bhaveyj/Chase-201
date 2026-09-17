"""Delivery-level windows bounded by cricket events and scheduled decision points."""

import copy
from dataclasses import dataclass

from chase_engine.v31.context import context_summary, derive_context
from chase_engine.v31.rules import STRATEGY_LABELS
from chase_engine.v31.sampling import sample
from chase_engine.v31.types import (
    DecisionWindow,
    Outcome,
    PlayerProfile,
    RandomSource,
    StrategyId,
)
from chase_engine.v32.probabilities import distribution
from chase_engine.v32.rules import DEFAULT_RULES, Ruleset
from chase_engine.v32.transitions import apply_delivery, current_bowler
from chase_engine.v32.types import GameState


@dataclass
class Transition:
    state: GameState
    events: list[dict]


def decision_window(balls: int, rules: Ruleset = DEFAULT_RULES) -> int:
    for end, size in rules.schedule:
        if balls < min(end, rules.legal_balls):
            return min(size - balls % size, end - balls, rules.legal_balls - balls)
    return 0


def window_for(state: GameState, rules: Ruleset = DEFAULT_RULES) -> DecisionWindow:
    if state.status != "LIVE":
        return DecisionWindow(0, "DELIVERY")
    delivery = state.free_hit or state.balls >= rules.schedule[-2][0]
    return DecisionWindow(
        1 if delivery else decision_window(state.balls, rules),
        "DELIVERY" if delivery else "AGGREGATE",
        rules.stop_on_wicket,
        rules.stop_on_no_ball,
    )


def simulate_step(
    game_state: GameState,
    user_team: list[PlayerProfile],
    opponent_team: list[PlayerProfile],
    strategy_decision: StrategyId,
    decision_window: int,
    ruleset: Ruleset,
    random_source: RandomSource,
) -> Transition:
    strategy = StrategyId(strategy_decision)
    window = window_for(game_state, ruleset)
    if game_state.status != "LIVE" or not 1 <= decision_window <= window.max_legal_balls:
        raise ValueError("Cannot simulate a completed match or invalid window")
    state = copy.deepcopy(game_state)
    users = {p.id: p for p in user_team}
    opponents = {p.id: p for p in opponent_team}

    def profiles() -> tuple[PlayerProfile, PlayerProfile, PlayerProfile]:
        return (
            users[state.batting[state.striker].player_id],
            users[state.batting[state.non_striker].player_id],
            opponents[current_bowler(state).player_id],
        )

    before_context = context_summary(state, derive_context(state, *profiles(), ruleset), ruleset)
    end = state.balls + decision_window
    deliveries: list[dict] = []
    interruption = "WINDOW_END"
    while state.balls < end and state.status == "LIVE":
        if len(deliveries) >= ruleset.max_deliveries_per_window:
            raise ValueError("Random source failed to produce legal play")
        outcome = sample(distribution(state, *profiles(), strategy, ruleset), random_source)
        deliveries.append(apply_delivery(state, outcome, ruleset, strategy=strategy))
        if state.status != "LIVE":
            interruption = "INNINGS_COMPLETE"
            break
        if outcome == Outcome.WICKET and window.stop_on_wicket:
            interruption = "WICKET"
            break
        if outcome == Outcome.NO_BALL and window.stop_on_no_ball:
            interruption = "NO_BALL"
            break
        if window.presentation_granularity == "DELIVERY":
            interruption = "FREE_HIT" if state.free_hit else "WINDOW_END"
            break
    after_context = (
        context_summary(state, derive_context(state, *profiles(), ruleset), ruleset)
        if state.status == "LIVE"
        else None
    )
    runs, wickets = state.runs - game_state.runs, state.wickets - game_state.wickets
    detail = f"{runs} runs, {wickets} wicket{'s' if wickets != 1 else ''}"
    if window.presentation_granularity == "DELIVERY":
        detail = {
            Outcome.DOT: "Dot ball",
            Outcome.WICKET: "Wicket",
            Outcome.WIDE: "Wide",
            Outcome.NO_BALL: "No-ball · free hit",
        }.get(outcome, f"{runs} run{'s' if runs != 1 else ''}")
    event = {
        "kind": window.presentation_granularity,
        "label": f"{STRATEGY_LABELS[strategy]} · {detail}",
        "strategy": strategy.value,
        "interruption": interruption,
        "fromBall": game_state.balls,
        "toBall": state.balls,
        "runs": runs,
        "wickets": wickets,
        "score": state.runs,
        "totalWickets": state.wickets,
        "freeHit": state.free_hit,
        "deliveries": deliveries,
        "contextBefore": before_context,
        "contextAfter": after_context,
    }
    return Transition(state, [event])
