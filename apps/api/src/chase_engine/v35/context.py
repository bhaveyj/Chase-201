"""Batting ratings affect neither pressure nor matchup feedback in v3.5."""

from dataclasses import replace

from chase_engine.v31.context import context_summary as context_summary
from chase_engine.v31.context import derive_context as previous_context
from chase_engine.v31.types import DerivedContext, PlayerProfile
from chase_engine.v33.types import GameState
from chase_engine.v35.rules import DEFAULT_RULES, Ruleset


def neutral_batter(player: PlayerProfile) -> PlayerProfile:
    return replace(player, batting=75)


def derive_context(
    state: GameState,
    batter: PlayerProfile,
    partner: PlayerProfile,
    bowler: PlayerProfile,
    rules: Ruleset = DEFAULT_RULES,
) -> DerivedContext:
    return previous_context(state, neutral_batter(batter), neutral_batter(partner), bowler, rules)
