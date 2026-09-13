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

New drafts persist `selectionRuleset: balanced-v1`. Slots expose `ratingLabel`, `minimumRating` and `maximumRating`. Draft positions 0 (batter) and 6 (all-rounder) offer five players rated 90–92; the other nine positions offer five players rated 78–85. All 55 offers are disjoint. Selection, batting-order validation, confirmation and match creation recheck rating eligibility. Reordering does not change a player's original draft slot. An incompatible catalog returns 503 and rolls back the whole draft. Existing drafts are migrated to `open-v1` and retain their original options and ratings.

`sessions.kind` distinguishes guest and authenticated sessions in a shared hashed-token namespace. Authentication uses Google’s stable subject, never email matching. Successful login issues a fresh seven-day authenticated session and transfers eligible guest drafts/matches to the user. Access from a revoked guest cookie stops immediately. Different authenticated sessions for one user share access to that user’s games.

Guest access renews for 30 days on a successful game mutation. Each guest draft/match is independently inaccessible 30 days after creation, even if the session remains active. Cleanup removes old match events, decisions, scorecards, idempotency snapshots and orphaned draft/team data. A supporting team is retained while a younger match still references it. Claiming prunes expired games before transferring surviving rows, and uses the same guest lock as cleanup and mutations.

Catalog versions, players and simulation profiles are append-only through the application. Imported IDs are namespaced by version; drafts bind to a catalog version and matches to a ruleset version, so future imports/tuning cannot change an existing chase.

## Tactical decisions and v2 rollout

New matches bind to `v2.1`; saved `v2.0` matches use their frozen coefficients. Send one plan:

```json
{"expectedRevision": 0, "strategy": "ATTACK"}
```

Allowed strategies are `PRESERVE`, `ROTATE`, `BALANCED`, `ATTACK`, and `ALL_OUT`. `v1.0` saved matches accept the original `intent`/`riskFocus` body and continue through the original engine. The union is strict: mixed bodies, unknown fields, or the wrong contract for the match return 422 without advancing the revision. The frontend chooses controls using `rulesetVersion`.

`MatchView` now includes `context` (pressure, phase, both batter setness labels and matchup), `strategyAssessments` (one entry per plan with qualitative scoring, boundary and wicket-risk bands), and `upcomingBowlers` (overall rating, role, pace/spin style and one-based over). These are computed by the server. Assessments describe the current striker against the current bowler on the next delivery; they are refreshed after every decision. Finished/legacy matches have null context and empty assessment/upcoming-bowler lists. Private player attributes, probability distributions and seed data remain excluded.

The state adds `recent_outcomes`, `partnership_runs`, `partnership_balls` and `last_wicket_ball`. Older snapshots deserialize with safe defaults. `decisionWindow` counts the maximum legal balls remaining until the next scheduled boundary, except free hits and the final two overs which resolve exactly one delivery (possibly illegal). Completed matches return zero.

Each new event includes `strategy`, `interruption`, ordered `deliveries`, and `contextBefore`/`contextAfter`. Interruption values are `WINDOW_END`, `WICKET`, `NO_BALL`, `FREE_HIT` (an extra preserves an already pending free hit), and `INNINGS_COMPLETE`. Delivery entries include outcome, legal-ball positions, runs, wickets, striker/bowler IDs and free-hit state. `THREE` is a supported outcome. One presentation event is persisted per decision; its `AGGREGATE` kind now describes presentation, while actual simulation always evaluates each delivery. The chosen plan prefixes the event label, e.g. `Attack · 11 runs, 1 wicket`.

The `decisions` table stores the one-axis strategy and its qualitative pre-decision context. Legacy intent/risk columns are retained and nullable; a database check constraint enforces exactly one representation. Match state, decision, detailed events, scorecards and the idempotency response still commit together. Exact deterministic replay, stale-revision rejection, cross-session locking and ownership behavior are unchanged.

Run Alembic through `e20a91d8f672` before starting the updated API. The migration adds/backfills expanded profile fields and adds decision columns/checks; it never modifies existing match versions, seeds, snapshots or events. Original profile `batting` and `bowling` values remain intact. New catalog imports may supply `batting_control`, `batting_rotation`, `batting_power`, `bowling_control`, `bowling_threat` (1–100), and `bowling_style` (`PACE`/`SPIN`); omitted attributes use a stable player-ID backfill.

Downgrade is supported when no v2 matches exist. Once v2 games have been created, the migration refuses downgrade because the old schema cannot represent them; restore a pre-upgrade backup for that rollback. Deploy backend and generated-contract-compatible frontend together. Replaying old idempotency snapshots applies response-schema defaults to newly added optional fields and never re-simulates the action.
