# Verification record — gameplay redesign

## Aggressive opening inflation and late scoring stall — 19 September 2026

New simple and real-player matches use **v3.5**. The reported Aggressive-only chase was reproduced exactly from the saved revision-specific random streams: **197/7 after 20 overs**. V3.4's single-approach winning-run guard converted fours and sixes near the target into dots. V3.5 removes that guard and applies earlier, stronger repetition adaptation through probabilities from the opening overs. All sampled cricket outcomes keep their values, including winning boundaries and extras. Any approach can earn 201; the old zero-fixed-win requirement is historical. See [current semantics](three-modes.md) and [frozen v3.4 semantics](three-modes-v34.md).

- **461 backend tests passed against PostgreSQL**, covering historical replay, concurrency, the reported 197-run stall, every winning scoring outcome at 200, free hits, legal-delivery history, reloads and API idempotency. A further focused migration run passed with new v3.5 and real-player downgrade protections.
- **20 frontend unit tests** and **6 desktop/mobile browser journeys** passed. The added Aggressive-only journey plays actual deliveries, reloads, verifies unaltered outcome/run accounting and completes the chase. Accessibility checks remain included.
- The [500-seed real-player report](calibration-v35-real-players.json) passes all v3.5 checks across **8,000 full chases/continuations**, **500 deterministic replays**, **410,098 non-free-hit risk comparisons** and **3,311 zero-risk free-hit comparisons**. Historical burst limits still pass. Adaptive play wins **59.4%**, Balanced-only **36.2%**, Aggressive-only **25.6%**, and Defensive-only **0%**. Aggressive's mean first-ten-over score drops from **112.548 to 104.826** over common seeds; its final two-over samples contain fours, sixes, singles, twos, dots, wickets and extras.
- Comparing the new engine with the reported game's original decision entropy finishes **202/7 at 19.1 overs**, including 14 runs in the final two overs. This is a read-only comparison; the saved result is unchanged.
- Ruff, MyPy, import isolation, ESLint, TypeScript and the production build pass. OpenAPI and generated TypeScript include v3.5. Temporary build-directory entries were removed from tsconfig.
- The local preview was restarted using `.next-v35` on port 3000 and the API on port 8000. The served frontend responds successfully. A complete live Aggressive-only smoke chase used v3.5 and real-players-v2, ending naturally **70/10, lost**, with reconciled scorecards.
- Private row-hash comparisons verify every pre-existing row unchanged, including **53 drafts, 47 matches and 700 simulation profiles**, all original catalogs, offers, decisions, events, scorecards and idempotency receipts. Only the smoke journey's new guest/draft/match rows were added. No catalog or schema change was needed.

Start a new chase to use v3.5; saved games continue with their recorded engine. Upstream Authlib deprecation notices remain. No external deployment was performed.

## Real-player draft pool — 19 September 2026

New drafts use the `real-players-v2` catalog and `real-players-v1` selection rules, creating v3.4 matches. The [200-player roster and sources](player-catalog.md) cover 17 countries: 52 batters, 31 wicketkeepers, 55 all-rounders and 62 bowlers. All 139 unique supplied identities retain their exact roles and ratings; duplicated Devon Conway/Jos Buttler rows are collapsed, and 61 researched identities are added.

- Five hundred draft seeds exercised all 200 identities, with 55 disjoint offers and the correct 5/1/2/3 XI composition on every seed. Elite keepers/bowlers and the supplied 77–79-rated entries remain draftable under the new versioned rating limits.
- The full PostgreSQL suite passed **421 tests**, including concurrency and historical replay checks. After profile calibration and fixture isolation, all **9 real-catalog tests** passed against PostgreSQL. Four additional acceptance-comparison tests passed, covering sampling uncertainty, identical/better plans and rejection of materially weaker plans.
- **19 frontend unit tests**, **4 desktop/mobile browser journeys**, and a further complete desktop chase using the final calibrated catalog passed. Browser checks cover accessibility, no overflow, draft limits, ordering, reloads, match completion, reconciled scorecards and history. Draft screenshots were visually checked; artifacts are under private ignored `outputs/real-players/`.
- Ruff, MyPy, import boundaries, ESLint, TypeScript and the production build passed. OpenAPI export and generated TypeScript types have no contract drift. An API wheel was built and inspected to confirm the final JSON roster and profile calibration are included. Temporary build/type-directory changes were removed.
- A private database backup was captured before activation. Hash comparisons verified every pre-existing row unchanged, including **50 original drafts and 44 original matches**. The final calibration was imported as v2, preserving v1 and its already-created game: **51 drafts, 45 matches and 500 existing profiles** were unchanged during that import. Each activation added only its catalog and 200 identities/profiles.
- The calibrated [500-seed report](calibration-real-players-v2.json) passed all acceptance gates: **62.8% adaptive wins**, 0% wins for each fixed approach, and 82.6%/84.0% Defensive/Balanced wins in qualified low-pressure continuations. It covers 8,000 chases/continuations and 500 deterministic replays; the rules hash matches the original v3.4 report. Useful-plan comparisons for the real roster account for paired common-seed uncertainty; all other acceptance limits and engine coefficients remain unchanged.
- The tested frontend is served from `.next-real-players` on port 3000, with the final API on port 8000 and local `CATALOG_VERSION=real-players-v2`. The final Balanced-only live smoke completed **196/4, lost**, with reconciled figures. Start a new chase to use the new pool; saved games retain their original catalog and profiles.

