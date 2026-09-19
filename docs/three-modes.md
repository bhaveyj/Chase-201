# Natural scoring and early Aggressive adaptation — v3.5

New `simple-v1` and `real-players-v1` drafts create **v3.5** matches. The default roster remains the [200-player real-players-v2 catalog](player-catalog.md), with the supplied names and ratings unchanged. Target 201, 120 legal balls, ten wickets and the production decision windows are unchanged. Saved matches use their recorded engine; tradeoff drafts still create v3.0 matches.

## Why late Aggressive scoring stalled

V3.4 removed the old paced score ceiling but retained a rule that prevented any single approach from scoring winning runs. At 197, this converted every sampled four and six into a dot. At 200, every scoring outcome became a dot. This produced normal or fast opening scoring followed by an artificial stall near the target.

The reported Aggressive-only game was reproduced exactly from its saved decisions and revision-specific HMAC random streams: **197/7 after 20 overs**. Comparing v3.5 with the same decision entropy produces **202/7 after 19.1 overs**, including 14 real runs in the final two overs. This comparison does not rewrite the saved result or guarantee the outcome of a fresh game.

## Scoring and approach risk

V3.5 retains every sampled outcome in both the distribution and accounting layers. A four scores four; a six scores six; wides and no-balls score one without consuming a legal ball. Any approach can earn winning runs. A chase ends immediately when the target is reached, ten wickets fall, or 120 legal balls are completed. There is no score ceiling, winning-run qualification, or later score correction.

Repeated Aggressive play is discouraged through bowling adaptation from the opening overs. The last 24 legal deliveries persist their approaches; Aggressive reaches full adaptation after 18 uses, compared with 24 in v3.4. Its repetition vector reduces boundary probability and increases dot and wicket probability more strongly. Each outcome retains positive probability throughout a live innings, except wickets on free hits. A one-delivery switch does not erase the history.

Defensive and Balanced retain their existing repetition coefficients. The initial approach vectors, shared phase priors and bowling inputs remain unchanged. Aggressive remains the highest wicket risk, Balanced the middle risk, and Defensive the lowest. Free-hit wicket risk remains exactly zero. The same probability distribution drives displayed estimates and seeded delivery sampling.

Player batting ratings remain excluded from outcomes, sustainable scoring, pressure and matchup feedback. Cards continue to show name, role and OVR. Bowler control, threat and style, setness, phase, recent dots, wickets, partnership and required rate still affect play.

## Verification and balance

The [v3.5 real-player report](calibration-v35-real-players.json) covers 500 randomized legal drafts, four policies across full chases and three continuation scenarios, deterministic replays, scorecard reconciliation and mode-risk comparisons at reconstructed deliveries. It measures the opening and final two overs for all three fixed approaches, including Aggressive, which the previous varied-outcome gate omitted.

Adaptive play wins **59.4%**, Balanced-only **36.2%**, Aggressive-only **25.6%**, and Defensive-only **0%** of full chases in this sample. Aggressive averages **104.826 runs in the first ten overs**, down from v3.4's **112.548** over the same seeds. Its final two-over samples include 124 fours and 90 sixes, alongside dots, singles, twos, wickets and extras. The report checks **410,098 non-free-hit states** and **3,311 free-hit states**; every acceptance check passes. These rates describe this catalog and documented policy, not every possible team or decision sequence.

The new acceptance checks require lower opening Aggressive scoring than v3.4 over common seeds, better adaptive-play results than fixed Aggressive, varied opening/closing outcomes for every fixed mode, and the historical burst limits. Accounting, replay, ordered risks and free hits are asserted during simulation. The old maximum-200 and zero-fixed-win requirements are archived with v3.4: they depended on the artificial block being removed here.

```powershell
.venv/Scripts/python.exe apps/api/scripts/balance_v35.py --seeds 500 --check --output docs/calibration-v35-real-players.json
```

Regression tests exercise every scoring outcome at 200 on the final legal ball, all outcomes at the reported 197-run stall with and without a free hit, early adaptation, persisted history after token switches, rating independence, reloads and API idempotent retries. Historical engine tests remain in place, including v3.4's original target guard.

## Activation

Restart the API and rebuild/restart the frontend together, then start a new chase. No catalog import or schema change is needed for this engine fix. The API contract and frontend accept v3.5 alongside every earlier version. Existing profiles, saved match snapshots, events, scorecards and receipts are preserved.

See [historical v3.4](three-modes-v34.md), [v3.2](three-modes-v32.md), [v3.1](three-modes-v31.md) and [v3.0](three-modes-v30.md).
