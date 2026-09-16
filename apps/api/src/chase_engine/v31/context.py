"""Derive context from observable scorecard state and player profiles."""

from chase_engine.v31.rules import DEFAULT_RULES, Ruleset, phase_index
from chase_engine.v31.types import DerivedContext, GameState, Outcome, PlayerProfile


def clamp(value: float, low: float = 0, high: float = 1) -> float:
    return max(low, min(high, value))


def setness_label(balls: int, rules: Ruleset = DEFAULT_RULES) -> str:
    return (
        "New"
        if balls < rules.settling_balls
        else "Settling"
        if balls < rules.setness_cap
        else "Set"
    )


def derive_context(
    state: GameState,
    batter: PlayerProfile,
    partner: PlayerProfile,
    bowler: PlayerProfile,
    rules: Ruleset = DEFAULT_RULES,
) -> DerivedContext:
    remaining = max(0, rules.legal_balls - state.balls)
    needed = max(0, rules.target - state.runs)
    required = needed * 6 / max(1, remaining)

    def quality(p: PlayerProfile) -> float:
        return p.batting

    batting_quality = (
        quality(batter) * (1 - rules.sustainable_partner_weight)
        + quality(partner) * rules.sustainable_partner_weight
    )
    sustainable = rules.sustainable_base_rate + batting_quality * rules.sustainable_attribute_rate
    chase = clamp(
        (required / sustainable - rules.chase_pressure_start_ratio) / rules.chase_pressure_span
    )
    consecutive = 0
    for outcome in reversed(state.recent_outcomes):
        if outcome != Outcome.DOT:
            break
        consecutive += 1
    recent = clamp(
        consecutive / 6 * rules.consecutive_dot_weight
        + state.recent_outcomes.count(Outcome.DOT) / 6 * rules.recent_dot_weight
        + (Outcome.WICKET in state.recent_outcomes) * rules.recent_wicket_pressure
    )
    pressure = clamp(
        chase
        + recent * rules.recent_dot_weight
        + state.wickets / rules.wicket_limit * rules.tail_pressure_scale * chase
        + clamp(1 - remaining / rules.closing_pressure_balls) * rules.closing_pressure_scale * chase
    )
    band = ("Low", "Building", "High", "Extreme")[
        sum(pressure >= x for x in rules.pressure_thresholds)
    ]
    edge = quality(batter) - (bowler.bowling_control + bowler.bowling_threat) / 2
    matchup = (
        "Batter advantage"
        if edge > rules.matchup_edge
        else "Testing spell"
        if edge < -rules.matchup_edge
        else "Even contest"
    )
    return DerivedContext(
        needed,
        remaining,
        state.runs * 6 / max(1, state.balls),
        required,
        ("POWERPLAY", "MIDDLE", "DEATH")[phase_index(state.balls, rules)],
        pressure,
        band,
        rules.wicket_limit - state.wickets,
        clamp(state.batting[state.striker].balls / rules.setness_cap),
        recent,
        min(
            clamp(state.partnership_balls / rules.partnership_ball_cap),
            clamp(state.partnership_runs / rules.partnership_run_cap),
        ),
        matchup,
    )


def context_summary(
    state: GameState, context: DerivedContext, rules: Ruleset = DEFAULT_RULES
) -> dict:
    """Allowlist for browser/persisted feedback: no coefficients or hidden ratings."""
    return {
        "pressure": context.pressure_band,
        "phase": context.phase,
        "strikerSetness": setness_label(state.batting[state.striker].balls, rules),
        "nonStrikerSetness": setness_label(state.batting[state.non_striker].balls, rules),
        "matchup": context.batter_bowler_matchup,
    }
