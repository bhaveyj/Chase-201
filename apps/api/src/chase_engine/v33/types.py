"""Legal-delivery history persists field adaptation across decisions/reloads."""

from dataclasses import dataclass, field

from chase_engine.v31.types import Batting, Bowling
from chase_engine.v32.types import GameState as PreviousGameState


@dataclass
class GameState(PreviousGameState):
    recent_approaches: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "GameState":
        return cls(
            **{
                **raw,
                "batting": [Batting(**b) for b in raw["batting"]],
                "bowling": [Bowling(**b) for b in raw["bowling"]],
            }
        )
