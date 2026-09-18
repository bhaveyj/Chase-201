"""Common-seed checks for natural scoring and early Aggressive adaptation.

The old zero-win and maximum-200 gates are deliberately historical: v3.5
allows any approach to earn winning runs through sampled cricket deliveries.
"""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from balance_v34 import POLICIES, SCENARIOS, catalog, choose, reconcile

from chase201.catalog import REAL_CATALOG_VERSION
from chase201.draft_rules import REAL_SELECTION, draft_offers, opponent_players
from chase_engine.v31.types import Outcome, StrategyId
from chase_engine.v34 import engine as historical
from chase_engine.v34.transitions import apply_delivery as historical_apply
from chase_engine.v35 import engine
from chase_engine.v35.transitions import apply_delivery


def run(seed, team, opponent, policy, scenario, version=engine, audit=True):
    state = version.initial_state(team, opponent)
    apply = historical_apply if version is historical else apply_delivery
    balls, runs, wickets = SCENARIOS[scenario]
    for _ in range(wickets):
        apply(state, Outcome.WICKET, strategy=StrategyId.BALANCED)
    for i in range(balls - wickets):
        value = runs // (balls - wickets) + (i < runs % (balls - wickets))
        apply(
            state,
            list(Outcome)[value],
            strategy=StrategyId.DEFENSIVE if i % 12 < 6 else StrategyId.BALANCED,
        )
    rng = random.Random(seed)
    opponents = {p.id: p for p in opponent}
    opening, closing, outcomes, overs = Counter(), Counter(), Counter(), Counter()
    first_ten, risks_checked, free_hits = 0, 0, 0
    trace = hashlib.sha256()
    while state.status == "LIVE":
        mode = choose(policy, state)
        step = version.simulate_step(
            state,
            team,
            opponent,
            mode,
            version.window_for(state).max_legal_balls,
            version.DEFAULT_RULES,
            rng,
        )
        trace.update(json.dumps(asdict(step), sort_keys=True).encode())
        replay = version.GameState.from_dict(asdict(state))
        for delivery in step.events[0]["deliveries"]:
            if audit:
                profiles = (
                    team[replay.striker],
                    team[replay.non_striker],
                    opponents[version.current_bowler(replay).player_id],
                )
                risks = [
                    version.distribution(replay, *profiles, s).wicket_probability
                    for s in StrategyId
                ]
                if replay.free_hit:
                    assert risks == [0, 0, 0]
                    free_hits += 1
                else:
                    assert 0 < risks[0] < risks[1] < risks[2] < 1, risks
                    risks_checked += 1
                assert apply(replay, Outcome(delivery["outcome"]), strategy=mode) == delivery
            outcomes[delivery["outcome"]] += 1
            overs[delivery["fromBall"] // 6] += delivery["runs"]
            if delivery["fromBall"] < 18:
                opening[delivery["outcome"]] += 1
            if delivery["fromBall"] < 60:
                first_ten += delivery["runs"]
            if delivery["fromBall"] >= 108:
                closing[delivery["outcome"]] += 1
        if audit:
            assert replay == step.state
        state = step.state
        reconcile(state)
    assert (state.status == "WON") == (state.runs >= 201)
    return {
        "won": state.status == "WON",
        "score": state.runs,
        "wickets": state.wickets,
        "firstTenRuns": first_ten,
        "opening": opening,
        "closing": closing,
        "outcomes": outcomes,
        "thirtyRunOvers": sum(r >= 30 for r in overs.values()),
        "overs": len(overs),
        "winsByEightOvers": state.status == "WON" and state.balls <= 48,
        "risksChecked": risks_checked,
        "freeHits": free_hits,
        "trace": trace.hexdigest(),
    }


def summarize(rows):
    opening, closing, outcomes = Counter(), Counter(), Counter()
    for row in rows:
        opening.update(row["opening"])
        closing.update(row["closing"])
        outcomes.update(row["outcomes"])
    return {
        "winRate": mean(r["won"] for r in rows),
        "meanScore": mean(r["score"] for r in rows),
        "meanWickets": mean(r["wickets"] for r in rows),
        "meanFirstTenRuns": mean(r["firstTenRuns"] for r in rows),
        "maxScore": max(r["score"] for r in rows),
        "firstThreeOvers": dict(opening),
        "lastTwoOvers": dict(closing),
        "outcomeCounts": dict(outcomes),
        "thirtyRunOverRate": sum(r["thirtyRunOvers"] for r in rows) / sum(r["overs"] for r in rows),
        "winsByEightOvers": mean(r["winsByEightOvers"] for r in rows),
    }


def characterize(seeds):
    players, profiles = catalog(REAL_CATALOG_VERSION)
    samples = defaultdict(list)
    previous = []
    for seed in range(seeds):
        rng = random.Random(seed)
        picks = [rng.choice(g) for g in draft_offers(players, rng, REAL_SELECTION)]
        team = sorted([profiles[p.id] for p in picks], key=lambda p: p.overall, reverse=True)
        opponent = [profiles[p.id] for p in opponent_players(players, random.Random(seed + 10000))]
        for scenario in SCENARIOS:
            for policy in POLICIES:
                row = run(seed, team, opponent, policy, scenario)
                samples[scenario, policy].append(row)
                if scenario == "full_chase" and policy == "SENSIBLE":
                    assert (
                        row["trace"]
                        == run(seed, team, opponent, policy, scenario, audit=False)["trace"]
                    )
        previous.append(
            run(seed, team, opponent, "AGGRESSIVE", "full_chase", version=historical, audit=False)
        )
        if (seed + 1) % 50 == 0:
            print(f"Checked {seed + 1}/{seeds} common seeds", flush=True)
    results = {
        scenario: {p: summarize(samples[scenario, p]) for p in POLICIES} for scenario in SCENARIOS
    }
    old = summarize(previous)
    failures = []
    full = results["full_chase"]
    if full["AGGRESSIVE"]["meanFirstTenRuns"] >= old["meanFirstTenRuns"]:
        failures.append("Repeated Aggressive did not reduce early scoring over common seeds")
    if full["AGGRESSIVE"]["winRate"] >= full["SENSIBLE"]["winRate"]:
        failures.append("Repeated Aggressive is as successful as adaptive play")
    for policy in POLICIES:
        if full[policy]["winsByEightOvers"] > 0.01 or full[policy]["thirtyRunOverRate"] > 0.04:
            failures.append(f"{policy} exceeds the historical burst limits")
    for policy in POLICIES[:3]:
        for phase in ("firstThreeOvers", "lastTwoOvers"):
            if not all(
                full[policy][phase].get(outcome, 0)
                for outcome in ("DOT", "ONE", "TWO", "FOUR", "SIX", "WICKET")
            ):
                failures.append(f"{policy} lacks varied sampled outcomes in {phase}")
    return {
        "ruleset": "v3.5",
        "catalog": REAL_CATALOG_VERSION,
        "seeds": seeds,
        "rulesetSha256": hashlib.sha256(
            json.dumps(asdict(engine.DEFAULT_RULES), sort_keys=True).encode()
        ).hexdigest(),
        "scoringRule": "Every sampled outcome is retained, including winning runs for a single approach. No target guard, per-ball ceiling or end-of-innings score correction.",
        "adaptationRule": "Legal-delivery approach frequency in the persisted last 24 balls; Aggressive reaches full adaptation at 18 uses. Token switches do not clear this history.",
        "scenarioPrefixes": SCENARIOS,
        "drafting": "Random legal real-player picks; batting order descending OVR; production opponent selection with seed + 10000.",
        "policy": "The historical SENSIBLE required-rate/free-hit/history policy and production decision windows, unchanged for comparison.",
        "acceptance": "Ordered wicket risks, zero-risk free hits, scorecard accounting, seeded replay, varied opening/closing scoring for all modes, historical burst limits, lower opening Aggressive scoring and more successful adaptive play over common seeds.",
        "scenarios": results,
        "historicalAggressive": old,
        "nonFreeHitStatesChecked": sum(
            r["risksChecked"] for rows in samples.values() for r in rows
        ),
        "freeHitStatesChecked": sum(r["freeHits"] for rows in samples.values() for r in rows),
        "deterministicReplays": seeds,
        "balanceFailures": failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.seeds < 1 or (args.check and args.seeds < 500):
        parser.error("Acceptance requires at least 500 common seeds")
    report = characterize(args.seeds)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "fullChase": report["scenarios"]["full_chase"],
                "balanceFailures": report["balanceFailures"],
            }
        )
    )
    if args.check and report["balanceFailures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
