from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from chase_engine.types import Outcome, StrategyId
from chase_engine.v2.types import StrategyId as V2StrategyId


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Revision(APIModel):
    expectedRevision: int = Field(ge=0)


class SelectionIn(Revision):
    playerId: str = Field(min_length=1, max_length=100)


class OrderIn(Revision):
    playerIds: list[str] = Field(min_length=11, max_length=11)


class MatchIn(Revision):
    draftId: str


class StrategyDecision(Revision):
    strategy: StrategyId


class V2StrategyDecision(Revision):
    strategy: V2StrategyId


class LegacyStrategyDecision(Revision):
    intent: Literal["DEFEND", "ROTATE", "ATTACK"]
    riskFocus: Literal["PROTECT_WICKETS", "BALANCED", "MAXIMIZE_RUNS"]


class PlayerSummary(APIModel):
    id: str
    name: str
    role: Literal["BATTER", "WICKETKEEPER", "ALL_ROUNDER", "BOWLER"]
    overallRating: int
    battingRating: float | None = Field(default=None, ge=1, le=100, exclude_if=lambda v: v is None)
    battingPlaystyle: Literal["Anchor", "Rotator", "Hitter"] | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    battingControl: float | None = Field(default=None, ge=1, le=100, exclude_if=lambda v: v is None)
    battingRotation: float | None = Field(
        default=None, ge=1, le=100, exclude_if=lambda v: v is None
    )
    battingPower: float | None = Field(default=None, ge=1, le=100, exclude_if=lambda v: v is None)


class SessionView(APIModel):
    kind: Literal["anonymous", "guest", "user"]
    csrfToken: str
    revision: int
    expiresAt: str | None = None
    userName: str | None = None
    googleEnabled: bool
    activeDraftId: str | None = None
    activeMatchId: str | None = None


class SlotView(APIModel):
    id: str
    role: str
    position: int
    options: list[PlayerSummary]
    selectedPlayerId: str | None
    ratingLabel: str = "Open selection"
    minimumRating: int = 1
    maximumRating: int = 100


class DraftView(APIModel):
    id: str
    revision: int
    status: str
    catalogVersion: str
    selectionRuleset: str = "open-v1"
    slots: list[SlotView]
    battingOrder: list[str]
    matchId: str | None = None


class BatterView(APIModel):
    player_id: str
    runs: int
    balls: int
    fours: int
    sixes: int
    out: bool


class BowlerView(APIModel):
    player_id: str
    runs: int
    balls: int
    wickets: int


class StateView(APIModel):
    runs: int
    wickets: int
    balls: int
    wides: int
    no_balls: int
    striker: int
    non_striker: int
    next_batter: int
    free_hit: bool
    status: str
    batting: list[BatterView]
    bowling: list[BowlerView]
    over_bowlers: list[str]
    recent_outcomes: list[Outcome] = Field(default_factory=list)
    partnership_runs: int = 0
    partnership_balls: int = 0
    last_wicket_ball: int | None = None


class ThreeModeStateView(StateView):
    approaches_used: list[StrategyId] = Field(default_factory=list)


class ContextSummary(APIModel):
    pressure: Literal["Low", "Building", "High", "Extreme"]
    phase: Literal["POWERPLAY", "MIDDLE", "DEATH"]
    strikerSetness: Literal["New", "Settling", "Set"]
    nonStrikerSetness: Literal["New", "Settling", "Set"]
    matchup: str


Band = Literal["Very low", "Low", "Moderate", "High", "Very high"]


class AssessmentBands(APIModel):
    scoring: Band
    wicketRisk: Band | Literal["None (free hit)"]
    boundary: Band


class AssessmentView(AssessmentBands):
    strategy: StrategyId
    # Absent only in historical idempotency receipts created before this field existed.
    wicketProbability: float | None = Field(default=None, ge=0, le=1)


class V2AssessmentView(AssessmentBands):
    strategy: V2StrategyId


class UpcomingBowler(PlayerSummary):
    style: Literal["PACE", "SPIN"]
    over: int


class DeliveryView(APIModel):
    outcome: Outcome
    fromBall: int
    toBall: int
    runs: int
    wickets: int
    batterId: str
    bowlerId: str
    freeHit: bool


class EventData(APIModel):
    revision: int
    sequence: int
    kind: str
    label: str
    fromBall: int
    toBall: int
    runs: int
    wickets: int
    score: int
    totalWickets: int
    freeHit: bool
    batterId: str | None = None
    bowlerId: str | None = None
    interruption: (
        Literal["WINDOW_END", "WICKET", "NO_BALL", "FREE_HIT", "INNINGS_COMPLETE"] | None
    ) = None
    deliveries: list[DeliveryView] = Field(default_factory=list)
    contextBefore: ContextSummary | None = None
    contextAfter: ContextSummary | None = None


class EventView(EventData):
    strategy: StrategyId | None = None


class V2EventView(EventData):
    strategy: V2StrategyId | None = None


class MatchData(APIModel):
    id: str
    revision: int
    target: int
    decisionWindow: int
    state: StateView
    team: list[PlayerSummary]
    opponent: list[PlayerSummary]
    createdAt: str
    context: ContextSummary | None = None
    upcomingBowlers: list[UpcomingBowler] = Field(default_factory=list)


class MatchView(MatchData):
    rulesetVersion: Literal["v3.0", "v3.1", "v3.2", "v3.3", "v3.4"]
    state: ThreeModeStateView
    events: list[EventView]
    strategyAssessments: list[AssessmentView] = Field(default_factory=list)


class SavedMatchView(MatchData):
    rulesetVersion: Literal["v1.0", "v2.0", "v2.1"]
    events: list[V2EventView]
    strategyAssessments: list[V2AssessmentView] = Field(default_factory=list)


class HistoryEntry(APIModel):
    id: str
    status: str
    runs: int
    wickets: int
    balls: int
    createdAt: str


class HistoryView(APIModel):
    matches: list[HistoryEntry]
    nextOffset: int | None


class ErrorView(APIModel):
    detail: str | list[dict[str, Any]]
