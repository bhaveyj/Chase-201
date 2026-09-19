# Chase 201

A guest-first, single-player cricket chase. Draft an XI, choose the batting order, and chase 201 in 20 overs. The complete Next.js → FastAPI → PostgreSQL journey is implemented.

The default catalog contains **200 real cricket players across 17 countries**: 139 unique user-supplied players with their original roles and ratings, plus 61 researched additions. Added ratings are editorial T20 game estimates, not official ICC ratings. See the [roster and sources](docs/player-catalog.md). Historical fictional catalogs remain available for saved games and regression fixtures.

## Run locally

Requires Python 3.12+, Node 20.19+ (Node 22 is used in CI), and Docker Desktop.

From the repository root, in PowerShell:

```powershell
docker compose up -d db
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r apps/api/requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e apps/api
npm ci
Copy-Item apps/api/.env.example apps/api/.env
Copy-Item apps/web/.env.example apps/web/.env.local
```

Start the API in one terminal:

```powershell
cd apps/api
..\..\.venv\Scripts\alembic.exe upgrade head
..\..\.venv\Scripts\python.exe -m chase201.catalog
..\..\.venv\Scripts\python.exe -m uvicorn chase201.main:app --reload --port 8000
```

Start the frontend from the repository root in another terminal:

```powershell
npm run dev
```

Open [the game](http://localhost:3000). [Interactive API documentation](http://localhost:8000/docs) is available locally. On macOS/Linux, use `.venv/bin/python`, `.venv/bin/alembic`, and `cp` instead of the Windows equivalents. Run API commands from `apps/api` so the environment file and migration configuration resolve correctly.

For a local production preview, run `npm run build` followed by `npm run start --workspace apps/web`, with `NEXT_OUTPUT_DIR` unset for both commands. The build requires `NEXT_PUBLIC_API_URL`; copying `apps/web/.env.example` to `apps/web/.env.local` supplies the local value.

If another project uses port 5432, set `POSTGRES_PORT=5433` in a root `.env` file and change the port in `apps/api/.env` and `TEST_DATABASE_URL` to 5433. Compose keeps the database volume when its published port changes.

## What is implemented

- Landing, lobby, XI draft, batting order, live chase, result/scorecard, and authenticated history routes.
- Immediate guest play; resumable drafts and live matches; 30-day retention **per guest game**, with a renewable guest access cookie.
- Google OIDC authorization code flow with PKCE, nonce, browser-bound single-use state, verified RS256 ID tokens, opaque backend sessions, token rotation, and guest-to-user claiming.
- Immutable catalog versions and private simulation profiles; exact 5/1/2/3 role composition; five disjoint offers per slot; unique selections and complete batting-order validation.
- One match per confirmed XI and a balanced AI XI from the same catalog. New real-player drafts have one star batter and one star all-rounder rated 90–100, five core players rated 75–89, and a keeper plus three bowlers rated 75–100. Stars may bat anywhere; the server validates the limits at every team boundary. Saved fictional drafts retain their original 90–92/78–85 limits.
- Exactly three modes for new matches: Defensive, Balanced and Aggressive; per-delivery matchup/context simulation; wicket and free-hit interruptions; recent deliveries, partnerships, setness and exact next-delivery wicket risk.
- Simple player cards show name, role and OVR. Modes control risk and reward; unique five-player offers retain role and rating limits. Historical cards keep their original attributes.
- Server-owned deterministic seeds, versioned rules, transactionally stored decisions/events/state/scorecards, ownership checks, CSRF, expected revisions, and idempotent retries.
- Desktop/mobile UI, keyboard-operable team ordering and strategy controls, accessible status/error messages, reduced-motion support, and automated WCAG AA checks.
- Alembic migration, Docker image, Railway/Vercel configuration, CI, cleanup command, generated API types, calibration report command, and deployment smoke test.

## Repository map

```text
apps/web/src/app/           Next.js App Router pages
apps/web/src/components/    Game UI and journey
apps/web/src/lib/           Typed REST client; transient Zustand store
apps/web/e2e/               Playwright + axe desktop/mobile journeys
apps/api/src/chase201/      HTTP, auth, application services, persistence
apps/api/src/chase_engine/  Pure Python simulation, without framework or I/O imports
apps/api/migrations/       Tracked Alembic revisions
apps/api/tests/            API, ownership, retention, simulation and concurrency tests
apps/api/scripts/          OpenAPI export, calibration and smoke commands
docs/                     Engine, API and deployment notes
```

TanStack Query owns server-backed data. Zustand only contains the active draft tab, unsaved order changes, and selected strategy. The frontend does not persist authoritative data to localStorage, sessionStorage, or a Zustand persistence store. The browser stores only HttpOnly server-issued session/OAuth/bootstrap cookies.

## Tests and checks

Backend, from `apps/api`:

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q
..\..\.venv\Scripts\ruff.exe check src tests scripts migrations
..\..\.venv\Scripts\mypy.exe src
..\..\.venv\Scripts\lint-imports.exe
```

The default fast suite uses a disposable SQLite database; PostgreSQL concurrency tests are explicitly skipped there. To include real row-lock tests, create the dedicated test database from the root, then run:

```powershell
docker compose exec -T db createdb -U chase201 chase201_test
cd apps/api
$env:TEST_DATABASE_URL='postgresql+asyncpg://chase201:local-development-only@localhost:5432/chase201_test'
..\..\.venv\Scripts\python.exe -m pytest -q
```

The test fixture recreates only a database named `chase201_test`; never point it at application data.

Frontend, from the root:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright starts isolated servers on ports 3000 and 8001; stop any existing server on 3000 first. It uses a fresh temporary SQLite database per run and a test-only Google exchange in `tests/e2e_server.py`. That file is neither packaged nor copied into the deployment image. Real OAuth state, cookies and history claiming still run in the browser tests. On Windows, if OneDrive holds an old test output folder open, set `PLAYWRIGHT_OUTPUT_DIR` to a fresh path under `outputs/`.

Refresh generated contracts after changing API schemas:

```powershell
cd apps/api
..\..\.venv\Scripts\python.exe scripts/export_openapi.py
cd ../..
npm run api:types
```

CI checks migration upgrade/downgrade and schema drift, architecture boundaries, Python/TypeScript typing, both unit suites, common-seed gameplay balance and catalog sensitivity, PostgreSQL concurrency, generated-contract drift, the production build, and browser journeys.

New drafts use the `real-players-v2` catalog with `real-players-v1` selection rules and create `v3.5` matches. Saved drafts retain their original catalogs and limits. Apply `alembic upgrade head`, run `python -m chase201.catalog`, and set `CATALOG_VERSION=real-players-v2` for local development. Start a new chase to use the real-player roster and corrected scoring. Player cards omit Batting and its rating no longer affects the engine. Repeated Aggressive play faces earlier bowling adaptation, while all sampled scoring outcomes—including winning runs—are retained. Any approach can earn a win; there is no forced score block at 200. See [current semantics and calibration](docs/three-modes.md).

See the [verification record](docs/verification.md) for completed local checks and their limits.

## Production launch

See [deployment instructions](docs/deployment.md), [API contract notes](docs/api.md), and [engine semantics](docs/engine.md). Live Google credentials, related HTTPS custom domains, hosting projects, and an approved player dataset must be supplied. No external deployment or real Google account login is performed by the local test suite.

The application intentionally has no score sharing, defending mode, multiplayer, WebSockets, live data, or social features.
