"""Versioned balance; v3.1 saves retain their original coefficients."""

from dataclasses import dataclass
from types import MappingProxyType

from chase_engine.v31.rules import Ruleset as PreviousRuleset


@dataclass(frozen=True)
class Ruleset(PreviousRuleset):
    version: str = "v3.2"
    # Shared boundary priors, calibrated against randomized legal drafts.
    phase_weights: tuple[tuple[float, ...], ...] = (
        (0.280, 0.300, 0.105, 0.006, 0.17355, 0.06675, 0.055),
        (0.290, 0.320, 0.110, 0.008, 0.1424, 0.0534, 0.060),
        (0.280, 0.260, 0.110, 0.006, 0.18245, 0.07565, 0.075),
    )


DEFAULT_RULES = Ruleset()
RULESETS = MappingProxyType({DEFAULT_RULES.version: DEFAULT_RULES})
