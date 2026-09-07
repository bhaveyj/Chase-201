# V1 simulation semantics

The engine accepts dataclasses, a ruleset, and an injected random source. It reads no database, network, filesystem, clock or global random state. `import-linter` forbids dependencies on the application, FastAPI, SQLAlchemy and Pydantic.

## Decision schedule

| Overs | Window |
| --- | --- |
| 1–6 | 18 legal balls |
| 7–12 | 12 legal balls |
| 13–16 | 6 legal balls |
| 17–18 | 3 legal balls |
| 19–20 | One delivery, including a wide or no-ball |

The finish exposes every delivery. An illegal delivery leaves the legal-ball count unchanged and gives the captain another decision. Earlier windows continue until their legal-ball allowance is reached or the innings ends.

## Aggregate play

Early windows use a geometric draw for the number of non-rotating scoring outcomes before a single, wicket, wide or no-ball. A multinomial draw allocates that block’s dots, twos, fours and sixes directly to the striker; it does not generate a hidden delivery sequence. The terminating strike-change/extra/dismissal event is retained and resolved. Blocks stop at over boundaries, a free hit, and a conservative maximum-score bound near the target. Close to victory, one-outcome blocks preserve an immediate finish. Each early decision emits one aggregate event.

Outcome weights respond to striker batting strength, bowler strength, phase, wickets lost, required-rate pressure, intent and risk focus. The API derives a revision-specific random stream using HMAC of the private match seed, ID, revision and ruleset version. Seeds and hidden coefficients never cross the response boundary.

## Cricket accounting

- 201 or more wins immediately. A terminal score of 200 ties; no super over. Any lower terminal score loses. Ten wickets or 120 legal balls ends the innings.
- Odd bat runs swap the strike; over completion swaps it again. A wicket replaces the striker with the next available batter. The final wicket leaves a terminal state without introducing a twelfth player.
- Wides and no-balls each add one extra and one bowler-conceded run, without using a legal ball or a batter’s ball faced. V1 no-balls are penalty-only: combined no-ball bat runs, byes, leg-byes and run-outs are not modeled.
- A no-ball grants a free hit; further wides/no-balls preserve it. A legal delivery consumes it and cannot dismiss a batter. V1 dismissals are bowler-attributed; no run-out exception is needed.
- The five eligible opposition bowlers rotate by over in a deterministic schedule, ordered by hidden bowling strength. Each bowls at most four overs, never consecutive overs. The AI XI itself varies between matches.
- Runs equal batting runs plus extras, and also equal bowler-conceded runs. Legal balls reconcile between team, batting and bowling records. Dismissals reconcile between wickets, batter status and bowler wickets.

## Calibration

Run `python scripts/calibrate.py --seeds 1000` from `apps/api` with the environment installed. For the version `v1.0` fictional benchmark (top-eight batting 82, tail batting 46, opposition bowling 80), the verified 1,000-seed report is:

| Fixed policy | Win rate | First 18 balls: runs | First 18 balls: wickets |
| --- | ---: | ---: | ---: |
| Defend / protect wickets | 0.7% | 24.42 | 0.22 |
| Rotate / balanced | 57.3% | 32.57 | 0.90 |
| Attack / maximize runs | 53.8% | 38.71 | 1.61 |

The fixed-horizon comparison avoids censoring from successful chases ending early. Aggression increases both scoring and wicket risk. Defensive play can preserve wickets but is insufficient as an unchanged policy throughout a 201 chase. These are development benchmark odds, not a guarantee for every draft or evidence about real players. Recalibrate an approved catalog before launch; ship tuning under a new ruleset version and preserve old implementations for in-progress matches.
