"""Versioned rating bands for disjoint draft offers and server-side validation."""

from collections import Counter
from dataclasses import dataclass
from random import Random
from typing import Protocol

LEGACY_SELECTION = "open-v1"
BALANCED_SELECTION = "balanced-v1"
SIMPLE_SELECTION = "simple-v1"
STAR_POSITIONS = (0, 6)  # One batter and one all-rounder; batting order stays editable.
ROLES = ["BATTER"] * 5 + ["WICKETKEEPER"] + ["ALL_ROUNDER"] * 2 + ["BOWLER"] * 3


@dataclass(frozen=True)
class RatingBand:
    label: str
    minimum: int
    maximum: int


def rating_band(position: int, ruleset: str = BALANCED_SELECTION) -> RatingBand:
    if ruleset == LEGACY_SELECTION:
        return RatingBand("Open selection", 1, 100)
    if ruleset not in {
        BALANCED_SELECTION,
        "tradeoffs-v1",
        SIMPLE_SELECTION,
    } or not 0 <= position < len(ROLES):
        raise ValueError("Unknown draft selection rules")
    return (
        RatingBand("Star player", 90, 92)
        if position in STAR_POSITIONS
        else RatingBand("Core player", 78, 85)
    )


class RatedPlayer(Protocol):
    id: str
    role: str
    overall_rating: int


def draft_offers[P: RatedPlayer](catalog: list[P], rng: Random) -> list[list[P]]:
    """Every position has five unique options, without blocking any future selection."""
    remaining = list(catalog)
    rng.shuffle(remaining)
    offers = []
    for position, role in enumerate(ROLES):
        band = rating_band(position)
        options = [
            p
            for p in remaining
            if p.role == role and band.minimum <= p.overall_rating <= band.maximum
        ][:5]
        if len(options) != 5:
            raise ValueError(
                f"Catalog needs five disjoint {role} offers rated {band.minimum}–{band.maximum} "
                f"for position {position + 1}"
            )
        offers.append(options)
        used = {p.id for p in options}
        remaining = [p for p in remaining if p.id not in used]
    return offers


def opponent_players[P: RatedPlayer](catalog: list[P], rng: Random) -> list[P]:
    """The same median-strength opposition used by games and balance checks."""
    opponent = []
    for role, count in Counter(ROLES).items():
        pool = [p for p in catalog if p.role == role]
        median = sorted(p.overall_rating for p in pool)[len(pool) // 2]
        rng.shuffle(pool)
        pool.sort(key=lambda p: abs(p.overall_rating - median))
        opponent.extend(rng.sample(pool[: max(count * 2, 5)], count))
    return opponent
