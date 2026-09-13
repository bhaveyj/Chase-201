"""Stable v2 attribute backfill for legacy catalogs; never changes v1 ratings."""

import hashlib


def expanded_profile(player_id: str, batting: float, bowling: float) -> dict:
    digest = hashlib.sha256(player_id.encode()).digest()

    def rating(base: float, index: int) -> float:
        return round(max(1, min(100, base + digest[index] % 17 - 8)), 2)

    return {
        "batting_control": rating(batting, 0),
        "batting_rotation": rating(batting, 1),
        "batting_power": rating(batting, 2),
        "bowling_control": rating(bowling, 3),
        "bowling_threat": rating(bowling, 4),
        "bowling_style": "PACE" if digest[5] % 2 == 0 else "SPIN",
    }
