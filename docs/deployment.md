# Deployment

The intended deployment uses Render for the API, Neon for PostgreSQL, and Vercel for the Next.js frontend. The live Render database connection must still be switched during cutover. No custom domain or Google credential is included.

## Player catalog

The bundled `real-players-v2` roster is useful for development and testing, but its public-source identities and editorial ratings do not constitute production licensing approval. Supply an approved, manually curated JSON dataset with provenance and usage rights. The import schema is `CatalogImport` in `chase201/catalog.py`:

```json
{
  "version": "approved-2026-01",
  "source": "Documented approved source",
  "license": "Documented rights and approval reference",
  "approved": true,
  "selectionRuleset": "real-players-v1",
  "players": [
    {"id": "stable-id", "name": "Approved identity", "role": "BATTER", "overallRating": 80, "batting": 82, "bowling": 25, "bowling_style": "PACE"}
  ]
}
```

The fragment illustrates the schema, not a valid full catalog. For `real-players-v1`, provide at least five batters and five all-rounders rated 90–100; 20 more batters and five more all-rounders rated 75–89; and five wicketkeepers plus 15 bowlers rated 75–100. Every slot gets five disjoint offers, so all drafts remain completable. IDs must be unique; coefficients and ratings range from 1–100. Import refuses an existing version and never overwrites its rows.

After migrating, run `python -m chase201.catalog --file /path/to/approved.json` against the intended database, and set `CATALOG_VERSION` to its version. `approved: true` records an actual human approval; the importer cannot determine legal rights. Recalibrate v3.5 against the final roster before launch; the checked `balance_v35.py` report currently targets the bundled roster, so adapting that input is a required release task once the approved dataset is known.

For local development, apply `alembic upgrade head`, seed the bundled roster with `python -m chase201.catalog`, and select `real-players-v2`. Use `--legacy-fixtures` only when testing historical saved-game compatibility. Preserve every imported catalog because existing drafts and matches retain their catalog and engine versions. See [current v3.5 semantics](three-modes.md).

## Render

The root `render.yaml` defines the free Render Docker web service `chase201-api`. Its `DATABASE_URL` is a secret supplied in the Render Dashboard, not a Render Postgres reference. An existing Render Postgres resource is not deleted when its Blueprint definition is removed; leave it in place until any data migration and cutover are verified.

For this app, set Render's `DATABASE_URL` to the **direct** Neon production URL (`DATABASE_URL_UNPOOLED` in the gitignored root `.env` created by `neon link`). The Docker startup command runs `alembic upgrade head && python -m chase201.catalog --approve-real-catalog` before Uvicorn, and migrations must use a direct connection. The API converts Neon's libpq URL to SQLAlchemy/asyncpg and verifies TLS certificates. Do not put the URL or password in Git. On an existing Render Blueprint, `sync: false` does not prompt for or replace the existing variable: edit it manually on the service's Environment page, then deploy.

Before changing Render's URL, decide whether existing users, OAuth identities, drafts, and played matches must be retained. The Neon production branch currently has the application schema and bundled 200-player catalog, but no old user/game records. Back up and transfer required records before cutover; do not delete the Render database until the transfer and live app are verified.

`/health` is a cheap process check for Render and UptimeRobot; it does not query Neon every few seconds. `/ready` checks database connectivity and the configured approved catalog. Check `/ready` after deployment and investigate a non-200 response. The Docker startup still requires the database and catalog to be ready before it serves requests.

After syncing the Blueprint and deploying the frontend to Vercel, the default service URLs are expected to be:

```text
Frontend: https://web-omega-eight-96.vercel.app
API:      https://chase201-api.onrender.com
```

If Render or Vercel assigns different hostnames, update `FRONTEND_URL`, `API_URL`, `CORS_ORIGINS`, and `NEXT_PUBLIC_API_URL`, then redeploy the affected services.

Guest-only launch does not require Google credentials. To enable sign-in later, provide `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` on `chase201-api` and register exactly `https://chase201-api.onrender.com/api/v1/auth/google/callback`, or the equivalent custom API domain.

