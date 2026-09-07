# API and persistence contract

The generated source of truth is `apps/api/openapi.json`; the web client uses `openapi-fetch` with `src/lib/api.generated.ts`. Response schemas explicitly exclude seeds, simulation coefficients, OAuth subjects, and bearer/session tokens.

## Request lifecycle

1. `GET /api/v1/session` returns the current session plus a CSRF token. Anonymous visitors receive an HttpOnly signed bootstrap cookie.
2. `POST /api/v1/guest-sessions` uses that CSRF token, `expectedRevision: 0`, and `Idempotency-Key`. Concurrent/lost-response retries of a bootstrap converge on the same opaque session.
3. Every game mutation sends an explicit allowed `Origin`, `X-CSRF-Token`, `Idempotency-Key` (8–100 characters), and `expectedRevision` in its JSON body.
4. The API locks the session and then the draft/match row. It verifies ownership before consulting idempotency responses, compares the full request fingerprint, validates the revision and state, and commits the result and retry response together.
5. State changes, decisions, append-only events and scorecard rows commit in one request-scoped async SQLAlchemy transaction. A failed action rolls everything back. Match reads also lock the aggregate while collecting events and team data to prevent a mixed-revision response.

`POST /drafts` expects the session revision and increments it. Draft edits, order, confirmation and match creation expect the draft revision. Match decisions expect the match revision. Successful edits increment the corresponding revision. Match creation also advances its source draft. Responses with HTTP 409 require a fresh read; the client automatically refreshes the affected query.

Idempotency keys are scoped by owner and action/resource. Reusing the same key with a changed body returns 409. A retry with the original body returns the original response even after later decisions or match completion. Responses expire after 30 days; the expected revision and one-match-per-team constraints still prevent replaying old actions after that period. Retention removes response snapshots associated with deleted guest games.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/guest-sessions` | Bootstrap a guest |
| GET | `/api/v1/session` | Session, CSRF and resumable game IDs |
| GET | `/api/v1/auth/google/start` | Begin OIDC with state, nonce and PKCE |
| GET | `/api/v1/auth/google/callback` | Verify identity and claim eligible guest data |
| POST | `/api/v1/auth/logout` | Revoke backend token and clear cookie |
| POST | `/api/v1/drafts` | New XI draft |
| GET | `/api/v1/drafts/{draft_id}` | Read owned draft |
| PUT | `/api/v1/drafts/{draft_id}/selections/{slot_id}` | Select offered player |
| PUT | `/api/v1/drafts/{draft_id}/batting-order` | Save all 11 ordered IDs |
| POST | `/api/v1/drafts/{draft_id}/confirm` | Lock team |
| POST | `/api/v1/matches` | Start confirmed XI’s only chase |
| GET | `/api/v1/matches/{match_id}` | Current match and full scorecard |
| POST | `/api/v1/matches/{match_id}/decisions` | Resolve next decision window |
| GET | `/api/v1/matches/{match_id}/events?after_revision=0` | Incremental ordered events |
| GET | `/api/v1/me/matches?offset=0&limit=20` | Authenticated history, newest first |

Ownership failures return 404 without revealing another player’s resource. Expired sessions return 401; invalid CSRF/origin returns 403; malformed choices return 422. Cookie CORS origins are explicit and credentialed, with no wildcard.

## Ownership and retention

`sessions.kind` distinguishes guest and authenticated sessions in a shared hashed-token namespace. Authentication uses Google’s stable subject, never email matching. Successful login issues a fresh seven-day authenticated session and transfers eligible guest drafts/matches to the user. Access from a revoked guest cookie stops immediately. Different authenticated sessions for one user share access to that user’s games.

Guest access renews for 30 days on a successful game mutation. Each guest draft/match is independently inaccessible 30 days after creation, even if the session remains active. Cleanup removes old match events, decisions, scorecards, idempotency snapshots and orphaned draft/team data. A supporting team is retained while a younger match still references it. Claiming prunes expired games before transferring surviving rows, and uses the same guest lock as cleanup and mutations.

Catalog versions, players and simulation profiles are append-only through the application. Imported IDs are namespaced by version; drafts bind to a catalog version and matches to a ruleset version, so future imports/tuning cannot change an existing chase.
