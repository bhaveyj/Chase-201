# Historical simulation semantics — ruleset v2.0

**New simple-v1 matches use v3.1.** See [simple batting, three modes and current acceptance](three-modes.md). This page records the frozen historical v2 behavior.

**Historical version: v2.1.** The architecture and accounting below still apply; the original v2.0 calibration table is retained as a historical reference. See [rating caps and All Out tuning](rating-balance.md) for current coefficients, draft rules and the v2.1 reports. Existing v2.0 matches keep their frozen behavior.

New matches use five batting plans and a delivery-level engine. Saved `v1.0` matches continue through the frozen original engine and retain their original controls, schedule, HMAC seed derivation and outcomes.

## Modules and ownership

The `chase_engine` package performs no I/O and imports no application/framework packages. `types.py` defines frozen player, strategy, context, distribution and window inputs plus owned scorecard snapshots; `rules.py` holds frozen, versioned coefficients; `context.py` derives cricket context; `probabilities.py` constructs outcome logits and qualitative assessments; `sampling.py` samples categorical outcomes; `transitions.py` applies one delivery; `simulation.py` runs windows and aggregates their events. `engine.py` is the public facade. `legacy.py` preserves the complete old implementation, verified against pre-change replay hashes.

`simulate_step` deep-copies the supplied snapshot and never mutates caller state or player inputs. Only its owned copy is mutated by delivery accounting. Application services load immutable catalog profiles, select the match's ruleset, inject a revision-specific `random.Random` seeded with HMAC of the private match seed, ID, revision and version, and atomically persist state, decisions, events and scorecards. Previous strategy choices are retained for analytics; there is no repetition penalty.

## Decision windows

| Overs | Scheduled window |
| --- | --- |
| 1–12 | Two overs (12 legal balls) |
| 13–16 | One over (6 legal balls) |
| 17–18 | Three legal balls |
| 19–20 | One delivery, including an extra |

There are 26 scheduled decisions in a complete 120-ball innings before interruptions. A wicket, no-ball or innings completion stops a window immediately. A free hit gets one delivery and its own batting-plan selection; a wide preserves the free hit and opens another decision. Ordinary boundaries and singles continue early windows. Wides use no legal-ball allowance. After an interruption, the next scheduled window ends at the original boundary: a wicket on ball 5 leaves seven legal balls to the 12-ball boundary. The UI labels partial windows in balls and displays both upcoming bowlers when a plan spans two overs.

Every internal delivery recalculates striker, bowler, attributes, setness, pressure and the distribution. A window produces one persisted presentation event plus its ordered delivery trace. Delivery events are used for free hits and the final two overs. Events include the selected plan, interruption reason and qualitative context before/after the window.

## Outcome kernel

1. Sample legality: legal, wide or no-ball. These probabilities depend on bowler control and their own limits; batting aggression never changes their normalization.
2. On a legal delivery, sample dot, one, two, three, four, six or wicket. Start with the phase's base weights converted to logits. Add separate vectors for the plan, batter control/rotation/power, bowler control/threat, player × plan interactions, small pace/spin × phase/plan effects, setness, recent pressure, chase pressure and partnership stability. Normalize with softmax.

Free hits remove the wicket logit and renormalize all remaining outcomes. Logits and wicket probability have safety limits. The injected random source must return finite values in `[0, 1)`; pathological sources that cannot produce legal play are rejected after a bounded number of deliveries. No extra luck meter, generic momentum, confidence or fatigue is stored.

| Plan | Character and consequence |
| --- | --- |
| Preserve | Lowest dismissal and boundary rates; many dots and a low scoring ceiling. Useful to protect an unset batter through a threatening spell, but required rate rises if held too long. |
| Rotate | Directly favors singles, twos and threes, reduces dots and wicket risk. Rotation specialists benefit most; an escalating equation can exceed its scoring ceiling. |
| Balanced | Natural matchup distribution with small stabilizing adjustments. Adaptable but can be too slow late. |
| Attack | Raises boundaries, misses and wickets while reducing singles. Power and setness help; weak control and threatening bowling increase collapse risk. |
| All-out Attack | Highest six and wicket rates in the neutral benchmark, and more dots than Attack. Large variance can rescue an urgent finish; sustained use exposes unset batters and the tail. |

The same plan's final probabilities change with every delivery. Exact percentages and hidden attributes stay on the server. The browser receives scoring, boundary and wicket-risk bands for the next delivery against the current bowler; a two-over plan's later distributions naturally differ.

## Context and profiles

Persist only the last six deliveries (including extras), partnership runs/legal balls and the last wicket's legal-ball number alongside the existing scorecard. Partnership extras count as runs; a wicket resets the partnership counters.

Setness grows from an individual batter's balls faced and caps at 15: New below six, Settling through 14, then Set. A new arrival starts unset. Recent pressure reflects consecutive dots, dots in the six-delivery buffer and a recent wicket. Chase pressure compares required rate with a sustainable rate derived from both current batters, with small wicket/remaining-ball adjustments. A partnership earns a small stability effect as it survives and scores. Tail quality already lives in batter attributes; there is no large generic wickets-lost scoring penalty. Current run rate remains derived display information.

