"""Scoring pace and repetition tuning, separate from saved v3.2 matches."""

from dataclasses import dataclass
from types import MappingProxyType

from chase_engine.v32.rules import Ruleset as PreviousRuleset


@dataclass(frozen=True)
class Ruleset(PreviousRuleset):
    version: str = "v3.3"
    phase_weights: tuple[tuple[float, ...], ...] = (
        (0.280, 0.300, 0.105, 0.006, 0.18135, 0.06975, 0.055),
        (0.290, 0.320, 0.110, 0.008, 0.1488, 0.0558, 0.060),
        (0.280, 0.260, 0.110, 0.006, 0.19065, 0.07905, 0.075),
    )
    repetition_window: int = 24
    repetition_grace: int = 12
    # DOT / ONE / TWO / THREE / FOUR / SIX / WICKET, by approach.
    repetition_vectors: tuple[tuple[float, ...], ...] = (
        (0.15, 0.05, -0.05, -0.10, -0.60, -0.80, 0.30),
        (0.036, 0.018, -0.018, -0.030, -0.135, -0.195, 0.030),
        (0.066, -0.015, -0.030, -0.045, -0.105, -0.135, 0.075),
    )
    single_approach_totals: tuple[int, ...] = (150, 180, 185)
    single_approach_headroom: int = 60


DEFAULT_RULES = Ruleset()
RULESETS = MappingProxyType({DEFAULT_RULES.version: DEFAULT_RULES})
