from datetime import timedelta

from sqlalchemy import select
from test_api import guest, match, mutate

from chase201.cleanup import cleanup
from chase201.models import Draft, Match, Session, now


async def test_guest_creation_retry_after_cookie_received(client):
    bootstrap = (await client.get("/api/v1/session")).json()
    client.headers["X-CSRF-Token"] = bootstrap["csrfToken"]
    first = await mutate(
        client, "POST", "/api/v1/guest-sessions", {"expectedRevision": 0}, "same-bootstrap-key"
    )
    second = await mutate(
        client, "POST", "/api/v1/guest-sessions", {"expectedRevision": 0}, "same-bootstrap-key"
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


async def test_game_retention_is_independent_of_session_activity(client, database):
    m = await match(client)
    s = (await client.get("/api/v1/session")).json()
    assert s["activeMatchId"] == m["id"]
    async with database() as db, db.begin():
        row = await db.get(Match, m["id"])
        row.created_at = now() - timedelta(days=31)
        draft = await db.scalar(select(Draft))
        draft.created_at = now() - timedelta(days=32)
        session = await db.scalar(select(Session))
        session.expires_at = now() + timedelta(days=29)
    assert (await client.get(f"/api/v1/matches/{m['id']}")).status_code == 404
    async with database() as db, db.begin():
        assert await cleanup(db) == 0  # The active session survives; old game data does not.
    async with database() as db:
        assert await db.get(Match, m["id"]) is None
        assert await db.scalar(select(Draft)) is None
        assert await db.scalar(select(Session)) is not None


async def test_new_game_extends_guest_access_for_full_retention_window(client, database):
    s = await guest(client)
    async with database() as db, db.begin():
        session = await db.scalar(select(Session))
        session.expires_at = now() + timedelta(hours=1)
    response = await mutate(client, "POST", "/api/v1/drafts", {"expectedRevision": s["revision"]})
    assert response.status_code == 200
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    async with database() as db:
        session = await db.scalar(select(Session))
        from chase201.auth import future

        assert future(session.expires_at - timedelta(days=29))
