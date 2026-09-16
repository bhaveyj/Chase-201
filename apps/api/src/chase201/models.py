"""Relational aggregates; match snapshots and event payloads use portable JSON.

Catalog rows are immutable through the application; import never updates a version.
Session.kind distinguishes guest and authenticated sessions in one token namespace.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"
    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20), default="google")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("kind IN ('guest', 'user')"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    revision: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OAuthAttempt(Base):
    __tablename__ = "oauth_attempts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(100))
    verifier: Mapped[str] = mapped_column(String(150))
    guest_id: Mapped[str | None] = mapped_column(String(36))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(1000))
    license: Mapped[str] = mapped_column(String(1000))
    approved: Mapped[bool] = mapped_column(default=False)
    selection_ruleset: Mapped[str] = mapped_column(String(40), default="open-v1")
    offer_allocation: Mapped[list[list[str]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (CheckConstraint("overall_rating BETWEEN 1 AND 100"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalog_versions.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    overall_rating: Mapped[int]


class SimulationProfile(Base):
    __tablename__ = "simulation_profiles"
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    batting: Mapped[float]
    bowling: Mapped[float]
    batting_control: Mapped[float]
    batting_rotation: Mapped[float]
    batting_power: Mapped[float]
    bowling_control: Mapped[float]
    bowling_threat: Mapped[float]
    bowling_style: Mapped[str] = mapped_column(String(10))
    __table_args__ = (
        CheckConstraint("batting_control BETWEEN 1 AND 100", name="profile_batting_control"),
        CheckConstraint("batting_rotation BETWEEN 1 AND 100", name="profile_batting_rotation"),
        CheckConstraint("batting_power BETWEEN 1 AND 100", name="profile_batting_power"),
        CheckConstraint("bowling_control BETWEEN 1 AND 100", name="profile_bowling_control"),
        CheckConstraint("bowling_threat BETWEEN 1 AND 100", name="profile_bowling_threat"),
        CheckConstraint("bowling_style IN ('PACE', 'SPIN')", name="profile_bowling_style"),
    )


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalog_versions.id"))
    selection_ruleset: Mapped[str] = mapped_column(String(40), default="tradeoffs-v1")
    revision: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="DRAFTING")
    batting_order: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DraftSlot(Base):
    __tablename__ = "draft_slots"
    __table_args__ = (UniqueConstraint("draft_id", "position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    position: Mapped[int]


class DraftOffer(Base):
    __tablename__ = "draft_offers"
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("draft_slots.id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)


class Selection(Base):
    __tablename__ = "selections"
    __table_args__ = (UniqueConstraint("draft_id", "player_id"),)
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("draft_slots.id", ondelete="CASCADE"), primary_key=True
    )
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), unique=True)


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "position"),)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    position: Mapped[int]


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), unique=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    opponent: Mapped[list[str]] = mapped_column(JSON)
    seed: Mapped[str] = mapped_column(String(100))
    ruleset: Mapped[str] = mapped_column(String(40), default="v3.0")
    revision: Mapped[int] = mapped_column(default=0)
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Decision(Base):
    __tablename__ = "decisions"
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(primary_key=True)
    intent: Mapped[str | None] = mapped_column(String(20))
    risk_focus: Mapped[str | None] = mapped_column(String(30))
    strategy: Mapped[str | None] = mapped_column(String(20))
    context_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    __table_args__ = (
        CheckConstraint(
            "(strategy IS NULL AND intent IS NOT NULL AND risk_focus IS NOT NULL) OR "
            "(strategy IS NOT NULL AND strategy IN ('DEFENSIVE', 'AGGRESSIVE', 'PRESERVE', 'ROTATE', 'BALANCED', 'ATTACK', 'ALL_OUT') "
            "AND intent IS NULL AND risk_focus IS NULL)",
            name="decision_strategy_shape",
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MatchEvent(Base):
    __tablename__ = "match_events"
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(primary_key=True)
    sequence: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class BattingPerformance(Base):
    __tablename__ = "batting_performances"
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    runs: Mapped[int]
    balls: Mapped[int]
    fours: Mapped[int]
    sixes: Mapped[int]
    out: Mapped[bool]


class BowlingPerformance(Base):
    __tablename__ = "bowling_performances"
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    runs: Mapped[int]
    balls: Mapped[int]
    wickets: Mapped[int]


class Idempotency(Base):
    __tablename__ = "idempotency_keys"
    actor: Mapped[str] = mapped_column(String(80), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    scope: Mapped[str] = mapped_column(String(200), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