Hidden batting attributes are control, rotation and power; hidden bowling attributes are control and threat, with PACE/SPIN style. Only overall rating, role, bowler style, setness, pressure and qualitative assessments are public. Legacy catalogs receive a deterministic, player-ID-based backfill; original batting/bowling values are unchanged for old matches. New imports can supply all six expanded fields, validated to their domain/range, and unspecified fields use the same backfill. Fictional identities and existing overall ratings are preserved.

The user's bowling ability does not grant a chase bonus: the user never bowls. Drafted bowlers matter through their batting profiles when the tail is exposed. Opposition bowlers directly affect dots, extras, boundaries and dismissals.

## Cricket accounting

- Target 201 wins immediately; a terminal 200 ties with no super over. Ten wickets or 120 legal balls ends the innings.
- Odd bat runs (including three) swap strike; over completion swaps it again. A wicket replaces the striker with the next batter unless it ends the innings.
- Wides/no-balls each add one extra and one bowler-conceded run without consuming a legal ball or ball faced. No-ball bat runs, byes, leg-byes, run-outs and dismissal types remain outside this ruleset.
- No-balls grant a free hit; further illegal deliveries preserve it. The next legal delivery consumes it and cannot dismiss a batter.
- Five eligible opposition bowlers rotate by over, ordered by bowling threat then control and ID. Maximum 24 legal balls per bowler; no consecutive overs. The opponent XI varies between matches.
- Team runs reconcile to batting runs plus extras and bowling runs conceded. Legal balls and wickets reconcile across every scorecard.

## Calibration and freeze

From the repository root:

```powershell
.venv/Scripts/python.exe apps/api/scripts/calibrate.py --seeds 500 --catalog --check --output docs/calibration-v2.json
.venv/Scripts/python.exe apps/api/scripts/baseline.py --seeds 500 --output docs/legacy-baseline.json
```

The [v2 report](calibration-v2.json) contains common-seed comparisons of all five fixed plans and two simple adaptive policies. Metrics include wins, mean/percentile scores, score/outcome variance, dot/single/boundary/six/wicket/extra rates, phase run rates, first-wicket histograms, decision counts and strategy usage. All 75 catalog players are assessed as batters, eligible bowlers are also assessed as bowlers, and strongest/weakest catalog XIs are compared. It is a fictional gameplay benchmark, not professional cricket forecasting.

The benchmark uses batting attributes 82 for the first eight players, 46 for the tail and opposition bowling attributes 80, with alternating pace/spin styles. Situations all retain target 201: fresh innings; 161/7 after 14 overs; 101/3 after 10 overs; and 165/4 after 18 overs. Scenario prefixes are constructed through legal scorecard transitions.

| Fixed/adaptive policy | Full chase | Low pressure | Medium pressure | High pressure |
| --- | ---: | ---: | ---: | ---: |
| Preserve | 0.0% | 1.0% | 0.0% | 0.0% |
| Rotate | 20.8% | 53.0% | 28.4% | 0.4% |
| Balanced | 66.6% | 46.6% | 64.4% | 5.4% |
| Attack | 59.0% | 24.4% | 66.8% | 34.6% |
| All-out Attack | 28.0% | 7.4% | 46.6% | 47.0% |
| Adapt to rate | 74.0% | 55.0% | 73.4% | 46.6% |
| Adapt to context | 78.6% | 46.8% | 73.2% | 46.4% |

These are 500 common seeds. Fixed Preserve is deliberately insufficient for an entire demanding chase; its benefit is temporary wicket protection. Adaptive policies change plans with the equation/setness and use free hits; they do not predict exact outcomes. Differences of a few percentage points are sampling noise. The strongest and weakest catalog XIs win 97.4% and 20.8% respectively under the same adaptive policy against the reference opponent; those extreme drafts are a sensitivity test, not typical game odds.

CI uses 300 seeds and broad neutral envelopes (20–80% win rate; 15–42% dots; 15–45% singles; 15–42% boundaries; 3–20% sixes; 2.5–12% wickets; 1–6% extras; 15–45 mean decisions). It fails if a fixed plan is within five percentage points of best across every pressure scenario, if any tested policy strictly beats every alternative by more than five points in all scenarios, if low-pressure plans lack separation, or if full-catalog quality/risk separation disappears. An adaptive policy being competitive in several situations is expected. Statistical envelopes are regression alarms, not proof that every possible policy is balanced.

All behavioral coefficients, assessment thresholds, schedule and interruption settings live in frozen `Ruleset` tuples/dataclasses with a read-only registry. The report records a configuration SHA-256; frozen per-plan seeded traces live in `tests/fixtures/v2-replay.json`. Any shipped coefficient or behavior change must introduce a new version and retain the earlier implementation/configuration for its saved matches. Update envelopes only with documented evidence. The [legacy baseline](legacy-baseline.json) preserves distributions and three complete replay hashes for each of the nine old combinations.
