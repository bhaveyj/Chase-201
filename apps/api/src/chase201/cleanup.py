"""Run hourly as a Railway cron job. Claiming and expiry lock the same guest row."""

import asyncio
from datetime import UTC, timedelta

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from chase201.models import Draft, Idempotency, Match, OAuthAttempt, Session, Team, now


async def prune_guest(db: AsyncSession, session: Session, expired: bool = False) -> None:
    """Retention is per game, even while an active guest renews their session cookie."""
    cutoff = now() if expired else now() - timedelta(days=30)
    matches = (
        await db.scalars(
            select(Match).where(
                Match.session_id == session.id, Match.user_id.is_(None), Match.created_at <= cutoff
            )
        )
    ).all()
    for match in matches:
        await db.execute(
            delete(Idempotency).where(
                Idempotency.actor == f"guest:{session.id}",
                Idempotency.scope.like(f"match:{match.id}:%"),
            )
        )
        await db.delete(match)
    await db.flush()
    # Preserve a confirmed draft/team while a younger match still needs its XI.
    has_match = exists(
        select(Match.id).join(Team, Team.id == Match.team_id).where(Team.draft_id == Draft.id)
    )
    drafts = (
        await db.scalars(
            select(Draft).where(
                Draft.session_id == session.id,
                Draft.user_id.is_(None),
                Draft.created_at <= cutoff,
                ~has_match,
            )
        )
    ).all()
    for draft in drafts:
        await db.execute(
            delete(Idempotency).where(
                Idempotency.actor == f"guest:{session.id}",
                Idempotency.scope.like(f"draft:{draft.id}:%"),
            )
        )
        await db.delete(draft)


async def cleanup(db: AsyncSession) -> int:
    cutoff = now() - timedelta(days=30)
    expired = (
        await db.scalars(
            select(Session)
            .where(
                or_(
                    Session.expires_at <= now(),
                    Session.id.in_(
                        select(Match.session_id).where(
                            Match.user_id.is_(None), Match.created_at <= cutoff
                        )
                    ),
                    Session.id.in_(
                        select(Draft.session_id).where(
                            Draft.user_id.is_(None), Draft.created_at <= cutoff
                        )
                    ),
                )
            )
            .with_for_update(skip_locked=True)
        )
    ).all()
    removed = 0
    for session in expired:
        is_expired = session.expires_at.replace(tzinfo=UTC) <= now()
        await prune_guest(db, session, expired=is_expired)
        if is_expired:
            await db.execute(delete(Idempotency).where(Idempotency.actor == f"guest:{session.id}"))
            await db.delete(session)
            removed += 1
    await db.execute(delete(OAuthAttempt).where(OAuthAttempt.expires_at <= now()))
    await db.execute(delete(Idempotency).where(Idempotency.created_at < now() - timedelta(days=30)))
    return removed


async def main() -> None:
    from chase201.db import SessionFactory

    async with SessionFactory() as db, db.begin():
        print(f"Expired sessions removed: {await cleanup(db)}")


if __name__ == "__main__":
    asyncio.run(main())
