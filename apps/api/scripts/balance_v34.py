"""Common-seed v3.4 acceptance with randomized legal drafts and opponents.

All modes see the same XI, opponent and simulation seed. Sensible switching uses
only required rate and free-hit state, at the same decision windows as the UI.
"""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict
from math import sqrt
from pathlib import Path
from statistics import mean

from chase201.catalog import REAL_CATALOG_VERSION, real_players, simple_fictional_players
from chase201.draft_rules import REAL_SELECTION, SIMPLE_SELECTION, draft_offers, opponent_players
from chase201.models import Player
from chase_engine.v31.types import BowlingStyle, Outcome
from chase_engine.v34.engine import (
    DEFAULT_RULES,
    GameState,
    PlayerProfile,
    StrategyId,
    distribution,
    initial_state,
    simulate_step,
    window_for,
)
from chase_engine.v34.transitions import apply_delivery, current_bowler

SCENARIOS = {
    "full_chase": (0, 0, 0),
    "low_pressure": (84, 161, 7),
    "medium_pressure": (60, 101, 3),
    "high_pressure": (108, 165, 4),
}
POLICIES = [s.value for s in StrategyId] + ["SENSIBLE"]


def statistically_competitive(candidate, leader):
    """Paired common-seed wins: accept a gap within 1.96 standard errors."""
    differences = [
        int(best["won"]) - int(plan["won"]) for plan, best in zip(candidate, leader, strict=True)
    ]
    gap = mean(differences)
    if gap <= 0:
        return True
    if len(differences) < 2:
        return False
    standard_error = sqrt(
        sum((difference - gap) ** 2 for difference in differences)
        / (len(differences) - 1)
        / len(differences)
    )
    return gap <= 1.96 * standard_error


def catalog(version="fictional-v4"):
    source = real_players() if version == REAL_CATALOG_VERSION else simple_fictional_players()
    players = [Player(id=p.id, role=p.role, overall_rating=p.overallRating) for p in source]
    profiles = {
        p.id: PlayerProfile(
            p.id,
            p.role,
            p.overallRating,
            p.batting,
            p.bowling_control,
            p.bowling_threat,
            BowlingStyle(p.bowling_style),
        )
        for p in source
    }
    return players, profiles


def choose(policy, state):
    if policy != "SENSIBLE":
        return StrategyId(policy)
    rate = (201 - state.runs) * 6 / max(1, 120 - state.balls)
    if state.free_hit:
        return StrategyId.AGGRESSIVE
    if rate < 7:
        return StrategyId.DEFENSIVE
    if state.recent_approaches.count("AGGRESSIVE") >= 12 and state.balls < 108:
        return StrategyId.BALANCED
    if rate > 11.5 or state.recent_approaches.count("BALANCED") >= 18:
        return StrategyId.AGGRESSIVE
    return StrategyId.BALANCED


def reconcile(state):
    assert state.runs == sum(b.runs for b in state.batting) + state.wides + state.no_balls
    assert state.runs == sum(b.runs for b in state.bowling)
    assert (
        state.wickets == sum(b.out for b in state.batting) == sum(b.wickets for b in state.bowling)
    )
    assert state.balls == sum(b.balls for b in state.batting) == sum(b.balls for b in state.bowling)
    assert all(b.balls <= 24 for b in state.bowling)
    assert all(a != b for a, b in zip(state.over_bowlers, state.over_bowlers[1:], strict=False))


