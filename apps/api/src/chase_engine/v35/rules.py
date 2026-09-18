"""Frozen probability tuning; no score ceiling or winning-run qualification."""

from dataclasses import dataclass
from types import MappingProxyType

from chase_engine.v34.rules import Ruleset as PreviousRuleset


@dataclass(frozen=True)
class Ruleset(PreviousRuleset):
    version: str = "v3.5"
    # Adaptation is based on legal deliveries, not clicks or the innings score.
    repetition_saturation: tuple[int, ...] = (24, 24, 18)
    repetition_vectors: tuple[tuple[float, ...], ...] = (
        (0.15, 0.05, -0.05, -0.10, -0.60, -0.80, 0.25),
        (0.036, 0.018, -0.018, -0.030, -0.135, -0.195, 0.030),
        (0.086, -0.015, -0.030, -0.045, -0.180, -0.235, 0.125),
    )


DEFAULT_RULES = Ruleset()
RULESETS = MappingProxyType({DEFAULT_RULES.version: DEFAULT_RULES})
