import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from joserfc import jwt
from joserfc.jwk import KeySet, KeySetSerialization
from sqlalchemy import select, update
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from chase201.cleanup import prune_guest
from chase201.config import get_settings
from chase201.db import get_db
from chase201.models import Draft, Match, OAuthAttempt, OAuthIdentity, Session, User, now
from chase201.schemas import Revision, SessionView

router = APIRouter(prefix="/api/v1")
DB = Annotated[AsyncSession, Depends(get_db)]
COOKIE = "c201_session"
BOOTSTRAP = "c201_bootstrap"
OAUTH_COOKIE = "c201_oauth"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def future(value: datetime) -> bool:
    return value.replace(tzinfo=UTC) > now()


def set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="lax",
        path="/",
    )


def require_origin(request: Request) -> None:
    if request.headers.get("origin") not in get_settings().cors_origins:
        raise HTTPException(403, "Untrusted or missing request origin")


async def optional_session(request: Request, db: DB) -> Session | None:
    token = request.cookies.get(COOKIE, "")
    if not token:
        return None
    session = await db.scalar(select(Session).where(Session.token_hash == digest(token)))
    return session if session and future(session.expires_at) else None


async def require_session(session: Annotated[Session | None, Depends(optional_session)]) -> Session:
    if session is None:
        raise HTTPException(401, "Your session has expired. Start a new guest session.")
    return session


Principal = Annotated[Session, Depends(require_session)]


