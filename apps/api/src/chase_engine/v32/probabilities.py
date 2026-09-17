"""The displayed next-delivery assessment includes the approach requirement."""

from chase_engine.v31.probabilities import assess as assess
from chase_engine.v31.probabilities import distribution as previous_distribution
from chase_engine.v31.types import Outcome, OutcomeDistribution, PlayerProfile, StrategyId
from chase_engine.v32.rules import DEFAULT_RULES, Ruleset
from chase_engine.v32.transitions import permitted_outcome
from chase_engine.v32.types import GameState


def distribution(
    state: GameState,
    batter: PlayerProfile,
    partner: PlayerProfile,
    bowler: PlayerProfile,
    strategy: StrategyId,
    rules: Ruleset = DEFAULT_RULES,
) -> OutcomeDistribution:
    base = previous_distribution(state, batter, partner, bowler, strategy, rules)
    if len(state.approaches_used) >= 2 or state.runs + 6 < rules.target:
        return base
    masses = dict.fromkeys(Outcome, 0.0)
    for outcome in Outcome:
        masses[permitted_outcome(state, outcome, strategy, rules)] += base.probability(outcome)
    wide, no_ball = masses[Outcome.WIDE], masses[Outcome.NO_BALL]
    legal_mass = 1 - wide - no_ball
    legal = tuple(masses[outcome] / legal_mass for outcome in list(Outcome)[:7])
    return OutcomeDistribution(
        legal,
        (legal_mass, wide, no_ball),
        sum(
            masses[outcome] * runs
            for outcome, runs in zip(Outcome, (0, 1, 2, 3, 4, 6, 0, 1, 1), strict=True)
        ),
        masses[Outcome.WICKET],
        masses[Outcome.FOUR] + masses[Outcome.SIX],
    )
