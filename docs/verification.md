# Verification record — gameplay redesign

## Rating limits and All Out update — 13 September 2026

New drafts use `balanced-v1` and `fictional-v2`: one 90–92-rated batter, one 90–92-rated all-rounder and nine 78–85-rated core players. New matches use `v2.1`. The existing 38-0-inspired dark design is retained. See [balance evidence](rating-balance.md).

- **86 backend tests passed on PostgreSQL**, including concurrent actions, rating validation at selection/order/confirmation/match creation, 100 complete disjoint offer draws, frozen v2.0/v2.1 replays and migration preservation/rollback guards. A subsequent focused rating suite passed **9 tests**, adding compatibility for pre-update idempotency receipts.
- **9 frontend unit tests** and **4 desktop/mobile browser journeys** passed. Browser checks cover all eleven slots' rating bands, star/core counters, keyboard reordering, full chases, history and WCAG A/AA accessibility. Desktop and mobile draft screenshots were visually reviewed.
- Ruff, MyPy, import-linter, ESLint, generated OpenAPI/TypeScript contracts, diff whitespace checks and the production build passed. All eight frontend routes built into the standard `.next` directory.
- PostgreSQL upgrade → schema drift check → downgrade to base → upgrade → drift check passed on the dedicated migration database. The local game database was backed up before upgrading to `f31b72d4c905`; all **15 existing match snapshots and all original catalog profiles** were verified unchanged. The backup is private and ignored under `work/chase201-before-ratings-20260913.sql`.
- Both 500-seed reports passed their balance gates. The CI-sized 300-seed draft stress check passed too. In 500 randomized drafts, fixed All Out won 15.8%, no chase ended within eight overs, and 50-run two-over blocks averaged 1.5%. The strongest permitted batting lineup also passed all burst/win gates.
- The rebuilt local frontend and restarted API were checked against PostgreSQL. The smoke journey explicitly validated the draft rating bands and `v2.1`, then completed a chase and reconciled its scorecard. A final live browser check confirmed `fictional-v2`, `balanced-v1`, five star options, the dark theme and no horizontal overflow on desktop and mobile.

Browser evidence: `outputs/browser-ratings-20260913/`; final served-page screenshots: `outputs/rating-live-desktop.png` and `outputs/rating-live-mobile.png`. New caps/tuning apply when starting a fresh chase; existing drafts and matches keep their recorded rules.

## Earlier verification

UI serving fix, 12 September 2026: the local frontend had been restarted from a build containing the original light design. The 38-0-inspired source was intact. Rebuilt all routes into the standard `.next` directory and restarted the frontend on port 3000. Desktop and mobile browser checks confirmed the dark theme, green accents, hero wordmark, hub cards, working guest lobby and no horizontal overflow. Gameplay source was unchanged. Screenshots are in `outputs/ui-restored-desktop.png` and `outputs/ui-restored-mobile.png`.

Verified locally on 10 September 2026 with Python 3.12.5, Node 20.19.2, Next.js 16.3.4 and PostgreSQL 17.

| Check | Result |
| --- | --- |
| Backend suite on PostgreSQL | **73 passed**, including concurrent decisions, cross-session idempotency, v1 compatibility, v2 interruption/replay, cricket invariants and populated legacy migration tests |
| Frontend unit tests | **9 passed**; strategy selection, refreshed bands, legacy controls, disabled inputs, API validation and recovery |
| Browser journeys | **4 passed** across desktop and mobile Chromium on the final UI |
| Accessibility | WCAG A/AA scans on landing, draft, order, match, result and history; no horizontal overflow; keyboard controls passed |
| Static checks | Ruff, MyPy, ESLint, TypeScript and import-linter passed |
| Production frontend | All eight routes built successfully into `.next-v2-production` |
| PostgreSQL migration | Upgrade → drift check → downgrade to base → upgrade → drift check passed on `chase201_migration_test` |
| Populated v1 migration | SQLite migration test verifies deterministic profile backfill, unchanged old state/events/ratings, preserved decision fields and safe downgrade refusal once v2 matches exist |
| Local database rollout | Backed up existing game database, upgraded to `e20a91d8f672`, and checked schema drift; eight existing matches remain on v1.0 |
| Running application smoke | Full guest draft → XI → v2 chase → reconciled result passed against the local PostgreSQL API; frontend returned HTTP 200 |
| Calibration | 500 common seeds across seven policies/four scenarios plus the full fictional catalog; all balance gates passed. The CI-sized 300-seed run also passed |
| Frozen replay | Pre-change v1 full-trace hashes for all nine choices preserved; deterministic v2 trace hashes cover all five plans |
| Contracts | OpenAPI regenerated and compared to application schemas; TypeScript client regenerated; no hidden profiles, numerical probabilities or seeds in public responses |

The live smoke match `f955dfa6-a6a4-4c85-99be-24db8d097ce0` finished **203/4, won**, on v2.0. Local services are running at [the game](http://localhost:3000/play) and [the API](http://localhost:8000/docs), with this project's PostgreSQL container on port 5433. Saved v1 matches still use the original engine and original controls; draft a new XI to try v2.

Final browser evidence is in the ignored `outputs/browser-v2-mobile-final/` directory, including both desktop and mobile screenshots. Visual review found that the existing mobile CSS hid the bowler; that was corrected and both browser projects passed again. The local pre-migration SQL backup is in ignored `work/chase201-before-v2-20260910.sql`; it contains private local application data and is not part of the source change.

The standard Windows temp folder and old OneDrive output folders were locked during some checks. PostgreSQL tests passed with a fresh `work/pytest-postgres-v2` temporary directory and cache writing disabled. Browser tests used a fresh output directory. The production build passed in a fresh output directory without a preceding type-generation cleanup. These workarounds do not change the deployable application or CI checks.

The 500-seed [calibration artifact](calibration-v2.json) and [engine notes](engine.md) document coefficients, envelopes, policy performance, full-catalog sensitivity and limitations. Adaptive policies were competitive across situations; no repeated fixed plan was dominant across all pressure scenarios. These fictional benchmarks do not establish perfect balance against every possible policy.

No production deployment or live Google consent flow was performed. Browser tests stub only the external token exchange; application state, cookies, claiming and history still execute. Existing signed-token tests verify issuer, audience, nonce, expiry and signatures. Authlib emits two upstream deprecation warnings. The Docker API image was not rebuilt in this pass; the Python application and migrations were verified directly against PostgreSQL.
