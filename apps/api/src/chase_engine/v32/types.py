"""Persisted approach history extends the unchanged cricket scorecard."""

from dataclasses import dataclass, field

from chase_engine.v31.types import Batting, Bowling
from chase_engine.v31.types import GameState as PreviousGameState


@dataclass
class GameState(PreviousGameState):
    # Only approaches actually used on legal deliveries count; UI selections and
    # extras cannot unlock a win. Stored with the authoritative match snapshot.
    approaches_used: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "GameState":
        return cls(
            **{
                **raw,
                "batting": [Batting(**b) for b in raw["batting"]],
                "bowling": [Bowling(**b) for b in raw["bowling"]],
            }
        )
