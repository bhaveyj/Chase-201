# Historical v3.0: three modes and profile tradeoffs

Historical tradeoffs-v1 chases use engine `v3.0`, catalog `fictional-v3`, and selection rules `tradeoffs-v1`. V1 is the product scope; the engine number is independent. The 38-0 design, target 201, 20 overs, role composition and decision schedule are preserved.

## Modes

The active `StrategyId` contains exactly `DEFENSIVE`, `BALANCED`, and `AGGRESSIVE`. Balanced is initially selected, including after reload and entry into another match. Wickets and free hits retain the same three choices.

- **Defensive** converts potential dots into controlled singles and twos, reduces dismissal risk, and sacrifices boundaries. It is useful when the required rate allows wicket protection.
- **Balanced** combines strike rotation with selective boundaries. Rotation has its strongest relative interaction here.
- **Aggressive** increases boundaries, failed attacking shots and dismissals. Power helps its boundary potential; weak control and threatening bowling make sustained aggression dangerous.

Every delivery recalculates the distribution from the chosen mode, the current striker and partner, opposing bowler, phase, setness, recent deliveries, partnership and chase equation. Playstyles add no coefficients or bonuses. A user's bowling attributes and OVR never enter the batting kernel. All randomness, coefficients and numerical outcome probabilities remain server-side.

## Profiles and offers

The immutable new catalog uses deliberate profiles with a fixed batting strength total per role and rating tier. Core baselines are 72 per attribute for batters, 70 for keepers, 69 for all-rounders and 44 for specialist bowlers. Stars add six per attribute to the baseline. Specialization and small cohort variations redistribute the total without adding strength. OVR includes role ability and is not an automatic batting multiplier.

Anchor leads with Control; Rotator leads with Rotation; Hitter leads with Power. Each has a visible weakness. Draft cards expose exactly those engine attributes, labeled on a common 0–100 scale, and explain their effects. The full values and playstyle are included in each card's accessible name. OVR remains visible in a smaller badge.

Before any catalog rows are inserted, exact partition search proves an allocation of eleven disjoint, five-player offers. Every offer must have all three styles, five distinct profiles, and no option equal or worse than another across all three attributes. The search backtracks across slots; it never relaxes these requirements. Complete allocations are persisted with immutable catalog metadata. Runtime validation rechecks the entire allocation before creating offers and shuffles only interchangeable role/tier slots and card order.

The XI retains five batters, one keeper, two all-rounders and three bowlers: exactly one 90–92 batter, one 90–92 all-rounder and nine 78–85 players. Any selection path through the allocation is unique and legal. All team boundaries revalidate ratings and roles, and stars can bat anywhere.

## Compatibility and persistence

`chase_engine/legacy.py` remains the original v1 engine. `chase_engine/v2/` freezes the complete v2.0/v2.1 implementations, strategy order and coefficients; golden replay hashes are unchanged. Saved versions select their own engine for simulation, assessments, windows and context. The UI keeps separate state and components for historical controls.

Active and saved match/assessment/event schemas are separate. Old strategy names are rejected when submitted to v3 matches, including via the common compatibility endpoint. Historical intent/risk requests remain available only for v1 saves; v2 requests use their own five-value enum. Older idempotency receipts remain readable through optional display fields. Existing drafts retain their selection rules and offers, and catalogs/profiles are never rewritten.

Migration `a42c83e5d016` adds immutable catalog allocation metadata and expands stored decision constraints. Downgrade refuses to discard v3 matches, drafts, catalogs or decisions. OpenAPI and generated TypeScript types describe both active and historical contracts explicitly.

## Reproducible acceptance

Run `python apps/api/scripts/balance_v3.py --seeds 500 --check --output docs/calibration-v3-final.json` from the repository root. The check refuses fewer than 500 seeds.

The report compares 500 common delivery seeds for each of four drafting policies (highest OVR, Control, Rotation and Power), three fixed modes, and four situations. Each seed generates a complete ordinary offer allocation and opposition. Three specialist XIs also stress the strongest legal Control, Rotation and Power profiles, with all three modes in all four situations. This covers 42,000 simulated chases or chase continuations. The strong XIs obey role/rating/uniqueness constraints while deliberately exploring catalog maxima beyond a single offer draw.

Situations keep target 201: fresh innings; 161/7 after 14 overs; 101/3 after 10 overs; and 165/4 after 18 overs. Prefixes are constructed through cricket scorecard transitions. Gates require a useful winning context for every mode, no fixed mode leading everywhere, a material specialist-drafting advantage over highest OVR in at least one context, and Aggressive burst limits for every ordinary/strong drafting policy: eight-over wins ≤1%, 50-run two-over blocks ≤5%, and 30-run overs ≤4%. Block and over rates count observed blocks/overs; ordinary metrics average each seed's rate, while strong-XI metrics pool observations.

These are fictional game balance measurements, not forecasts of professional cricket.

The final [500-seed report](calibration-v3-final.json) passes every gate. With highest-OVR drafting, Defensive wins 47.8% of the low-pressure scenario, Balanced wins 28.4% of medium-pressure chases, and Aggressive wins 8.6% of urgent finishes. Control-aware drafting raises Defensive's low-pressure wins to 72.6%; Power-aware drafting raises Aggressive's urgent-finish wins to 23.8%. No fixed mode or highest-OVR drafting policy leads every context. Across all ordinary and strong-XI Aggressive stress cases, the worst measured rates are 0% eight-over wins, 0.4474% 50-run two-over blocks, and 0.6538% 30-run overs, below all required limits.
