"""Sample dots, singles and boundaries throughout the innings without paced caps."""

import math

from chase_engine.v31.probabilities import assess as assess
from chase_engine.v31.probabilities import distribution as previous_distribution
from chase_engine.v31.types import Outcome, OutcomeDistribution, PlayerProfile, StrategyId
from chase_engine.v33.types import GameState
from chase_engine.v34.context import neutral_batter
from chase_engine.v34.rules import DEFAULT_RULES, Ruleset
from chase_engine.v34.transitions import permitted_outcome


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
    recent = state.recent_approaches[-rules.repetition_window :]
    repetition = max(0, recent.count(strategy.value) - rules.repetition_grace) / (
        rules.repetition_window - rules.repetition_grace
    )
    vector = rules.repetition_vectors[list(StrategyId).index(strategy)]
    weights = [
        p * math.exp(value * repetition) for p, value in zip(base.legal, vector, strict=True)
    ]
    legal = tuple(weight / sum(weights) for weight in weights)
    if legal[-1] > rules.wicket_probability_max:
        scale = (1 - rules.wicket_probability_max) / (1 - legal[-1])
        legal = (*[p * scale for p in legal[:-1]], rules.wicket_probability_max)
    masses = dict.fromkeys(Outcome, 0.0)
    for outcome, probability in zip(list(Outcome)[:7], legal, strict=True):
        masses[permitted_outcome(state, outcome, strategy, rules)] += base.legality[0] * probability
    for outcome in (Outcome.WIDE, Outcome.NO_BALL):
        masses[permitted_outcome(state, outcome, strategy, rules)] += base.probability(outcome)
    wide, no_ball = masses[Outcome.WIDE], masses[Outcome.NO_BALL]
    legal_mass = 1 - wide - no_ball
    return OutcomeDistribution(
        tuple(masses[outcome] / legal_mass for outcome in list(Outcome)[:7]),
        (legal_mass, wide, no_ball),
        sum(
            masses[outcome] * runs
            for outcome, runs in zip(Outcome, (0, 1, 2, 3, 4, 6, 0, 1, 1), strict=True)
        ),
        masses[Outcome.WICKET],
        masses[Outcome.FOUR] + masses[Outcome.SIX],
    )
