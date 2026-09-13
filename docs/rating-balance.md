# Rating caps and All Out balance — 13 September 2026

New XIs have one 90–92-rated batter, one 90–92-rated all-rounder, and nine 78–85-rated players. Those two star positions belong to the draft, so both can open or bat elsewhere after reordering. Each position still has five distinct choices; all 55 offers are disjoint, so earlier selections cannot make the XI impossible to finish. Public cards show the rating bands and selection counts in the existing dark theme.

The API validates the bands when selecting, setting the order, confirming and creating the match. The draft stores its selection-rule version. Migration `f31b72d4c905` marks existing drafts `open-v1`, without changing any saved team. New drafts use `balanced-v1` and the new immutable `fictional-v2` catalog. Custom catalogs need enough players in each band; no ratings are silently relabelled or clamped.

The cap alone did not resolve excessive slogging. Against the same median-strength opponent, the strongest legal team could still win 87.4% of fixed All Out chases under v2.0, with 50-run two-over blocks 20.0% of the time. This adversarial XI maximizes private batting power/control within each permitted band and puts its strongest batters first; ordinary players only see overall ratings.

Ruleset v2.1 reduces All Out's six logit from 1.90 to 1.55, power interaction from 1.25 to 0.30, control interaction from 1.05 to 0.50 and setness multiplier from 1.70 to 0.70. Its other outcome offsets are rebalanced to retain more sixes and greater wicket risk than Attack at the reference matchup. All Out remains the best chance when the last ball requires six; free hits still remove wicket risk. No hard score ceiling, scripted collapse or repeated-plan penalty is imposed. Other plans and cricket accounting are unchanged. Saved v2.0 matches retain their exact old coefficients and replay hashes.

## Reproducible checks

```powershell
.venv/Scripts/python.exe apps/api/scripts/draft_balance.py --seeds 500 --check --output docs/draft-balance-v21.json
.venv/Scripts/python.exe apps/api/scripts/calibrate.py --seeds 500 --catalog --check --output docs/calibration-v21.json
```

The [draft report](draft-balance-v21.json) uses the actual catalog profiles, offer generator and opposition selector. Common delivery seeds compare the unrestricted old XI, cap-only XI and capped v2.1 XI. A separate 500-seed run varies offers and opponents for every match, picks the highest displayed rating from each offer set, and orders by overall rating.

| All Out throughout | Win rate | Wins by 8 overs | 50+ runs in a two-over block |
| --- | ---: | ---: | ---: |
| Unrestricted top-rated XI, v2.0 | 95.8% | 11.8% | 24.0% |
| Strongest permitted XI, cap only | 87.4% | 10.0% | 20.0% |
| Strongest permitted XI, v2.1 | 37.4% | 0.0% | 3.4% |
| Randomized drafts and opponents, v2.1 | 15.8% | 0.0% | 1.5% |

Winning-ball percentiles for the strongest capped v2.1 XI are 59 / 69 / 80 (10th / median / 90th). Burst rates count fixed two-over blocks, including a partial final block. The randomized-draft burst figure is the mean of each match's block rate. These are fictional game simulations, not a claim that rare extreme scores are impossible.

The [general report](calibration-v21.json) retains the original uniform-attribute reference team, low/medium/high pressure scenarios, all five plans, two adaptive policies and the old catalog sensitivity benchmark for comparison. Fixed All Out has a low full-chase success rate on that ordinary reference team, as expected for sustained high dismissal risk; tactical switching remains useful. Actual limited drafts are covered separately above.

CI checks both reports with 300 seeds. The draft gate limits All Out wins to 70%, wins by eight overs to 1%, 50-run two-over blocks to 5% and 30-run overs to 4%, including the adversarial legal XI. Tests also cover injected out-of-band offers, validation at every team boundary, arbitrary batting order, complete unique offer sets, unchanged saved drafts, both v2 replay versions and guarded migrations.