def run(scenario, policy, seed, team, opponent, audit=True):
    state = initial_state(team, opponent)
    balls, runs, wickets = SCENARIOS[scenario]
    for _ in range(wickets):
        apply_delivery(state, Outcome.WICKET, strategy=StrategyId.BALANCED)
    for i in range(balls - wickets):
        value = runs // (balls - wickets) + (i < runs % (balls - wickets))
        apply_delivery(
            state,
            list(Outcome)[value],
            strategy=StrategyId.DEFENSIVE if i % 12 < 6 else StrategyId.BALANCED,
        )
    rng = random.Random(seed)
    bowlers = {p.id: p for p in opponent}
    counts, usage, overs, blocks = Counter(), Counter(), Counter(), Counter()
    opening, closing = Counter(), Counter()
    checked, free_hits = 0, 0
    trace = hashlib.sha256()
    last_ten = []
    while state.status == "LIVE":
        mode = choose(policy, state)
        usage[mode.value] += 1
        transition = simulate_step(
            state,
            team,
            opponent,
            mode,
            window_for(state).max_legal_balls,
            DEFAULT_RULES,
            rng,
        )
        trace.update(json.dumps(asdict(transition), sort_keys=True, separators=(",", ":")).encode())
        if audit:
            replay = GameState.from_dict(asdict(state))
        for delivery in transition.events[0]["deliveries"]:
            if audit:
                risks = [
                    distribution(
                        replay,
                        team[replay.striker],
                        team[replay.non_striker],
                        bowlers[current_bowler(replay).player_id],
                        s,
                    ).wicket_probability
                    for s in StrategyId
                ]
                if replay.free_hit:
                    assert risks == [0, 0, 0]
                    free_hits += 1
                else:
                    assert 0 < risks[0] < risks[1] < risks[2] < 1, (scenario, seed, risks)
                    checked += 1
                assert (
                    apply_delivery(replay, Outcome(delivery["outcome"]), strategy=mode) == delivery
                )
            if delivery["fromBall"] >= 110:
                last_ten.append((delivery["fromBall"], delivery["runs"]))
            counts[delivery["outcome"]] += 1
            if delivery["fromBall"] < 18:
                opening[delivery["outcome"]] += 1
            if delivery["fromBall"] >= 102:
                closing[delivery["outcome"]] += 1
            overs[delivery["fromBall"] // 6] += delivery["runs"]
            blocks[delivery["fromBall"] // 12] += delivery["runs"]
        if audit:
            assert replay == transition.state
            reconcile(replay)
        state = transition.state
    return {
        "won": state.status == "WON",
        "score": state.runs,
        "wickets": state.wickets,
        "lastTenRuns": sum(v for ball, v in last_ten),
        "eightOverWin": state.status == "WON" and state.balls <= 48,
        "thirtyRunOvers": sum(v >= 30 for v in overs.values()),
        "overs": len(overs),
        "fiftyRunBlocks": sum(v >= 50 for v in blocks.values()),
        "blocks": len(blocks),
        "counts": counts,
        "opening": opening,
        "closing": closing,
        "usage": usage,
        "checked": checked,
        "freeHits": free_hits,
        "traceSha256": trace.hexdigest(),
    }


def characterize(seeds, version="fictional-v4"):
    players, profiles = catalog(version)
    selection = REAL_SELECTION if version == REAL_CATALOG_VERSION else SIMPLE_SELECTION
    samples = defaultdict(list)
    fingerprints = set()
    for seed in range(seeds):
        rng = random.Random(seed)
        offers = draft_offers(players, rng, selection)
        picks = [rng.choice(group) for group in offers]
        # A sensible order keeps the tail last; choices within every offer are random.
        team = sorted([profiles[p.id] for p in picks], key=lambda p: p.overall, reverse=True)
        opponent = [profiles[p.id] for p in opponent_players(players, random.Random(seed + 10000))]
        fingerprints.add(tuple(p.id for p in team))
        for scenario in SCENARIOS:
            for policy in POLICIES:
                row = run(scenario, policy, seed, team, opponent)
                samples[scenario, policy].append(row)
                if scenario == "full_chase" and policy == "SENSIBLE":
                    assert (
                        row["traceSha256"]
                        == run(
                            scenario,
                            policy,
                            seed,
                            team,
                            opponent,
                            audit=False,
                        )["traceSha256"]
                    )
        if (seed + 1) % 50 == 0:
            print(f"Randomized legal drafts: {seed + 1}/{seeds} common seeds", flush=True)

    results = {}
    for scenario in SCENARIOS:
        results[scenario] = {}
        for policy in POLICIES:
            rows = samples[scenario, policy]
            counts, usage, opening, closing = Counter(), Counter(), Counter(), Counter()
            for row in rows:
                counts.update(row["counts"])
                usage.update(row["usage"])
                opening.update(row["opening"])
                closing.update(row["closing"])
            results[scenario][policy] = {
                "winRate": mean(r["won"] for r in rows),
                "meanScore": mean(r["score"] for r in rows),
                "maxScore": max(r["score"] for r in rows),
                "scoreP95": sorted(r["score"] for r in rows)[int((len(rows) - 1) * 0.95)],
                "meanWickets": mean(r["wickets"] for r in rows),
                "meanLastTenRuns": mean(r["lastTenRuns"] for r in rows),
                "wicketRate": counts["WICKET"] / sum(counts.values()),
                "outcomeCounts": dict(counts),
                "firstThreeOvers": dict(opening),
                "lastThreeOvers": dict(closing),
                "strategyUsage": dict(usage),
                "winsByEightOvers": mean(r["eightOverWin"] for r in rows),
                "thirtyRunOverRate": sum(r["thirtyRunOvers"] for r in rows)
                / sum(r["overs"] for r in rows),
                "fiftyRunTwoOverRate": sum(r["fiftyRunBlocks"] for r in rows)
                / sum(r["blocks"] for r in rows),
            }
    failures = []
    full = results["full_chase"]
    for policy, low, high in (
        ("SENSIBLE", 0.60, 0.65),
        ("DEFENSIVE", 0.0, 0.0),
        ("BALANCED", 0.0, 0.0),
        ("AGGRESSIVE", 0.0, 0.0),
    ):
        if not low <= full[policy]["winRate"] <= high:
            failures.append(f"{policy} win rate outside {low}–{high}: {full[policy]['winRate']}")
    for policy, maximum in (("DEFENSIVE", 200), ("BALANCED", 200), ("AGGRESSIVE", 200)):
        if full[policy]["maxScore"] > maximum:
            failures.append(f"{policy} exceeded score ceiling {maximum}")
    if not 2 <= full["DEFENSIVE"]["meanWickets"] <= 3:
        failures.append("Defensive mean wickets outside 2–3")
    for policy, low, high in (
        ("DEFENSIVE", 0.01, 0.04),
        ("BALANCED", 0.03, 0.07),
        ("AGGRESSIVE", 0.08, 0.13),
    ):
        if not low <= full[policy]["wicketRate"] <= high:
            failures.append(
                f"{policy} wicket rate outside {low}–{high}: {full[policy]['wicketRate']}"
            )
        useful = False
        for scenario, rows in results.items():
            if rows[policy]["winRate"] < 0.05:
                continue
            leader = max(POLICIES[:3], key=lambda p: rows[p]["winRate"])
            competitive = rows[policy]["winRate"] >= rows[leader]["winRate"]
            if version == REAL_CATALOG_VERSION:
                competitive = statistically_competitive(
                    samples[scenario, policy], samples[scenario, leader]
                )
            if competitive:
                useful = True
                break
        if not useful:
            failures.append(f"{policy} lacks a useful winning scenario")
    for policy in POLICIES:
        for metric, limit in (
            ("winsByEightOvers", 0.01),
            ("thirtyRunOverRate", 0.04),
            ("fiftyRunTwoOverRate", 0.05),
        ):
            if full[policy][metric] > limit:
                failures.append(f"{policy} exceeds burst limit {metric}: {full[policy][metric]}")
    for policy in ("DEFENSIVE", "BALANCED"):
        for phase in ("firstThreeOvers", "lastThreeOvers"):
            if not all(
                full[policy][phase].get(outcome, 0) > 0
                for outcome in ("DOT", "ONE", "TWO", "FOUR", "SIX", "WICKET")
            ):
                failures.append(f"{policy} lacks varied outcomes in {phase}")
    return {
        "ruleset": "v3.4",
        "catalog": version,
        "selectionRuleset": selection,
        "usefulPlanCriterion": (
            "At least 5% wins in a scenario, within 1.96 paired standard errors of the best fixed plan over common seeds."
            if version == REAL_CATALOG_VERSION
            else "At least 5% wins in a scenario and the highest observed fixed-plan win rate."
        ),
        "rulesetSha256": hashlib.sha256(
            json.dumps(asdict(DEFAULT_RULES), sort_keys=True).encode()
        ).hexdigest(),
        "boundaryPriorScaleVsV30": DEFAULT_RULES.phase_weights[0][4] / 0.195,
        "seeds": seeds,
        "uniqueDrafts": len(fingerprints),
        "scenarioPrefixes": SCENARIOS,
        "prefixApproaches": "Continuation prefixes use Balanced for wickets and alternate Defensive/Balanced every six scoring balls; the full chase starts with no approaches used.",
        "variationRule": "Recent repetition changes sampling probabilities from the opening overs onward, without per-ball scoring ceilings. One approach cannot score winning runs; extras do not count as switching.",
        "drafting": "Random choice from each legal five-player offer; batting order by descending OVR. Opponents use production median-strength selection with seed + 10000.",
        "policy": "Aggressive on free hits; Defensive below required rate 7; otherwise Balanced after 12 Aggressive balls in the last 24 before the final two overs, Aggressive above required rate 11.5 or after 18 Balanced balls in the last 24, Balanced otherwise. Decisions use production windows.",
        "wicketRateDenominator": "All simulated deliveries in fixed-mode full chases, including extras and free hits; pooled counts, not mean match rates.",
        "scenarios": results,
        "nonFreeHitStatesChecked": sum(r["checked"] for rows in samples.values() for r in rows),
        "freeHitStatesChecked": sum(r["freeHits"] for rows in samples.values() for r in rows),
        "scorecardReconciliation": "Every decision and reconstructed delivery",
        "deterministicReplays": seeds,
        "balanceFailures": failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--catalog", choices=["fictional-v4", REAL_CATALOG_VERSION], default="fictional-v4"
    )
    args = parser.parse_args()
    if args.seeds < 1 or (args.check and args.seeds < 500):
        parser.error("Acceptance requires at least 500 common seeds")
    report = characterize(args.seeds, args.catalog)
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
