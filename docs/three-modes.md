# Rating-independent batting and varied repeated play — v3.4

New `simple-v1` drafts use `fictional-v4` and create `v3.4` matches. Target 201, 20 overs, XI rating limits and decision windows remain unchanged. Saved matches keep their recorded engine, including v3.3; existing `tradeoffs-v1` drafts still create v3.0 matches.

## Player cards and ability inputs

Simple cards show the player name, role and OVR. The Batting label, number and accessible description are removed, including when an older response still contains `battingRating`. Simple summaries omit Batting and the legacy control/rotation/power/playstyle fields. Historical profile cards retain their original attributes.

V3.4 does not read a player's Batting rating for outcomes, sustainable scoring, chase pressure or matchup feedback. The batting vector and sustainable attribute multiplier are zero; shared context calculations receive a neutral batter profile. OVR is not substituted for the removed ability input. Bowler control/threat/style, the selected approach, phase, setness, recent dots, wickets, partnership and required rate still affect play.

## Random scoring throughout the innings

V3.3 allowed 60 runs of initial headroom, then released its fixed-approach score ceiling at an almost constant rate per legal ball. This could produce easy opening runs followed by repeated forced singles in the final overs.

V3.4 removes those 150/180/185 scoring budgets and the per-ball ceiling. Repetition instead adjusts the probabilities of dots, singles, twos, threes, boundaries and wickets before each delivery is sampled. Adaptation begins with repeated legal deliveries in the opening overs, rather than after a 12-ball grace period, and uses the persisted recent 24-ball approach history. A token switch does not erase that history. Dots and boundaries remain possible in the final overs, provided the chase has not reached the winning-run guard.

Sampling continues to use the server's seeded random source. Reloads and idempotent retries preserve the same result; a new chase produces a new sequence. No extra client randomness or result rewriting is introduced.

## A single approach cannot win

Defensive-only, Balanced-only and Aggressive-only full chases cannot score winning runs. At least two approaches must be used on legal deliveries. Wides and no-balls do not qualify as a switch; a legal free hit does. A second approach can qualify on the winning legal delivery itself. A fixed approach may tie at 200.

The only scoring guard redirects a scoring outcome that would reach target 201 to a dot until variation qualifies. This guard applies to boundaries, extras and free hits in both the probability assessment and transition layer. Ordinary scoring outcomes below this guard are not converted into singles. Scorecards and events use the same final delivery outcome. Mode risk remains Defensive < Balanced < Aggressive, with zero wicket probability on free hits.

## Calibration and verification

Shared phase priors compensate for removing player-specific Batting ability; the approach vectors and contextual effects are retained. The adaptive-play acceptance target remains 60–65% full-chase wins in the documented randomized-draft benchmark. This is a benchmark range, not a guarantee for every strategy or team.

The final benchmark passes every gate: **63.2% adaptive-play wins**, **0% Defensive-only**, **0% Balanced-only**, and **0% Aggressive-only**. Defensive and Balanced both win **83.4%** of the qualified low-pressure continuations. Fixed-mode scoring remains varied in the opening and final three overs.

```powershell
.venv/Scripts/python.exe apps/api/scripts/balance_v34.py --seeds 500 --check --output docs/calibration-v34-final.json
```

The [500-seed report](calibration-v34-final.json) measures fixed approaches and adaptive play across full chases and three continuation scenarios, checks scorecards and mode risks at every reconstructed delivery, and compares deterministic replays. It also records outcome counts separately for the opening and final three overs and requires varied Defensive/Balanced outcomes in both.

Draft choices are random legal selections, ordered by descending OVR. Adaptive play uses Aggressive on free hits, Defensive below required rate 7, otherwise alternates Balanced/Aggressive in response to required rate and recent approach history at production decision windows. Continuation prefixes already use multiple approaches; their outcomes measure situational usefulness rather than bypassing the full-chase qualification requirement.

Regression tests compare ratings 1 and 100 against identical seeds, require identical contexts/distributions/full traces, exercise all outcomes at the target guard, verify late boundaries remain boundaries, and cover reloads and API idempotency. Earlier version tests remain in place.

## Activation

Restart the API and frontend, then start a new chase. Existing `fictional-v4` installations need no catalog reimport or schema change. The generated API contract accepts v3.4 alongside earlier versions; downgrade protection includes v3.4. Saved matches and receipts are not rewritten.

See [historical v3.2](three-modes-v32.md), [v3.1](three-modes-v31.md) and [v3.0](three-modes-v30.md).
