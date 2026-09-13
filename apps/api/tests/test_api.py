import asyncio
import os
import uuid
from collections import Counter
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from chase201 import auth
from chase201.catalog import COMPOSITION
from chase201.cleanup import cleanup
from chase201.config import get_settings
from chase201.main import app
from chase201.models import BattingPerformance, Decision, Draft, Match, MatchEvent, Session, now


async def guest(client):
    s = (await client.get("/api/v1/session")).json()
    r = await client.post(
        "/api/v1/guest-sessions",
        json={"expectedRevision": 0},
        headers={"X-CSRF-Token": s["csrfToken"], "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrfToken"]
    return r.json()


async def mutate(client, method, url, body, key=None):
    return await client.request(
        method, url, json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())}
    )


async def draft(client):
    s = await guest(client)
    r = await mutate(client, "POST", "/api/v1/drafts", {"expectedRevision": s["revision"]})
    assert r.status_code == 200, r.text
    return r.json()


async def filled_draft(client):
    d = await draft(client)
    for slot in d["slots"]:
        r = await mutate(
            client,
            "PUT",
            f"/api/v1/drafts/{d['id']}/selections/{slot['id']}",
            {"expectedRevision": d["revision"], "playerId": slot["options"][0]["id"]},
        )
        assert r.status_code == 200, r.text
        d = r.json()
    return d


