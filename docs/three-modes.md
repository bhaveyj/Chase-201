# Simple batting and three modes — v3.1

New drafts use immutable catalog `fictional-v4` and selection rules `simple-v1`. They create `v3.1` matches. Existing `tradeoffs-v1` drafts still create `v3.0` matches; saved matches retain their recorded engine. Target 201, 20 overs, role composition and decision windows are unchanged.

## Batting and OVR

Draft cards show one Batting bar beside OVR. Batting affects scoring and survival; your batting mode controls how much risk the player takes. OVR sets draft eligibility and does not enter the batting kernel. There are no archetypes, hidden playstyle bonuses or player-by-mode interactions in v3.1. Historical draft cards retain their original attributes.

| Role | Core Batting | Star Batting |
| --- | ---: | ---: |
| Batter | 80 | 86 |
| Wicketkeeper | 78 | — |
| All-rounder | 77 | 83 |
| Bowler | 44 | — |

Within each role/tier cohort, ratings repeat the variations −3, −1, 0, +1, +3, preserving the stated average. OVR and all bowling attributes match fictional-v3 exactly. Older catalogs are never rewritten.

`simple-v1` retains five batters, one keeper, two all-rounders and three bowlers: one 90–92 OVR batter, one 90–92 OVR all-rounder and nine 78–85 OVR core players. Each draft has eleven disjoint offers of five unique players. Catalog imports validate role/tier capacity before writing any rows. No playstyle or non-dominance requirements apply. Selection, ordering, confirmation and match creation revalidate ratings, roles, offer membership and uniqueness. Stars may bat anywhere.

## Probability model

`chase_engine/v31/` owns v3.1. A batter has one ability input, `batting`. In dot/one/two/three/four/six/wicket order, its logit contribution is:

```text
(-0.30, 0.22, 0.26, 0.28, 0.30, 0.42, -0.50) × (batting − 75) / 25
```

Defensive and Balanced retain their v3.0 vectors. Aggressive retains its vector except the wicket logit is 0.85. Every mode applies a 0.8 setness scale. Bowler control/threat, pace/spin by phase, recent pressure, partnership and the chase equation still affect outcomes, independently of mode. Sustainable scoring derives from striker and partner Batting. Extras retain their independent bowler-controlled legality distribution.

Calibration reduced shared four/six prior weights to 0.92 of v3.0 in every phase, preserving relative phase effects and all requested batting/mode coefficients. The unadjusted randomized-draft benchmark was too easy: sensible 76.8%, Balanced 74.6%, Aggressive 47.4%. This shared baseline adjustment brings the final model inside every acceptance band.

| Mode | Purpose |
| --- | --- |
| Defensive | Protect wickets and rotate strike when the required rate permits. |
| Balanced | Combine strike rotation with selective boundaries. |
| Aggressive | Seek more boundaries with more dots and greater dismissal risk. |

Every delivery recalculates the distribution. Wickets and no-balls interrupt windows; free hits get a separate decision. On free hits the wicket logit is removed and all three modes have exactly zero risk. Cricket accounting, bowling quotas, extras, partnerships and strike rotation remain unchanged.

## API and compatibility

Player summaries add `battingRating` (1–100). Simple draft and v3.1 match summaries omit `battingControl`, `battingRotation`, `battingPower`, and `battingPlaystyle`. Historical cards continue to render their original attributes even when `battingRating` is present.

Both v3.0 and v3.1 use the three-mode API and frontend controls. Active assessments add `wicketProbability`, a full-precision 0–1 probability for the next delivery, including legality. The UI displays one decimal place: `Wicket risk: 5.2% · Low`. Free hits show `Wicket risk: 0% · None` for all modes. Scoring and boundary estimates remain qualitative. Historical idempotency receipts may omit the probability and retain their existing band. Completed matches have no active assessments.

The parent `chase_engine/` modules freeze v3.0. Nine complete golden replays captured before this change verify identical final states and event traces. `chase_engine/v2/` and `legacy.py` preserve v2.0/v2.1 and v1.0. HMAC seed derivation and stored decisions, events, states, results and catalogs are not rewritten. See [historical v3.0 semantics](three-modes-v30.md).

No schema migration is needed beyond existing head `a42c83e5d016`; the Batting column and version strings already support this model. Downgrade protection includes v3.1/simple-v1. To activate locally, seed catalogs with `python -m chase201.catalog`, set `CATALOG_VERSION=fictional-v4`, and restart the API. Existing drafts keep their original catalog and selection rules.

## Reproducible acceptance

```powershell
.venv/Scripts/python.exe apps/api/scripts/balance_v31.py --seeds 500 --check --output docs/calibration-v31-final.json
```

The checker requires at least 500 common seeds. Each seed randomly selects from legal five-player offers, orders the XI by Batting, and draws opponents using production selection. All four policies share the seed, XI and opponent. Sensible switching chooses Aggressive on free hits or required rate above 11.5, Defensive below 7, and Balanced otherwise, only at production decision windows.

Four scenarios retain target 201: full chase; 161/7 after 14 overs; 101/3 after 10 overs; 165/4 after 18 overs. There are 8,000 primary chases/continuations plus 500 deterministic full-chase replays. Wicket rates pool wickets over all deliveries in fixed-mode full chases, including extras and free hits, rather than averaging match rates.

| Policy | Full-chase wins | Required | Wickets per delivery | Required |
| --- | ---: | ---: | ---: | ---: |
| Defensive | 9.2% | — | 1.30% | 1–4% |
| Balanced | 62.4% | 55–75% | 4.84% | 3–7% |
| Aggressive | 41.8% | 25–50% | 9.45% | 8–13% |
| Sensible switching | 67.6% | 65–75% | 4.87% | — |

The final [500-seed report](calibration-v31-final.json) passes every gate. Defensive leads low pressure at 78.8%; Balanced leads fixed modes in medium pressure at 56.8%; Aggressive leads urgent finishes at 24.0%. No fixed mode leads every scenario. All 395,044 sampled non-free-hit states satisfy Defensive < Balanced < Aggressive wicket probability; all 3,299 sampled free-hit states have zero risk. Scorecards reconcile and all 500 replay traces match. Worst full-chase burst rates are 0% wins by eight overs, 0.239% 30-run overs and 0.190% 50-run two-over blocks (limits 1%, 4%, 5%). These are fictional-game measurements, not professional cricket forecasts.
