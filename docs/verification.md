# Verification record

Verified locally on 6 September 2026 with Python 3.12.5, Node 20.19.2, Next.js 16.3.4 and PostgreSQL 17.

| Check | Result |
| --- | --- |
| Backend suite on PostgreSQL | 38 passed, including concurrent decisions and cross-session idempotency |
| Frontend unit tests | 7 passed using Vitest, Testing Library and MSW |
| Browser journeys | 4 passed across desktop and mobile Chromium |
| Accessibility | Automated WCAG A/AA scans on landing, draft, batting order, match, result and history; keyboard reordering and overflow checks passed |
| Static checks | Ruff, MyPy, ESLint, TypeScript and import-linter passed |
| Production frontend | All eight routes built successfully |
| Linux API image | Final source built successfully as `chase201-api:dev` |
| PostgreSQL migration | Upgrade, schema drift check, downgrade and upgrade passed on a dedicated migration database |
| Running API smoke | Guest session → XI → chase → persisted result passed against PostgreSQL |

The final smoke match was `269a5ff2-e06c-4677-a26f-d1ae57c0f525`, finishing at 189/4. The script checks terminal status and scorecard reconciliation. The engine suite also checks deterministic output, cricket invariants with generated cases, and scoring/wicket differences across strategy policies. See [engine calibration](engine.md).

Browser evidence is in the ignored local `outputs/browser-final/` directory. Google browser tests mock only the external token exchange; the application’s state, cookies, guest claiming and history code still execute. Separate signed-token tests reject invalid issuer, audience, nonce, expiry and signatures.

The local production frontend is served at `http://localhost:3000`, the API at `http://localhost:8000`, and this workspace’s database at `127.0.0.1:5433`. Root and API `.env` files contain the ignored local port override. Restart instructions are in the [README](../README.md).

No production deployment or live Google consent flow was performed. Launch requires hosting configuration, Google credentials, related HTTPS domains and an approved real-player catalog. Current gameplay uses the original fictional development catalog. Authlib emits two upstream deprecation warnings; its compatible version is pinned in the dependency lock files.