async def match(client):
    d = await filled_draft(client)
    r = await mutate(
        client,
        "PUT",
        f"/api/v1/drafts/{d['id']}/batting-order",
        {
            "expectedRevision": d["revision"],
            "playerIds": [s["selectedPlayerId"] for s in d["slots"]],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    r = await mutate(
        client, "POST", f"/api/v1/drafts/{d['id']}/confirm", {"expectedRevision": d["revision"]}
    )
    assert r.status_code == 200, r.text
    d = r.json()
    r = await mutate(
        client, "POST", "/api/v1/matches", {"draftId": d["id"], "expectedRevision": d["revision"]}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_bootstrap_csrf_origin_and_ownership(client):
    assert (
        await client.post("/api/v1/guest-sessions", json={"expectedRevision": 0})
    ).status_code == 403
    d = await draft(client)
    assert all(len(s["options"]) == 5 for s in d["slots"])
    assert Counter(s["role"] for s in d["slots"]) == COMPOSITION
    assert all(
        set(p) == {"id", "name", "role", "overallRating"} for s in d["slots"] for p in s["options"]
    )
    assert len({p["id"] for s in d["slots"] for p in s["options"]}) == 55
    payload = {"expectedRevision": 0, "playerId": d["slots"][0]["options"][0]["id"]}
    url = f"/api/v1/drafts/{d['id']}/selections/{d['slots'][0]['id']}"
    assert (
        await client.put(
            url, json=payload, headers={"X-CSRF-Token": "wrong", "Idempotency-Key": "test-key"}
        )
    ).status_code == 403
    assert (
        await client.put(
            url,
            json=payload,
            headers={"Origin": "https://evil.test", "Idempotency-Key": "test-key"},
        )
    ).status_code == 403
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as other:
        await guest(other)
        assert (await other.get(f"/api/v1/drafts/{d['id']}")).status_code == 404
        assert (await mutate(other, "PUT", url, payload)).status_code == 404
    assert (await client.get("/api/v1/me/matches")).status_code == 401


async def test_offer_role_order_and_revision_validation(client):
    d = await draft(client)
    slot = d["slots"][0]
    path = f"/api/v1/drafts/{d['id']}/selections/{slot['id']}"
    for wrong in [d["slots"][1]["options"][0]["id"], d["slots"][-1]["options"][0]["id"], "unknown"]:
        assert (
            await mutate(client, "PUT", path, {"expectedRevision": 0, "playerId": wrong})
        ).status_code == 422
    key = str(uuid.uuid4())
    body = {"expectedRevision": 0, "playerId": slot["options"][0]["id"]}
    first = await mutate(client, "PUT", path, body, key)
    assert first.status_code == 200
    assert (await mutate(client, "PUT", path, body, key)).json() == first.json()
    assert (await mutate(client, "PUT", path, body)).status_code == 409
    assert (
        await mutate(client, "PUT", path, {**body, "playerId": slot["options"][1]["id"]}, key)
    ).status_code == 409
    assert (
        await mutate(client, "POST", f"/api/v1/drafts/{d['id']}/confirm", {"expectedRevision": 1})
    ).status_code == 422
    assert (
        await mutate(
            client,
            "PUT",
            f"/api/v1/drafts/{d['id']}/batting-order",
            {"expectedRevision": 1, "playerIds": [body["playerId"]] * 11},
        )
    ).status_code == 422


async def test_complete_guest_chase_idempotency_and_scorecards(client, database):
    m = await match(client)
    match_id = m["id"]
    assert m["rulesetVersion"] == "v2.1" and m["decisionWindow"] == 12
    assert len(m["strategyAssessments"]) == 5 and len(m["upcomingBowlers"]) == 2
    assert m["context"]["strikerSetness"] == "New"
    assert "seed" not in m and "batting" not in m["team"][0]
    path = f"/api/v1/matches/{match_id}/decisions"
    old = {"expectedRevision": 0, "strategy": "BALANCED"}
    first_key = str(uuid.uuid4())
    first = await mutate(client, "POST", path, old, first_key)
    assert first.status_code == 200, first.text
    assert (await mutate(client, "POST", path, old, first_key)).json() == first.json()
    assert (await mutate(client, "POST", path, old)).status_code == 409
    m = first.json()
    assert m["events"][0]["strategy"] == "BALANCED"
    assert m["events"][0]["contextBefore"] is not None
    assert m["events"][0]["deliveries"]
    async with database() as db:
        decision = await db.get(Decision, (match_id, 1))
        assert decision.strategy == "BALANCED" and decision.intent is None
        assert decision.context_summary == m["events"][0]["contextBefore"]
    for hidden in (
        "batting_control",
        "bowling_threat",
        "expected_runs",
        "wicket_probability",
        '"seed"',
    ):
        assert hidden not in first.text
    for _ in range(90):
        if m["state"]["status"] != "LIVE":
            break
        r = await mutate(
            client,
            "POST",
            path,
            {"expectedRevision": m["revision"], "strategy": "BALANCED"},
        )
        assert r.status_code == 200, r.text
        m = r.json()
    assert m["state"]["status"] in {"WON", "TIED", "LOST"}
    assert (
        await mutate(client, "POST", path, {**old, "expectedRevision": m["revision"]})
    ).status_code == 409
    assert (await client.get(f"/api/v1/matches/{match_id}")).json() == m
    assert (await mutate(client, "POST", path, old, first_key)).json() == first.json()
    events = (await client.get(f"/api/v1/matches/{match_id}/events?after_revision=1")).json()
    assert all(e["revision"] > 1 for e in events)
    async with database() as db:
        total = await db.scalar(
            select(func.sum(BattingPerformance.runs)).where(BattingPerformance.match_id == match_id)
        )
        assert total + m["state"]["wides"] + m["state"]["no_balls"] == m["state"]["runs"]
        assert (
            await db.scalar(
                select(func.count()).select_from(MatchEvent).where(MatchEvent.match_id == match_id)
            )
            == m["revision"]
        )


async def test_confirmed_team_immutable_and_one_match_per_draft(client, database):
    m = await match(client)
    async with database() as db:
        d = await db.scalar(select(Draft))
        draft_id = d.id
    d = (await client.get(f"/api/v1/drafts/{draft_id}")).json()
    assert d["matchId"] == m["id"]
    assert (
        await mutate(
            client,
            "PUT",
            f"/api/v1/drafts/{draft_id}/selections/{d['slots'][0]['id']}",
            {"expectedRevision": d["revision"], "playerId": d["slots"][0]["options"][1]["id"]},
        )
    ).status_code == 409
    assert (
        await mutate(
            client,
            "POST",
            "/api/v1/matches",
            {"expectedRevision": d["revision"], "draftId": draft_id},
        )
    ).status_code == 409


async def test_google_state_claiming_and_authenticated_ownership(client, database, monkeypatch):
    m = await match(client)
    guest_cookie = client.cookies.get(auth.COOKIE)
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")

    async def exchange(code, attempt):
        assert code == "test-code" and attempt.nonce and len(attempt.verifier) >= 43
        return {"sub": "google-test-user", "name": "Test Captain"}

    monkeypatch.setattr(auth, "exchange_google", exchange)
    start = await client.get("/api/v1/auth/google/start")
    args = parse_qs(urlparse(start.headers["location"]).query)
    assert args["code_challenge_method"] == ["S256"] and args["nonce"]
    state = args["state"][0]
    assert (
        await client.get("/api/v1/auth/google/callback?state=bad&code=test-code")
    ).status_code == 400
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as outsider:
        assert (
            await outsider.get(f"/api/v1/auth/google/callback?state={state}&code=test-code")
        ).status_code == 400
    callback = await client.get(f"/api/v1/auth/google/callback?state={state}&code=test-code")
    assert callback.status_code == 302 and callback.headers["location"].endswith("/history")
    assert (
        await client.get(f"/api/v1/auth/google/callback?state={state}&code=test-code")
    ).status_code == 400
    s = (await client.get("/api/v1/session")).json()
    assert s["kind"] == "user" and s["userName"] == "Test Captain"
    assert client.cookies.get(auth.COOKIE) != guest_cookie
    assert (await client.get("/api/v1/me/matches")).json()["matches"][0]["id"] == m["id"]
    client.headers["X-CSRF-Token"] = s["csrfToken"]
    assert (
        await mutate(
            client,
            "POST",
            f"/api/v1/matches/{m['id']}/decisions",
            {"expectedRevision": 0, "strategy": "PRESERVE"},
        )
    ).status_code == 200
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={auth.COOKIE: guest_cookie},
    ) as old_guest:
        assert (await old_guest.get(f"/api/v1/matches/{m['id']}")).status_code == 401
    async with database() as db, db.begin():
        expired = (await db.scalars(select(Session).where(Session.kind == "guest"))).all()
        for item in expired:
            item.expires_at = now() - timedelta(seconds=1)
    async with database() as db, db.begin():
        await cleanup(db)
    assert (await client.get(f"/api/v1/matches/{m['id']}")).status_code == 200


async def test_expiry_removes_guest_game_data(client, database):
    m = await match(client)
    async with database() as db, db.begin():
        session = await db.scalar(select(Session).where(Session.kind == "guest"))
        session.expires_at = now() - timedelta(seconds=1)
    assert (await client.get(f"/api/v1/matches/{m['id']}")).status_code == 401
    async with database() as db, db.begin():
        assert await cleanup(db) == 1
    async with database() as db:
        assert await db.scalar(select(func.count()).select_from(Match)) == 0
        assert await db.scalar(select(func.count()).select_from(Draft)) == 0
        assert await db.scalar(select(func.count()).select_from(MatchEvent)) == 0


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL required for row locks",
)
async def test_concurrent_decisions_and_duplicate_retries(client):
    m = await match(client)
    path = f"/api/v1/matches/{m['id']}/decisions"
    body = {"expectedRevision": 0, "strategy": "BALANCED"}
    first, second = await asyncio.gather(
        mutate(client, "POST", path, body), mutate(client, "POST", path, body)
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    key = str(uuid.uuid4())
    body["expectedRevision"] = 1
    first, second = await asyncio.gather(
        mutate(client, "POST", path, body, key), mutate(client, "POST", path, body, key)
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["revision"] == 2


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL required for row locks",
)
async def test_concurrent_same_user_different_sessions(client, database):
    from fastapi import Response

    from chase201.models import User

    m = await match(client)
    async with database() as db, db.begin():
        user = User(name="Shared captain")
        db.add(user)
        await db.flush()
        guest_session = await db.scalar(select(Session).where(Session.kind == "guest"))
        await auth.claim_guest(db, guest_session.id, user.id)
        cookies, csrf = [], []
        for _ in range(2):
            response = Response()
            session = await auth.new_session(db, response, user.id)
            cookies.append(response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1])
            csrf.append(session.csrf)
    async with (
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={auth.COOKIE: cookies[0]},
            headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf[0]},
        ) as one,
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={auth.COOKIE: cookies[1]},
            headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf[1]},
        ) as two,
    ):
        body = {"expectedRevision": 0, "strategy": "BALANCED"}
        path = f"/api/v1/matches/{m['id']}/decisions"
        responses = await asyncio.gather(
            mutate(one, "POST", path, body), mutate(two, "POST", path, body)
        )
        assert sorted(r.status_code for r in responses) == [200, 409]
        assert (await one.get("/api/v1/me/matches")).json()["matches"][0]["id"] == m["id"]
        retry_key = str(uuid.uuid4())
        responses = await asyncio.gather(
            mutate(one, "POST", "/api/v1/drafts", {"expectedRevision": 0}, retry_key),
            mutate(two, "POST", "/api/v1/drafts", {"expectedRevision": 0}, retry_key),
        )
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
