"""Frozen versioned tuning. Behavioral changes require a new ruleset version.

Vectors follow DOT / ONE / TWO / THREE / FOUR / SIX / WICKET.
Tuples and frozen dataclasses prevent accidental in-process tuning.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType

from chase_engine.types import StrategyId


@dataclass(frozen=True)
class Ruleset:
    version: str = "v2.0"
    target: int = 201
    legal_balls: int = 120
    wicket_limit: int = 10
    bowling_quota: int = 24
    phase_weights: tuple[tuple[float, ...], ...] = (
        (0.280, 0.300, 0.105, 0.006, 0.195, 0.075, 0.055),
        (0.290, 0.320, 0.110, 0.008, 0.160, 0.060, 0.060),
        (0.280, 0.260, 0.110, 0.006, 0.205, 0.085, 0.075),
    )
    phase_ends: tuple[int, ...] = (36, 96, 120)
    strategy_vectors: tuple[tuple[float, ...], ...] = (
        (0.65, 0.15, -0.40, -0.55, -1.15, -1.80, -1.15),
        (-0.35, 0.55, 0.65, 0.70, -0.40, -0.70, -0.50),
        (-0.04, 0.06, 0.03, 0.00, 0.00, -0.02, -0.06),
        (0.30, -0.48, -0.22, -0.25, 0.42, 0.80, 0.70),
        (1.20, -1.30, -0.70, -0.75, 0.40, 1.90, 1.70),
    )
    attribute_center: float = 75
    attribute_scale: float = 25
    batting_control_vector: tuple[float, ...] = (-0.22, 0.08, 0.00, 0.00, 0.02, -0.04, -0.46)
    batting_rotation_vector: tuple[float, ...] = (-0.08, 0.18, 0.26, 0.28, 0.00, 0.00, -0.04)
    batting_power_vector: tuple[float, ...] = (0.00, -0.04, 0.00, 0.00, 0.28, 0.46, 0.00)
    bowling_control_vector: tuple[float, ...] = (0.22, -0.15, -0.12, -0.10, -0.08, -0.06, 0.03)
    bowling_threat_vector: tuple[float, ...] = (0.10, 0.00, 0.00, 0.00, -0.20, -0.24, 0.40)
    control_interaction: tuple[float, ...] = (0.75, 0.20, 0.15, 0.60, 1.05)
    rotation_interaction: tuple[float, ...] = (0.00, 1.10, 0.15, 0.00, 0.00)
    power_interaction: tuple[float, ...] = (0.00, 0.00, 0.15, 0.80, 1.25)
    threat_interaction: tuple[float, ...] = (0.20, 0.10, 0.00, 0.25, 0.50)
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
    style_strategy_scale: tuple[float, ...] = (0.75, 0.85, 1.0, 1.15, 1.25)
    setness_cap: int = 15
    settling_balls: int = 6
    setness_vector: tuple[float, ...] = (-0.12, 0.06, 0.04, 0.02, 0.12, 0.18, -0.28)
    attacking_setness: tuple[float, ...] = (0.5, 0.6, 0.8, 1.4, 1.7)
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


V2_0_RULES = Ruleset()
# Bound the reward of a sustained slog without imposing artificial run ceilings.
# Saved v2.0 matches retain their original distribution and replay sequence.
DEFAULT_RULES = replace(
    V2_0_RULES,
    version="v2.1",
    strategy_vectors=(
        *V2_0_RULES.strategy_vectors[:4],
        (0.75, -1.00, -0.55, -0.65, 0.60, 1.55, 1.65),
    ),
    power_interaction=(*V2_0_RULES.power_interaction[:4], 0.30),
    control_interaction=(*V2_0_RULES.control_interaction[:4], 0.50),
    attacking_setness=(*V2_0_RULES.attacking_setness[:4], 0.70),
)
RULESETS = MappingProxyType({r.version: r for r in (V2_0_RULES, DEFAULT_RULES)})
STRATEGY_LABELS = MappingProxyType(
    dict(
        zip(
            StrategyId,
            (
                "Preserve",
                "Rotate",
                "Balanced",
                "Attack",
                "All-out Attack",
            ),
            strict=True,
        )
    )
)


def phase_index(balls: int, rules: Ruleset = DEFAULT_RULES) -> int:
    return next((i for i, end in enumerate(rules.phase_ends) if balls < end), 2)
