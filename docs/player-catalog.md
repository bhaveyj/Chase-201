# Real-player draft catalog

`real-players-v2` is the default static roster, using `real-players-v1` selection rules: **200 unique players from 17 countries**. It contains 52 batters, 31 wicketkeepers, 55 all-rounders and 62 bowlers.

The supplied list contained 141 rows and 139 unique players. Devon Conway and Jos Buttler each appeared twice with identical roles and ratings; each now has one identity. All 139 supplied players retain their exact names, roles and ratings. The other 61 identities were checked against official squad lists on 19 September 2026.

The [editable JSON roster](../apps/api/src/chase201/data/real-players-v2.json) records country, role, 1–100 game rating, bowling style, identity source and whether the rating came from the user or editorial judgment. Stable name-based IDs avoid duplicates across offers. Every player can appear in a legal draft. This is a franchise/international game pool, rather than a declaration of current international eligibility; internationally retired players in the supplied list remain included.

## Research and rating method

- [IPL 2026 retained squads](https://www.iplt20.com/news/article/tata-ipl-2026-player-retentions-announced): Indian domestic players and franchise specialists, including Hardik Pandya, Sunil Narine, Sai Sudharsan, MS Dhoni and Yuzvendra Chahal.
- [ICC Men's T20 World Cup 2026 squads](https://www.icc-cricket.com/tournaments/mens-t20-world-cup-2026/news/all-the-squads-for-icc-men-s-t20-world-cup-2026): international and associate-country additions, including Josh Inglis, Scott Edwards, Aasif Sheikh, Dipendra Singh Airee and Muhammad Waseem.
- [ICC post-tournament rankings context](https://www.icc-cricket.com/tournaments/mens-t20-world-cup-2026/news/india-batters-win-rankings-boost-for-t20-world-cup-heroics): broad context for elite T20 players; these ranking points are not copied into the game's ratings.

Added OVR ratings are project-authored estimates on the user's scale, weighing established T20 impact, specialist ability and experience. They are not official ICC ratings, scraped statistics or predictions. Bowling inputs are deterministic game estimates based on role and OVR, with explicit pace/spin styles; they are not measured control/threat statistics. V3.4 and the current v3.5 engine ignore individual batting ratings, while bowling inputs still affect play. No player photos or team logos are bundled.

The calibrated v2 profiles keep role-adjusted bowling control and reduce bowling threat by three points to retain the game's existing difficulty envelope with the stronger real-player pool. Names, roles and displayed ratings are identical to v1. Already imported catalogs and their profiles remain immutable.

The historical v3.4 [500-seed calibration](calibration-real-players-v2.json) measures **62.8% adaptive-play wins** and **0% wins for each fixed approach**. Qualified low-pressure continuations give Defensive **82.6%** and Balanced **84.0%** wins. For this larger roster, the useful-plan comparison accepts a scenario with at least 5% wins when the plan is within 1.96 paired standard errors of the best fixed plan over common seeds. The legacy fictional benchmark retains its exact observed-best criterion. These figures include v3.4's artificial winning-run block and describe saved v3.4 games. See [current v3.5 scoring and verification](three-modes.md) for removal of that block and earlier Aggressive adaptation. The catalog profiles are unchanged by this engine fix.

```powershell
.venv/Scripts/python.exe apps/api/scripts/balance_v34.py --catalog real-players-v2 --seeds 500 --check --output docs/calibration-real-players-v2.json
```

## Draft rules

The XI remains five batters, one keeper, two all-rounders and three bowlers, with five disjoint choices per position. The new version preserves the user's ratings without excluding elite keepers/bowlers or the 77–79-rated entries.

| Positions | Rating range | Picks |
| --- | --- | --- |
| Star batter and star all-rounder | 90–100 | 2 |
| Other batters and all-rounder | 75–89 | 5 |
| Keeper and bowlers | 75–100 | 4 |

Server-side offer creation, selection, batting-order confirmation and match creation all use these versioned limits. Saved fictional drafts retain their previous rules and profiles. Existing matches continue to use their recorded engine.

## Import and activation

From `apps/api`, run `python -m chase201.catalog`. The command imports only the real-player catalog by default and can safely be repeated. Set `CATALOG_VERSION=real-players-v2` and restart the API. Start a new chase to receive real players. `--legacy-fixtures` is available for historical benchmarks; it is not used for the default game.

The JSON is included in the installed Python package and Docker image. Imports are immutable: roster edits require a new catalog version. Existing production catalog-approval checks remain in force; the bundled dataset does not assert licensing approval.

For a production frontend preview, rebuild with `npm run build` before restarting so the new role-specific limits and counters are included. The current local preview uses `.next-v35` on port 3000 and the API on port 8000.
