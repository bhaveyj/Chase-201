import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from chase201.auth import DB
from chase201.auth import router as auth_router
from chase201.config import get_settings
from chase201.models import CatalogVersion
from chase201.routes import router
from chase201.timing import request_timings

logger = logging.getLogger("chase201.timing")

app = FastAPI(title="Chase 201 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
    expose_headers=["Server-Timing"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    timings: dict[str, float] = {}
    token = request_timings.set(timings)
    started = perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_timings.reset(token)
    timings["total"] = (perf_counter() - started) * 1000
    response.headers["Server-Timing"] = ", ".join(
        f"{name};dur={duration:.1f}" for name, duration in timings.items()
    )
    if request.url.path.endswith("/decisions"):
        logger.info("decision request status=%s timing_ms=%s", response.status_code, timings)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if get_settings().secure_cookies:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready(db: DB) -> dict:
    await db.execute(text("SELECT 1"))
    catalog = await db.get(CatalogVersion, get_settings().catalog_version)
    if catalog is None or (get_settings().environment == "production" and not catalog.approved):
        raise HTTPException(503, "The configured player catalog is not ready")
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(router)
