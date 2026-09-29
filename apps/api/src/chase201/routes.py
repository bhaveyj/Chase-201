from datetime import UTC, timedelta

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select

from chase201 import services as svc
from chase201.auth import DB, MutationPrincipal, Principal
from chase201.models import Match, User, now
from chase201.schemas import (
    DraftView,
    EventView,
    HistoryView,
    LegacyStrategyDecision,
    MatchIn,
    MatchView,
    OrderIn,
    Revision,
    SavedMatchView,
    SelectionIn,
    StrategyDecision,
    V2EventView,
    V2StrategyDecision,
)
from chase201.timing import timed

router = APIRouter(prefix="/api/v1")


@router.post("/drafts", response_model=DraftView)
async def create_draft(
    body: Revision, db: DB, session: MutationPrincipal, idempotency_key: str = Header()
) -> dict:
    if session.user_id:
        await db.scalar(select(User).where(User.id == session.user_id).with_for_update())
    scope, payload = "drafts:create", body.model_dump()
    if result := await svc.replay(db, session, idempotency_key, scope, payload):
        return result
    with timed("draft_create"):
        draft = await svc.create_draft(db, session, body.expectedRevision)
    with timed("draft_view"):
        view = await svc.draft_view(db, draft)
    return svc.remember(
        db, session, idempotency_key, scope, payload, view
    )


@router.get("/drafts/{draft_id}", response_model=DraftView)
async def read_draft(draft_id: str, db: DB, session: Principal) -> dict:
    with timed("draft_lookup"):
        draft = await svc.get_draft(db, draft_id, session, lock=True)
    with timed("draft_view"):
        return await svc.draft_view(db, draft)


async def edit_draft(
    draft_id: str,
    action: str,
    body: Revision,
    key: str,
    db: DB,
    session: MutationPrincipal,
    slot_id: str | None = None,
) -> dict:
    with timed("draft_lock"):
        draft = await svc.get_draft(db, draft_id, session, lock=True)
    scope, payload = f"draft:{draft.id}:{action}:{slot_id or ''}", body.model_dump()
    if result := await svc.replay(db, session, key, scope, payload):
        return result
    svc.check_revision(draft, body.expectedRevision)
    if draft.status != "DRAFTING":
        raise HTTPException(409, "Confirmed teams cannot be changed")
    if isinstance(body, SelectionIn) and slot_id:
        with timed("selection_validation"):
            await svc.select_player(db, draft, slot_id, body.playerId)
    elif isinstance(body, OrderIn):
        await svc.validate_order(db, draft, body.playerIds)
        draft.batting_order = body.playerIds
    elif action == "confirm":
        await svc.confirm_team(db, draft)
    draft.revision += 1
    with timed("draft_write"):
        await db.flush()
    with timed("draft_view"):
        view = await svc.draft_view(db, draft)
    return svc.remember(db, session, key, scope, payload, view)


@router.put("/drafts/{draft_id}/selections/{slot_id}", response_model=DraftView)
async def select_player(
    draft_id: str,
    slot_id: str,
    body: SelectionIn,
    db: DB,
    session: MutationPrincipal,
    idempotency_key: str = Header(),
) -> dict:
    return await edit_draft(draft_id, "select", body, idempotency_key, db, session, slot_id)


@router.put("/drafts/{draft_id}/batting-order", response_model=DraftView)
async def batting_order(
    draft_id: str,
    body: OrderIn,
    db: DB,
    session: MutationPrincipal,
    idempotency_key: str = Header(),
) -> dict:
    return await edit_draft(draft_id, "order", body, idempotency_key, db, session)


@router.post("/drafts/{draft_id}/confirm", response_model=DraftView)
async def confirm(
    draft_id: str,
    body: Revision,
    db: DB,
    session: MutationPrincipal,
    idempotency_key: str = Header(),
) -> dict:
    return await edit_draft(draft_id, "confirm", body, idempotency_key, db, session)


@router.post("/matches", response_model=MatchView | SavedMatchView)
async def create_match(
    body: MatchIn, db: DB, session: MutationPrincipal, idempotency_key: str = Header()
) -> dict:
    draft = await svc.get_draft(db, body.draftId, session, lock=True)
    scope, payload = f"draft:{draft.id}:match", body.model_dump()
    if result := await svc.replay(db, session, idempotency_key, scope, payload):
        return result
    svc.check_revision(draft, body.expectedRevision)
    match = await svc.create_match(db, draft, session)
    return svc.remember(
        db, session, idempotency_key, scope, payload, await svc.match_view(db, match)
    )


@router.get("/matches/{match_id}", response_model=MatchView | SavedMatchView)
async def read_match(match_id: str, db: DB, session: Principal) -> dict:
    return await svc.match_view(db, await svc.get_match(db, match_id, session, lock=True))


@router.post("/matches/{match_id}/decisions", response_model=MatchView | SavedMatchView)
async def decide(
    match_id: str,
    body: StrategyDecision | V2StrategyDecision | LegacyStrategyDecision,
    db: DB,
    session: MutationPrincipal,
    idempotency_key: str = Header(),
) -> dict:
    with timed("match_lock"):
        match = await svc.get_match(db, match_id, session, lock=True)
    scope, payload = f"match:{match.id}:decision", body.model_dump()
    if result := await svc.replay(db, session, idempotency_key, scope, payload):
        return result
    svc.check_revision(match, body.expectedRevision)
    people = await svc.load_match_people(db, match)
    with timed("simulation_and_write"):
        new_events = await svc.advance_match(db, match, body, people)
    with timed("view"):
        view = await svc.match_view(db, match, people, events=new_events)
    return svc.remember(
        db, session, idempotency_key, scope, payload, view
    )


@router.get("/matches/{match_id}/events", response_model=list[EventView | V2EventView])
async def events(
    match_id: str, db: DB, session: Principal, after_revision: int = Query(0, ge=0)
) -> list[dict]:
    await svc.get_match(db, match_id, session, lock=True)
    return await svc.events_view(db, match_id, after_revision)


@router.get("/me/matches", response_model=HistoryView)
async def history(
    db: DB, session: Principal, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)
) -> dict:
    owner = Match.user_id == session.user_id if session.user_id else Match.session_id == session.id
    if session.kind == "guest":
        owner = owner & (Match.created_at > now() - timedelta(days=30))
    rows = list(
        (
            await db.scalars(
                select(Match)
                .where(owner)
                .order_by(Match.created_at.desc(), Match.id)
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
    )
    return {
        "matches": [
            {
                "id": m.id,
                "status": m.state["status"],
                "runs": m.state["runs"],
                "wickets": m.state["wickets"],
                "balls": m.state["balls"],
                "createdAt": m.created_at.replace(tzinfo=UTC).isoformat(),
            }
            for m in rows[:limit]
        ],
        "nextOffset": offset + limit if len(rows) > limit else None,
    }