## Batting stat removal and varied repeated play — 17 September 2026

New simple-v1 chases use v3.4. Simple player cards omit the Batting label, number and accessible description. Batting ratings no longer affect delivery probabilities, sustainable scoring, pressure or matchup feedback. The 60-run headroom and per-ball fixed-approach scoring budgets are replaced by probabilistic repetition adaptation throughout the innings. A single approach still cannot win.

- The [final 500-seed calibration](calibration-v34-final.json) passed every gate: **63.2% adaptive-play wins**, **0% for each fixed approach**, with mixed scoring in the opening and final three overs. It covers 8,000 chases/continuations and 500 deterministic replays, 414,217 non-free-hit risk comparisons and 3,415 zero-risk free-hit checks. The report hash matches the final rules. Defensive and Balanced tie at 83.4% in the qualified low-pressure scenario.
- The full SQLite backend suite passed **410 tests**, with two PostgreSQL-only concurrency tests skipped. After final probability tuning, all **39 v3.4 regression/API tests** passed again. Tests cover rating-independent contexts and full traces, random opening/final-over scoring, late boundaries, every target-guard outcome, free hits, reloads, and idempotency. Historical replay and migration guards passed.
- **17 frontend unit tests** and **4 desktop/mobile browser journeys** passed, including accessibility, no overflow, correct three-mode routing, selection, complete chases, reloads and scorecards. Desktop/mobile draft screenshots were visually checked. Artifacts: `outputs/browser-v34/`.
- Ruff, MyPy, import boundaries, ESLint, TypeScript and the production build passed. The OpenAPI export matches the running application, and TypeScript types include v3.4. Temporary verification-directory entries were removed from tsconfig.
- Earlier `.next` and browser artifact directories were locked by Windows. Verification used fresh `.next-verify-v34`, `.next-e2e-v34` and `outputs/browser-v34` directories. The tested frontend is served on port 3000; the final API is served on port 8000. Both are healthy and the live API exposes v3.4.
- A live Balanced-only smoke chase completed **161/10, lost**, with reconciled scorecards. It created a separate guest draft/match; existing matches, catalogs and receipts were not rewritten. New games are required to use the updated engine.

## Approach variation and 60–65% difficulty — 16 September 2026

New simple-v1 chases now use v3.2. The player-card Batting bar is removed, leaving a plain numeric rating. At least two approaches must be played on legal deliveries before scoring the winning runs; every fixed approach is prevented from winning by the server. Saved matches retain their earlier engines.

- The [500-seed calibration](calibration-v32-final.json) passed all gates: **64.2% sensible-switching wins**, **0% Defensive-only**, **0% Balanced-only**, **0% Aggressive-only**. It covers 8,000 chases/continuations plus 500 deterministic replays, 403,855 non-free-hit risk comparisons and 3,325 free-hit checks. The coefficient hash matches the final rules.
- **346 backend tests passed; 2 PostgreSQL-only concurrency tests skipped** in this SQLite run. New tests cover every near-target outcome for all three modes, forced unbroken sixes with maximum batting strength, randomized chases, qualification on legal deliveries, exact assessments, reloads and idempotency. Existing golden replays and migration/downgrade guards passed.
- **15 frontend unit tests and all 4 desktop/mobile browser journeys passed**, including accessibility, no horizontal overflow, bar removal, the visible approach requirement, reloads, full chases, scorecards and mocked sign-in/history. Draft screenshots were visually inspected on desktop and mobile. Browser artifacts: `outputs/browser-v32-final/`.
- Ruff, MyPy, import boundaries, ESLint, TypeScript and the production build passed. OpenAPI and TypeScript were regenerated, with the new state field confined to the three-mode response schema. The historical v1/v2 response schema remains unchanged.
- The locked standard `.next` folder was preserved as `.next-before-v32-20260916` and replaced by a fresh production build. The local frontend and API were restarted on ports 3000 and 8000. No migration, catalog rewrite or historical match update was needed. A local smoke chase confirmed v3.2 and Balanced-only play finished **200/4, tied**, with reconciled figures and no win.

## Simple batting and difficulty — 16 September 2026

New drafts use `fictional-v4` / `simple-v1`, creating `v3.1` matches. Saved `tradeoffs-v1` drafts still start `v3.0`; all previous engines remain frozen. See [gameplay semantics](three-modes.md) and the [final 500-seed report](calibration-v31-final.json).

