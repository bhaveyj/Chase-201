"""Two categorical stages; randomness is always injected by the caller."""

import math
from collections.abc import Sequence

from chase_engine.v31.types import Outcome, OutcomeDistribution, RandomSource


def categorical(weights: Sequence[float], rng: RandomSource) -> int:
    value = rng.random()
    if not math.isfinite(value) or not 0 <= value < 1:
        raise ValueError("Random source must return a finite value in [0, 1)")
    cumulative = 0.0
    for i, weight in enumerate(weights):
        cumulative += weight
        if value < cumulative:
            return i
    return max(i for i, weight in enumerate(weights) if weight > 0)


def sample(outcomes: OutcomeDistribution, rng: RandomSource) -> Outcome:
    legality = categorical(outcomes.legality, rng)
    if legality:
        return (Outcome.WIDE, Outcome.NO_BALL)[legality - 1]
    return list(Outcome)[categorical(outcomes.legal, rng)]