async def mutation_session(
    request: Request,
    response: Response,
    session: Principal,
    db: DB,
    x_csrf_token: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> Session:
    require_origin(request)
    if not x_csrf_token or not secrets.compare_digest(x_csrf_token, session.csrf):
        raise HTTPException(403, "Invalid CSRF token")
    if not idempotency_key or not 8 <= len(idempotency_key) <= 100:
        raise HTTPException(400, "An Idempotency-Key of 8–100 characters is required")
    locked = await db.scalar(
        select(Session)
        .where(Session.id == session.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        not locked
        or not future(locked.expires_at)
        or not secrets.compare_digest(locked.token_hash, digest(request.cookies.get(COOKIE, "")))
    ):
        raise HTTPException(401, "Session has expired or was claimed")
    if locked.kind == "guest":
        locked.expires_at = now() + timedelta(days=30)
        set_cookie(response, COOKIE, request.cookies[COOKIE], 30 * 86400)
    return locked


MutationPrincipal = Annotated[Session, Depends(mutation_session)]


async def session_view(session: Session, db: AsyncSession) -> dict[str, Any]:
    user = await db.get(User, session.user_id) if session.user_id else None
    active: dict[str, str | None] = {}
    aggregates: list[tuple[type[Draft] | type[Match], str]] = [
        (Draft, "activeDraftId"),
        (Match, "activeMatchId"),
    ]
    for entity, key in aggregates:
        owner = (
            entity.user_id == session.user_id
            if session.user_id
            else entity.session_id == session.id
        )
        status = (
            Draft.status == "DRAFTING"
            if entity is Draft
            else Match.state["status"].as_string() == "LIVE"
        )
        q = select(entity.id).where(owner, status).order_by(entity.created_at.desc()).limit(1)
        if session.kind == "guest":
            q = q.where(entity.created_at > now() - timedelta(days=30))
        active[key] = await db.scalar(q)
    return {
        **active,
        "kind": session.kind,
        "csrfToken": session.csrf,
        "revision": session.revision,
        "expiresAt": session.expires_at.replace(tzinfo=UTC).isoformat(),
        "userName": user.name if user else None,
        "googleEnabled": bool(get_settings().google_client_id),
    }


async def new_session(db: AsyncSession, response: Response, user_id: str | None = None) -> Session:
    token = secrets.token_urlsafe(32)
    days = 7 if user_id else 30
    session = Session(
        token_hash=digest(token),
        csrf=secrets.token_urlsafe(32),
        kind="user" if user_id else "guest",
        user_id=user_id,
        expires_at=now() + timedelta(days=days),
    )
    db.add(session)
    await db.flush()
    set_cookie(response, COOKIE, token, days * 86400)
    return session


@router.get("/session", response_model=SessionView)
async def get_session(
    response: Response, db: DB, session: Annotated[Session | None, Depends(optional_session)]
) -> dict:
    if session:
        return await session_view(session, db)
    token = secrets.token_urlsafe(32)
    signed = URLSafeTimedSerializer(get_settings().secret_key, salt="bootstrap").dumps(token)
    set_cookie(response, BOOTSTRAP, signed, 3600)
    return {
        "kind": "anonymous",
        "csrfToken": token,
        "revision": 0,
        "googleEnabled": bool(get_settings().google_client_id),
    }


@router.post("/guest-sessions", response_model=SessionView)
async def create_guest(
    body: Revision,
    request: Request,
    response: Response,
    db: DB,
    session: Annotated[Session | None, Depends(optional_session)],
) -> dict:
    require_origin(request)
    if session:
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            # A retry can arrive after the browser has received the new guest cookie.
            try:
                bootstrap = URLSafeTimedSerializer(
                    get_settings().secret_key, salt="bootstrap"
                ).loads(request.cookies.get(BOOTSTRAP, ""), max_age=3600)
                retry_token = hmac.new(
                    get_settings().secret_key.encode(),
                    f"guest:{bootstrap}".encode(),
                    hashlib.sha256,
                ).hexdigest()
                valid_retry = secrets.compare_digest(
                    bootstrap, request.headers.get("x-csrf-token", "")
                ) and secrets.compare_digest(session.token_hash, digest(retry_token))
            except BadSignature:
                valid_retry = False
            if not valid_retry:
                raise HTTPException(403, "Invalid CSRF token")
        return await session_view(session, db)
    try:
        token = URLSafeTimedSerializer(get_settings().secret_key, salt="bootstrap").loads(
            request.cookies.get(BOOTSTRAP, ""), max_age=3600
        )
    except BadSignature as exc:
        raise HTTPException(403, "Load the session before starting as a guest") from exc
    if body.expectedRevision != 0 or not secrets.compare_digest(
        token, request.headers.get("x-csrf-token", "")
    ):
        raise HTTPException(403, "Invalid bootstrap CSRF token")
    key = request.headers.get("idempotency-key", "")
    if not 8 <= len(key) <= 100:
        raise HTTPException(400, "An Idempotency-Key is required")
    # The bootstrap cookie deterministically identifies creation retries, including lost responses.
    raw_token = hmac.new(
        get_settings().secret_key.encode(), f"guest:{token}".encode(), hashlib.sha256
    ).hexdigest()
    session = await db.scalar(select(Session).where(Session.token_hash == digest(raw_token)))
    if not session:
        session = Session(
            token_hash=digest(raw_token),
            csrf=secrets.token_urlsafe(32),
            kind="guest",
            expires_at=now() + timedelta(days=30),
        )
        try:
            async with db.begin_nested():
                db.add(session)
                await db.flush()
        except IntegrityError:
            # Concurrent bootstrap retries converge on the same opaque session.
            session = await db.scalar(
                select(Session).where(Session.token_hash == digest(raw_token))
            )
            if session is None:
                raise
    set_cookie(response, COOKIE, raw_token, 30 * 86400)
    return await session_view(session, db)


@router.post("/auth/logout")
async def logout(body: Revision, response: Response, db: DB, session: MutationPrincipal) -> dict:
    locked = await db.scalar(
        select(Session)
        .where(Session.id == session.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked or locked.revision != body.expectedRevision:
        raise HTTPException(409, "Session revision changed")
    # Keep guest rows for the promised retention period. Revoking the token ends access.
    locked.token_hash = digest(secrets.token_urlsafe(32))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/google/start")
async def google_start(
    request: Request, db: DB, session: Annotated[Session | None, Depends(optional_session)]
) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google sign-in is not configured. Guest play is available.")
    state, browser_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    async with AsyncOAuth2Client(
        settings.google_client_id,
        scope="openid profile",
        redirect_uri=f"{settings.api_url}/api/v1/auth/google/callback",
    ) as client:
        url, _ = client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            state=state,
            nonce=nonce,
            code_challenge=challenge,
            code_challenge_method="S256",
            prompt="select_account",
        )
    db.add(
        OAuthAttempt(
            id=digest(state),
            browser_hash=digest(browser_token),
            nonce=nonce,
            verifier=verifier,
            guest_id=session.id if session and session.kind == "guest" else None,
            expires_at=now() + timedelta(minutes=10),
        )
    )
    response = RedirectResponse(url, status_code=302)
    set_cookie(response, OAUTH_COOKIE, browser_token, 600)
    return response


async def exchange_google(code: str, attempt: OAuthAttempt) -> dict:
    settings = get_settings()
    async with AsyncOAuth2Client(
        settings.google_client_id,
        settings.google_client_secret,
        redirect_uri=f"{settings.api_url}/api/v1/auth/google/callback",
        token_endpoint_auth_method="client_secret_post",
    ) as client:
        token = await client.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code,
            code_verifier=attempt.verifier,
            grant_type="authorization_code",
        )
    async with httpx.AsyncClient(timeout=10) as http:
        response = await http.get("https://www.googleapis.com/oauth2/v3/certs")
        response.raise_for_status()
        keys = response.json()
    return validate_google_token(token, keys, attempt.nonce)


def validate_google_token(
    token: dict[str, Any], keys: KeySetSerialization, nonce: str
) -> dict[str, Any]:
    settings = get_settings()
    decoded = jwt.decode(
        token["id_token"],
        KeySet.import_key_set(keys),
        algorithms=["RS256"],
    )
    claims = CodeIDToken(
        decoded.claims,
        decoded.header,
        options={
            "iss": {
                "essential": True,
                "values": ["https://accounts.google.com", "accounts.google.com"],
            },
            "aud": {"essential": True, "value": settings.google_client_id},
            "sub": {"essential": True},
            "exp": {"essential": True},
        },
        params={
            "nonce": nonce,
            "client_id": settings.google_client_id,
            "access_token": token.get("access_token"),
        },
    )
    claims.validate(leeway=30)
    return dict(claims)


async def claim_guest(db: AsyncSession, guest_id: str, user_id: str) -> None:
    guest = await db.scalar(select(Session).where(Session.id == guest_id).with_for_update())
    if not guest or guest.kind != "guest" or not future(guest.expires_at):
        return
    await prune_guest(db, guest)
    for entity in (Draft, Match):
        await db.execute(
            update(entity)
            .where(entity.session_id == guest.id, entity.user_id.is_(None))
            .values(user_id=user_id, session_id=None)
        )
    guest.token_hash = digest(secrets.token_urlsafe(32))


@router.get("/auth/google/callback")
async def google_callback(
    request: Request, db: DB, state: str = "", code: str = "", error: str = ""
) -> RedirectResponse:
    attempt = await db.scalar(
        select(OAuthAttempt).where(OAuthAttempt.id == digest(state)).with_for_update()
    )
    browser_token = request.cookies.get(OAUTH_COOKIE, "")
    if (
        not attempt
        or not future(attempt.expires_at)
        or not browser_token
        or not secrets.compare_digest(attempt.browser_hash, digest(browser_token))
    ):
        raise HTTPException(400, "Invalid or expired Google sign-in state")
    await db.delete(attempt)
    if error or not code:
        return RedirectResponse(
            f"{get_settings().frontend_url}/play?auth=cancelled", status_code=302
        )
    try:
        claims = await exchange_google(code, attempt)
    except Exception:
        # Return normally so the consumed, single-use attempt is committed even on failure.
        return RedirectResponse(f"{get_settings().frontend_url}/play?auth=failed", status_code=302)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Serialize first logins for the same Google subject across application workers.
        subject_lock = int.from_bytes(
            hashlib.sha256(claims["sub"].encode()).digest()[:8], signed=True
        )
        await db.execute(sql_text("SELECT pg_advisory_xact_lock(:key)"), {"key": subject_lock})
    identity = await db.get(OAuthIdentity, claims["sub"])
    if not identity:
        user = User(name=str(claims.get("name", "Captain"))[:200])
        db.add(user)
        await db.flush()
        identity = OAuthIdentity(subject=claims["sub"], user_id=user.id)
        db.add(identity)
        await db.flush()
    response = RedirectResponse(f"{get_settings().frontend_url}/history", status_code=302)
    await new_session(db, response, identity.user_id)
    if attempt.guest_id:
        # Bind claiming to the same guest cookie that initiated this OAuth attempt.
        existing = await optional_session(request, db)
        if existing and existing.id == attempt.guest_id:
            await claim_guest(db, attempt.guest_id, identity.user_id)
    response.delete_cookie(OAUTH_COOKIE, path="/")
    return response
