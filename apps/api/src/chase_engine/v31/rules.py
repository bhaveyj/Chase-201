"""Frozen versioned tuning. Behavioral changes require a new ruleset version.

Vectors follow DOT / ONE / TWO / THREE / FOUR / SIX / WICKET.
Tuples and frozen dataclasses prevent accidental in-process tuning.
"""

from dataclasses import dataclass
from types import MappingProxyType

from chase_engine.v31.types import StrategyId


@dataclass(frozen=True)
class Ruleset:
    version: str = "v3.1"
    target: int = 201
    legal_balls: int = 120
    wicket_limit: int = 10
    bowling_quota: int = 24
    # Common-seed calibration: 0.92 of v3.0 boundary priors in every phase.
    # Phase ratios and all requested batting/mode coefficients remain unchanged.
    phase_weights: tuple[tuple[float, ...], ...] = (
        (0.280, 0.300, 0.105, 0.006, 0.1794, 0.0690, 0.055),
        (0.290, 0.320, 0.110, 0.008, 0.1472, 0.0552, 0.060),
        (0.280, 0.260, 0.110, 0.006, 0.1886, 0.0782, 0.075),
    )
    phase_ends: tuple[int, ...] = (36, 96, 120)
    strategy_vectors: tuple[tuple[float, ...], ...] = (
        (-0.40, 0.65, 0.60, 0.40, -0.50, -1.00, -1.15),
        (-0.08, 0.12, 0.16, 0.10, 0.04, -0.04, -0.10),
        (0.65, -0.70, -0.35, -0.45, 0.62, 1.20, 0.85),
    )
    attribute_center: float = 75
    attribute_scale: float = 25
    batting_vector: tuple[float, ...] = (-0.30, 0.22, 0.26, 0.28, 0.30, 0.42, -0.50)
    bowling_control_vector: tuple[float, ...] = (0.22, -0.15, -0.12, -0.10, -0.08, -0.06, 0.03)
    bowling_threat_vector: tuple[float, ...] = (0.10, 0.00, 0.00, 0.00, -0.20, -0.24, 0.40)
    pace_vectors: tuple[tuple[float, ...], ...] = (
        (0.06, -0.03, -0.02, 0.00, 0.02, -0.04, 0.08),
        (0.00, 0.02, 0.00, 0.00, 0.02, 0.02, 0.00),
        (0.03, -0.02, 0.00, 0.00, 0.02, 0.04, 0.04),
    )
    spin_vectors: tuple[tuple[float, ...], ...] = (
        (-0.02, 0.03, 0.02, 0.00, 0.04, 0.04, -0.03),
        (0.06, -0.02, -0.03, -0.02, -0.04, -0.04, 0.06),
        (0.02, 0.02, 0.00, 0.00, 0.00, 0.02, 0.02),
    )
    setness_cap: int = 15
    settling_balls: int = 6
    setness_vector: tuple[float, ...] = (-0.12, 0.06, 0.04, 0.02, 0.12, 0.18, -0.28)
    setness_scale: float = 0.8
    dot_pressure_vector: tuple[float, ...] = (0.18, -0.12, -0.05, -0.03, 0.05, 0.08, 0.24)
    chase_pressure_vector: tuple[float, ...] = (0.14, -0.08, -0.03, -0.02, 0.04, 0.06, 0.24)
    partnership_vector: tuple[float, ...] = (-0.05, 0.04, 0.03, 0.00, 0.03, 0.03, -0.10)
    partnership_ball_cap: int = 24
    partnership_run_cap: int = 30
    sustainable_base_rate: float = 5.5
    sustainable_attribute_rate: float = 0.045
    sustainable_partner_weight: float = 0.30
    chase_pressure_start_ratio: float = 0.70
    chase_pressure_span: float = 0.90
    tail_pressure_scale: float = 0.10
    closing_pressure_scale: float = 0.12
    closing_pressure_balls: int = 24
    consecutive_dot_weight: float = 0.65
    recent_dot_weight: float = 0.35
    recent_wicket_pressure: float = 0.18
    pressure_thresholds: tuple[float, ...] = (0.25, 0.55, 0.85)
    wide_base: float = 0.018
    no_ball_base: float = 0.009
    extras_control_scale: float = 0.35
    extras_min: float = 0.002
    extras_max: float = 0.06
    logit_limit: float = 12
    wicket_probability_max: float = 0.40
    scoring_thresholds: tuple[float, ...] = (1.0, 1.6, 2.0, 2.5)
    boundary_thresholds: tuple[float, ...] = (0.12, 0.24, 0.36, 0.48)
    wicket_thresholds: tuple[float, ...] = (0.025, 0.055, 0.09, 0.15)
    matchup_edge: float = 10
    schedule: tuple[tuple[int, int], ...] = ((72, 12), (96, 6), (108, 3), (120, 1))
    stop_on_wicket: bool = True
    stop_on_no_ball: bool = True
    max_deliveries_per_window: int = 1000


DEFAULT_RULES = Ruleset()
RULESETS = MappingProxyType({DEFAULT_RULES.version: DEFAULT_RULES})
STRATEGY_LABELS = MappingProxyType(
    dict(zip(StrategyId, ("Defensive", "Balanced", "Aggressive"), strict=True))
)


def phase_index(balls: int, rules: Ruleset = DEFAULT_RULES) -> int:
    return next((i for i, end in enumerate(rules.phase_ends) if balls < end), 2)
