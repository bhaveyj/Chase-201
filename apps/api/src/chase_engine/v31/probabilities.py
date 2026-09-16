"""Outcome-specific logit kernel, independent of randomness and score mutation."""

import math

from chase_engine.v31.context import derive_context
from chase_engine.v31.rules import DEFAULT_RULES, Ruleset, phase_index
from chase_engine.v31.types import (
    BowlingStyle,
    GameState,
    OutcomeDistribution,
    PlayerProfile,
    StrategyAssessment,
    StrategyId,
)


def softmax(logits: list[float]) -> tuple[float, ...]:
    peak = max(logits)
    weights = [math.exp(value - peak) for value in logits]
    total = sum(weights)
    return tuple(weight / total for weight in weights)


def distribution(
    state: GameState,
    batter: PlayerProfile,
    partner: PlayerProfile,
    bowler: PlayerProfile,
    strategy: StrategyId,
    rules: Ruleset = DEFAULT_RULES,
) -> OutcomeDistribution:
    context = derive_context(state, batter, partner, bowler, rules)
    phase = phase_index(state.balls, rules)
    plan = list(StrategyId).index(strategy)
    logits = [math.log(weight) for weight in rules.phase_weights[phase]]

    def add(vector: tuple[float, ...], scale: float = 1) -> None:
        for i, value in enumerate(vector):
            logits[i] += value * scale

    def attribute(value: float) -> float:
        return (value - rules.attribute_center) / rules.attribute_scale

    add(rules.strategy_vectors[plan])
    add(rules.batting_vector, attribute(batter.batting))
    add(rules.bowling_control_vector, attribute(bowler.bowling_control))
    add(rules.bowling_threat_vector, attribute(bowler.bowling_threat))
    styles = rules.pace_vectors if bowler.bowling_style == BowlingStyle.PACE else rules.spin_vectors
    add(styles[phase])
    add(rules.setness_vector, context.striker_setness * rules.setness_scale)
    add(rules.dot_pressure_vector, context.recent_pressure)
    add(rules.chase_pressure_vector, context.pressure)
    add(rules.partnership_vector, context.partnership_stability)
    logits = [max(-rules.logit_limit, min(rules.logit_limit, value)) for value in logits]
    if state.free_hit:
        logits[-1] = -math.inf
    legal = softmax(logits)
    if legal[-1] > rules.wicket_probability_max:
        scale = (1 - rules.wicket_probability_max) / (1 - legal[-1])
        legal = (*[p * scale for p in legal[:-1]], rules.wicket_probability_max)
    control = math.exp(-attribute(bowler.bowling_control) * rules.extras_control_scale)
    wide = max(rules.extras_min, min(rules.extras_max, rules.wide_base * control))
    no_ball = max(rules.extras_min, min(rules.extras_max, rules.no_ball_base * control))
    legality = (1 - wide - no_ball, wide, no_ball)
    return OutcomeDistribution(
        legal,
        legality,
        legality[0] * sum(p * runs for p, runs in zip(legal, (0, 1, 2, 3, 4, 6, 0), strict=True))
        + wide
        + no_ball,
        legality[0] * legal[-1],
        legality[0] * (legal[4] + legal[5]),
    )


def assess(
    strategy: StrategyId, outcomes: OutcomeDistribution, rules: Ruleset = DEFAULT_RULES
) -> StrategyAssessment:
    bands = ("Very low", "Low", "Moderate", "High", "Very high")

    def band(value: float, thresholds: tuple[float, ...]) -> str:
        return bands[sum(value >= x for x in thresholds)]

    return StrategyAssessment(
        strategy,
        band(outcomes.expected_runs, rules.scoring_thresholds),
        "None (free hit)"
        if outcomes.wicket_probability == 0
        else band(outcomes.wicket_probability, rules.wicket_thresholds),
        band(outcomes.boundary_probability, rules.boundary_thresholds),
        outcomes.wicket_probability,
    )
