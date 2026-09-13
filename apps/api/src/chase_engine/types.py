"""Framework-free domain data. Inputs are frozen; mutable snapshots are copied."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class StrategyId(StrEnum):
    PRESERVE = "PRESERVE"
    ROTATE = "ROTATE"
    BALANCED = "BALANCED"
    ATTACK = "ATTACK"
    ALL_OUT = "ALL_OUT"


class Outcome(StrEnum):
    DOT = "DOT"
    ONE = "ONE"
    TWO = "TWO"
    THREE = "THREE"
    FOUR = "FOUR"
    SIX = "SIX"
    WICKET = "WICKET"
    WIDE = "WIDE"
    NO_BALL = "NO_BALL"


class BowlingStyle(StrEnum):
    PACE = "PACE"
    SPIN = "SPIN"


class RandomSource(Protocol):
    def random(self) -> float: ...


@dataclass(frozen=True)
class PlayerProfile:
    id: str
    role: str
    overall: int = 75
    batting_control: float = 75
    batting_rotation: float = 75
    batting_power: float = 75
    bowling_control: float = 75
    bowling_threat: float = 75
    bowling_style: BowlingStyle = BowlingStyle.PACE


@dataclass
class Batting:
    player_id: str
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    out: bool = False


@dataclass
class Bowling:
    player_id: str
    runs: int = 0
    balls: int = 0
    wickets: int = 0


@dataclass
class GameState:
    runs: int = 0
    wickets: int = 0
    balls: int = 0
    wides: int = 0
    no_balls: int = 0
    striker: int = 0
    non_striker: int = 1
    next_batter: int = 2
    free_hit: bool = False
    status: str = "LIVE"
    batting: list[Batting] = field(default_factory=list)
    bowling: list[Bowling] = field(default_factory=list)
    over_bowlers: list[str] = field(default_factory=list)
    recent_outcomes: list[str] = field(default_factory=list)
    partnership_runs: int = 0
    partnership_balls: int = 0
    last_wicket_ball: int | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> "GameState":
        return cls(
            **{
                **raw,
                "batting": [Batting(**b) for b in raw["batting"]],
                "bowling": [Bowling(**b) for b in raw["bowling"]],
            }
        )


@dataclass(frozen=True)
class DerivedContext:
    runs_required: int
    balls_remaining: int
    current_rate: float
    required_rate: float
    phase: str
    pressure: float
    pressure_band: str
    wickets_in_hand: int
    striker_setness: float
    recent_pressure: float
    partnership_stability: float
    batter_bowler_matchup: str


@dataclass(frozen=True)
class DecisionWindow:
    max_legal_balls: int
    presentation_granularity: str
    stop_on_wicket: bool = True
    stop_on_no_ball: bool = True


@dataclass(frozen=True)
class OutcomeDistribution:
    # DOT, ONE, TWO, THREE, FOUR, SIX, WICKET; then legal, wide, no-ball.
    legal: tuple[float, ...]
    legality: tuple[float, float, float]
    expected_runs: float
    wicket_probability: float
    boundary_probability: float

    def probability(self, outcome: Outcome) -> float:
        if outcome == Outcome.WIDE:
            return self.legality[1]
        if outcome == Outcome.NO_BALL:
            return self.legality[2]
        return self.legality[0] * self.legal[list(Outcome).index(outcome)]


@dataclass(frozen=True)
class StrategyAssessment:
    strategy_id: StrategyId
    scoring_band: str
    wicket_risk_band: str
    boundary_band: str


@dataclass
class Transition:
    state: GameState
    events: list[dict]