- **163 tests passed in the full PostgreSQL suite**, including concurrency and v1/v2/v3 golden replay coverage. **Two additional PostgreSQL compatibility tests passed** for starting an old draft after switching catalogs and replaying an old receipt without a probability field. Focused v3.1/migration rechecks also passed after final changes. Nine v3.0 golden full-match traces were captured before implementation.
- **14 frontend unit tests** and **4 desktop/mobile browser journeys passed**. Tests cover the single Batting bar, original historical cards, three-mode routing for both versions, exact decimal formatting, all-mode free-hit zero risk, selection limits, reloads, history claiming, keyboard ordering and WCAG A/AA checks. Desktop/mobile draft and match screenshots were visually reviewed. The external Google token exchange is mocked in the browser suite.
- **500 randomized legal XIs and opponents**, using common delivery seeds for every policy, passed all acceptance gates across 8,000 chases/continuations and 500 repeat full-chase traces. Sensible switching wins **67.6%**, Balanced **62.4%**, Aggressive **41.8%**. Fixed-mode wicket rates are **1.30% Defensive, 4.84% Balanced, 9.45% Aggressive**. All 395,044 non-free-hit states have strictly increasing mode risk; all 3,299 sampled free hits have zero risk. Scorecards reconcile, deterministic traces match, every mode has a useful scenario, and burst limits pass.
- The unadjusted model's sensible win rate was 76.8%, above the requested ceiling. Shared four/six phase priors were scaled by **0.92**; requested batting baselines, variation, batting/mode vectors and the 0.8 setness scale were retained. The report's coefficient hash matches the final engine.
- Ruff, MyPy, import boundaries, ESLint, TypeScript, generated-contract consistency and the production build passed. OpenAPI and TypeScript were regenerated; a second generation produced an identical contract. The final production frontend was built into standard `.next` and is served on port 3000, with the API on port 8000.
- The local database was backed up to private ignored `work/chase201-before-v31-20260916.sql`. Transactional hash comparisons verified every pre-existing row unchanged: **28 matches, 32 drafts, 225 profiles**, all catalogs, offers, decisions, events, scorecards and receipts. Activation added only fictional-v4 and its 75 players/profiles. Local `CATALOG_VERSION` is now `fictional-v4`.
- A full local API smoke chase verified new offers, v3.1 routing, mode probabilities and scorecard reconciliation, finishing **203/3, won**. A browser check against the served production build confirmed fictional-v4, five Batting bars, no archetype headings, v3.1, three controls, Balanced after reload, exact percentages and no page errors or mobile overflow.

Windows permissions blocked the default pytest temp folder, so PostgreSQL tests used a fresh permitted temp directory. OneDrive locked the old `.next` build; it was preserved as `.next-before-v31-20260916` before rebuilding the standard output. Browser journeys used isolated ports 3001/8001 and a fresh test database. Upstream Authlib deprecation warnings remain. No external deployment was performed.

## V1 three-mode scope — 14 September 2026

New drafts use `fictional-v3` / `tradeoffs-v1`; new matches use `v3.0`. The 38-0 dark design is retained. See [current semantics](three-modes.md) and the [final 500-seed report](calibration-v3-final.json).

- **123 backend tests passed on PostgreSQL**, including concurrency, frozen v1/v2.0/v2.1 replays, active/saved contracts, populated legacy migrations, downgrade guards, attribute effects and 500 complete offer allocations. An additional allocation-corruption rollback test passed on SQLite, confirming no partial draft or session revision survives rejection.
- **10 frontend tests** and **4 full desktop/mobile browser journeys** passed, including WCAG A/AA checks, keyboard ordering, draft bars, exact mode counts, reloads, interruption controls, full-chase accounting and history claiming. Google exchange remains mocked in the isolated browser suite. Final screenshots were visually reviewed. OneDrive stalled the first browser run's artifact cleanup; all four journeys completed when artifacts were written to the permitted local visualization directory.
- **42,000 simulated chases/continuations** across 500 common seeds per comparison passed all active balance gates. Defensive, Balanced and Aggressive each have a useful context; specialist drafting beats highest OVR in suitable contexts. Worst Aggressive stress rates: 0% eight-over wins, 0.4474% 50-run two-over blocks, 0.6538% 30-run overs.
- Ruff, MyPy, import boundaries, generated OpenAPI/TypeScript contracts, ESLint and the production Next.js build passed. PostgreSQL upgrade → schema drift → downgrade to base → upgrade → schema drift passed on `chase201_migration_test`.
- The local game database was backed up to private, ignored `work/chase201-before-v3-20260914.sql`, then upgraded to `a42c83e5d016`. Hash comparisons verified all **20 pre-existing matches**, **150 existing profiles**, saved events/decisions, drafts and offers unchanged. The new immutable catalog was then activated.
- The local API was restarted on port 8000. A real-database smoke run verified every offer's styles, nondomination and rating limits, then completed a v3 chase at **202/6** with reconciled accounting. The production frontend was rebuilt into the standard `.next` directory and restarted on port 3000. Locked/incomplete build directories were archived within the workspace before the successful build.
- A final production browser check confirmed `fictional-v3`, `v3.0`, fifteen attribute bars across five options, exactly three controls, Balanced initially selected, an Aggressive decision, reload behavior, the dark theme and no horizontal overflow on desktop and mobile.

Upstream Authlib deprecation notices and a Windows pytest cache warning do not affect the passing checks. No external deployment was performed.

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
