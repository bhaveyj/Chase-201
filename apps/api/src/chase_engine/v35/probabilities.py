"""Adjust repeated play before sampling; retain every sampled scoring outcome."""

import math

from chase_engine.v31.probabilities import assess as assess
from chase_engine.v31.probabilities import distribution as previous_distribution
from chase_engine.v31.types import OutcomeDistribution, PlayerProfile, StrategyId
from chase_engine.v33.types import GameState
from chase_engine.v34.context import neutral_batter
from chase_engine.v35.rules import DEFAULT_RULES, Ruleset


def distribution(
    state: GameState,
    batter: PlayerProfile,
    partner: PlayerProfile,
    bowler: PlayerProfile,
    strategy: StrategyId,
    rules: Ruleset = DEFAULT_RULES,
) -> OutcomeDistribution:
    base = previous_distribution(
        state, neutral_batter(batter), neutral_batter(partner), bowler, strategy, rules
    )
    index = list(StrategyId).index(strategy)
    recent = state.recent_approaches[-rules.repetition_window :]
    repetition = min(1.0, recent.count(strategy.value) / rules.repetition_saturation[index])
    vector = rules.repetition_vectors[index]
    weights = [
        p * math.exp(value * repetition) for p, value in zip(base.legal, vector, strict=True)
    ]
    total = sum(weights)
    legal = tuple(weight / total for weight in weights)
    if legal[-1] > rules.wicket_probability_max:
        scale = (1 - rules.wicket_probability_max) / (1 - legal[-1])
        legal = (*[p * scale for p in legal[:-1]], rules.wicket_probability_max)
    return OutcomeDistribution(
        legal,
        base.legality,
        base.legality[0]
        * sum(p * runs for p, runs in zip(legal, (0, 1, 2, 3, 4, 6, 0), strict=True))
        + sum(base.legality[1:]),
        base.legality[0] * legal[-1],
        base.legality[0] * (legal[4] + legal[5]),
    )
