# Deployment

The repository is ready to configure on Railway (API/PostgreSQL) and Vercel (Next.js). No hosting project, real-player license, custom domain, or Google credential is included.

## Player catalog

The development seed is fictional and is not approved for production. Supply an approved, manually curated JSON dataset with provenance and usage rights. The import schema is `CatalogImport` in `chase201/catalog.py`:

```json
{
  "version": "approved-2026-01",
  "source": "Documented approved source",
  "license": "Documented rights and approval reference",
  "approved": true,
  "players": [
    {"id": "stable-id", "name": "Approved identity", "role": "BATTER", "overallRating": 80, "batting": 82, "bowling": 25}
  ]
}
```

The fragment illustrates the schema, not a valid full catalog. Include at least 25 batters, 5 wicketkeepers, 10 all-rounders and 15 bowlers. Every role-specific slot gets five disjoint offers so all drafts remain completable. IDs must be unique; coefficients and ratings range from 1–100. Import refuses an existing version and never overwrites its rows.

After migrating, run `python -m chase201.catalog --file /path/to/approved.json` against the intended database, and set `CATALOG_VERSION` to its version. `approved: true` records an actual human approval; the importer cannot determine legal rights. Recalibrate the engine against the imported catalog.

Rating-limited drafts require at least 5 batters and 5 all-rounders rated 90–92, plus 20 batters, 5 keepers, 5 all-rounders and 15 bowlers rated 78–85. New simple catalogs must declare `selectionRuleset: simple-v1`, supply a `batting` rating (1–100), and support eleven disjoint five-player offers. They require no playstyles, legacy batting attributes or non-dominance constraints. Imports fail before activation when these conditions cannot be met. For local development, apply `alembic upgrade head`, seed immutable fixtures with `python -m chase201.catalog`, and select `fictional-v4`; preserve all existing catalog profiles. See [v3 rollout and verification](three-modes.md).

## Railway

1. Create a PostgreSQL service and API service using the repository root as build context. `railway.json` points to `apps/api/Dockerfile`.
2. Set `DATABASE_URL` with the `postgresql+asyncpg://` scheme and Railway’s private Postgres host; set `ENVIRONMENT=production`, a fresh random `SECRET_KEY` of at least 32 characters, and the approved `CATALOG_VERSION`.
3. Set `FRONTEND_URL=https://play.chase201.com`, `API_URL=https://api.chase201.com`, and `CORS_ORIGINS=["https://play.chase201.com"]` using your actual related domains. Configure DNS/TLS in both hosting projects.
4. Provide `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from a Google web OAuth client. Register exactly `https://api.chase201.com/api/v1/auth/google/callback`. For local development use `http://localhost:8000/api/v1/auth/google/callback` as an additional authorized redirect.
5. The pre-deploy command applies Alembic revisions. `/health` checks database connectivity. The Docker process runs as a non-root user and reads Railway’s `PORT`.
6. Add an hourly cron service using the same image/environment, command `python -m chase201.cleanup`, schedule `0 * * * *`, and no HTTP healthcheck. It should exit after each run. This is necessary to physically delete expired guest data; requests deny expired games immediately even between cleanup runs.

The application refuses production startup with a development secret, HTTP URLs, wildcard CORS, SQLite, or the fictional catalog. Import your approved version before directing traffic to the service. Store credentials only in the hosting environment; never in Git or a `NEXT_PUBLIC_` variable.

## Vercel

Import the monorepo, select `apps/web` as Root Directory, and include files outside that root so npm can access the workspace lockfile. `apps/web/vercel.json` supplies installation/build commands. Set `NEXT_PUBLIC_API_URL=https://api.chase201.com` before building and attach the related frontend domain. The public API URL is the only frontend environment variable required.

Use related HTTPS custom domains for cookie-based authentication. Default unrelated Vercel/Railway hostnames are not the intended production topology for SameSite=Lax cookies. Add any preview origin explicitly only when it is an approved related domain; never use wildcard credentialed CORS.

## Validate the deployment

From an installed API environment:

```sh
python scripts/smoke.py --api https://api.chase201.com --origin https://play.chase201.com
```

This intentionally creates one guest draft, completes a chase, and checks score reconciliation. The guest data expires through normal retention. Then verify actual Google consent/sign-in in a browser and confirm that a guest match appears in authenticated history. The mocked test flow cannot validate a live Google project’s redirect configuration or consent screen.

The primary setup references used are [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [Tailwind with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs), [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Railway configuration](https://docs.railway.com/config-as-code/reference), and [Vercel monorepos](https://vercel.com/docs/monorepos).
