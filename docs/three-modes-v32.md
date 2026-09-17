# Historical v3.2: simple batting and approach variation

New `simple-v1` drafts use the existing immutable `fictional-v4` catalog and create `v3.2` matches. Saved v3.1 and all earlier matches retain their recorded engines. Existing `tradeoffs-v1` drafts still create v3.0 matches. Target 201, 20 overs, the XI rating limits and decision windows remain unchanged.

## Player cards

Simple cards show Batting as a plain label and number beside OVR; the horizontal bar has been removed. Historical profile cards retain their original attributes. The underlying batting ratings still affect scoring and survival. Neither OVR nor the player's bowling skills enter the batting kernel.

## Winning requires approach variation

A chase must use at least two different approaches on legal deliveries to score the winning runs. Defensive-only, Balanced-only and Aggressive-only chases cannot win, regardless of random seed, batting strength, boundaries, extras or free hits. A single-approach chase can still tie at 200. This rule is shown above the batting controls, with confirmation once variation is complete.

The server records `approaches_used` in the match snapshot. Selecting a radio button without playing does not count; wides and no-balls do not count as a new approach. A legal free-hit delivery counts. A second approach can qualify on the winning legal delivery itself. This requirement prevents a completely fixed approach; it does not require all three modes or a minimum number of switches.

Until qualification, an outcome that would reach or exceed the target is converted to a dot before any scorecard accounting. All other outcomes retain their probabilities. Next-delivery assessments include this rule, so displayed scoring, boundary and wicket estimates match actual sampling. Wicket probabilities retain Defensive < Balanced < Aggressive; all free-hit wicket probabilities remain zero. Legal-ball counts, extras, batter/bowler figures and events reconcile normally. The transition layer also enforces the rule independently of the sampler.

## Difficulty

The v3.1 batting coefficients, mode vectors and context effects are retained. Shared four/six phase priors are now **0.89 of v3.0** (previously 0.92), preserving relative phase effects. The balance target is **60–65% full-chase wins for sensible switching**. It is a simulation acceptance range for the documented policy and draft distribution, not a promise for every player or strategy.

The sensible policy chooses Aggressive on free hits or required rate above 11.5, Defensive below 7, and Balanced otherwise. Decisions occur only at the same windows exposed in the game. Draft picks are random legal choices, ordered by descending Batting; opponents use production selection.

| Policy | Full-chase wins | Acceptance |
| --- | ---: | ---: |
| Defensive only | 0% | Exactly 0% |
| Balanced only | 0% | Exactly 0% |
| Aggressive only | 0% | Exactly 0% |
| Sensible switching | 64.2% | 60–65% |

## Verification

```powershell
.venv/Scripts/python.exe apps/api/scripts/balance_v32.py --seeds 500 --check --output docs/calibration-v32-final.json
```

The [500-seed report](calibration-v32-final.json) covers 8,000 chases/continuations plus 500 deterministic replays across randomized legal XIs and opponents. Every gate passes. Scorecards reconcile at every reconstructed delivery. All 403,855 checked non-free-hit states retain ordered mode risk; 3,325 free-hit states have zero wicket probability.

Continuation scenarios begin at 161/7 after 14 overs, 101/3 after 10 overs, and 165/4 after 18 overs. Their constructed prefixes already use multiple approaches; their results measure the usefulness of each mode for the remaining situation, not permission to win a full chase with one approach. Fixed-mode full chases always begin with empty approach history.

Exhaustive near-target outcome tests, randomized full innings, forced unbroken sixes with maximum-strength batters, and API reload/idempotency tests independently cover the no-fixed-approach-win invariant. CI keeps both the frozen v3.1 calibration and the new v3.2 acceptance check.

## Compatibility and activation

No new database migration or catalog import is needed for installations already using `fictional-v4` / `simple-v1`. Restart the API and frontend, then start a new chase. Historical matches remain on their original rules. State and event changes are written through the existing revision, transaction and idempotency protections.

The three-mode API now accepts v3.0, v3.1 and v3.2 match responses. The optional state field `approaches_used` defaults to an empty list for older response snapshots; historical persisted states are not rewritten. Downgrade protection includes v3.2. See [historical v3.1 semantics](three-modes-v31.md) and [historical v3.0 semantics](three-modes-v30.md).