Render cron jobs are not part of the free Blueprint. For production retention cleanup, add a paid Render cron job or another scheduler that runs `python -m chase201.cleanup` hourly against the same API image and environment.

## Railway

1. Create a PostgreSQL service and API service using the repository root as build context. `railway.json` points to `apps/api/Dockerfile`.
2. Set `DATABASE_URL` with the `postgresql+asyncpg://` scheme and Railway’s private Postgres host; set `ENVIRONMENT=production`, a fresh random `SECRET_KEY` of at least 32 characters, and the approved `CATALOG_VERSION`.
3. Set `FRONTEND_URL=https://play.chase201.com`, `API_URL=https://api.chase201.com`, and `CORS_ORIGINS=["https://play.chase201.com"]` using your actual related domains. Configure DNS/TLS in both hosting projects.
4. Optional: provide `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from a Google web OAuth client to enable sign-in. Register exactly `https://api.chase201.com/api/v1/auth/google/callback`. For local development use `http://localhost:8000/api/v1/auth/google/callback` as an additional authorized redirect. If these values are omitted, the app launches as guest-only and the Google sign-in route returns a temporary unavailable response.
5. The pre-deploy command applies Alembic revisions. `/health` checks the API process; `/ready` checks database connectivity and confirms that the configured catalog exists and is approved in production. The Docker process runs as a non-root user and reads Railway’s `PORT`.
6. Add an hourly cron service using the same image/environment, command `python -m chase201.cleanup`, schedule `0 * * * *`, and no HTTP healthcheck. It should exit after each run. This is necessary to physically delete expired guest data; requests deny expired games immediately even between cleanup runs.

The application refuses production startup with an unknown environment name, a development secret, incomplete Google credentials, HTTP URLs, URL paths, wildcard CORS, SQLite, or a fictional catalog. Google credentials are optional, but must be provided as a complete client ID/client secret pair when sign-in is enabled. Readiness stays unhealthy until the configured approved catalog is imported. Store credentials only in the hosting environment; never in Git or a `NEXT_PUBLIC_` variable.

## Vercel

Import or deploy `apps/web` as the Vercel project. `apps/web/vercel.json` supplies installation/build commands for a standalone Vercel deploy. Set `NEXT_PUBLIC_API_URL=https://chase201-api.onrender.com` before building and attach the related frontend domain. Production builds now fail fast when that variable is missing; it is the only frontend environment variable required.

Use related HTTPS custom domains for cookie-based authentication when you enable sign-in. Default unrelated Vercel/Render hostnames are acceptable for guest-only preview, but are not the intended final topology for OAuth-backed sessions. Add any preview origin explicitly only when it is an approved related domain; never use wildcard credentialed CORS.

## Launch inputs still required

- A production-approved player JSON file, its documented rights/provenance, and a v3.5 calibration run against that exact roster.
- A Render Blueprint sync for `render.yaml`, any required old-data transfer, and a manual Render `DATABASE_URL` update to the direct Neon production connection.
- A fresh secret key and final service URLs/CORS origins. A Google web OAuth client with its consent screen and exact callback URI is only needed when enabling sign-in.
- A database backup/restore plan, error and uptime monitoring, and an owner for the retention cleanup scheduler and incident response.

## Validate the deployment

From an installed API environment:

```sh
python scripts/smoke.py --api https://chase201-api.onrender.com --origin https://web-omega-eight-96.vercel.app
```

This intentionally creates one guest draft, completes a chase, and checks score reconciliation. The guest data expires through normal retention. If Google sign-in is enabled, also verify actual Google consent/sign-in in a browser and confirm that a guest match appears in authenticated history. The mocked test flow cannot validate a live Google project’s redirect configuration or consent screen.

The primary setup references used are [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [Tailwind with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs), [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Railway configuration](https://docs.railway.com/config-as-code/reference), and [Vercel monorepos](https://vercel.com/docs/monorepos).
