"""Repetition changes probabilities, never releases a fixed run budget per ball."""

from dataclasses import dataclass
from types import MappingProxyType

from chase_engine.v32.rules import Ruleset as PreviousRuleset


@dataclass(frozen=True)
class Ruleset(PreviousRuleset):
    version: str = "v3.4"
    # Shared priors keep adaptive play competitive after removing batting ability.
    phase_weights: tuple[tuple[float, ...], ...] = (
        (0.280, 0.300, 0.105, 0.006, 0.1976715, 0.0760275, 0.04785),
        (0.290, 0.320, 0.110, 0.008, 0.162192, 0.060822, 0.0522),
        (0.280, 0.260, 0.110, 0.006, 0.2078085, 0.0861645, 0.06525),
    )
    batting_vector: tuple[float, ...] = (0.0,) * 7
    sustainable_base_rate: float = 8.875
    sustainable_attribute_rate: float = 0.0
    repetition_window: int = 24
    repetition_grace: int = 0
    # DOT / ONE / TWO / THREE / FOUR / SIX / WICKET, by approach.
    repetition_vectors: tuple[tuple[float, ...], ...] = (
        (0.15, 0.05, -0.05, -0.10, -0.60, -0.80, 0.25),
        (0.036, 0.018, -0.018, -0.030, -0.135, -0.195, 0.030),
        (0.066, -0.015, -0.030, -0.045, -0.105, -0.135, 0.075),
    )


DEFAULT_RULES = Ruleset()
RULESETS = MappingProxyType({DEFAULT_RULES.version: DEFAULT_RULES})
