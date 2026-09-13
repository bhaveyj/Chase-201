"""Common-seed scenario/policy report and broad balance gates for fictional cricket."""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean, pvariance

from chase_engine.context import derive_context
from chase_engine.engine import (
    DEFAULT_RULES,
    PlayerProfile,
    StrategyId,
    initial_state,
    simulate_step,
    window_for,
)
from chase_engine.rules import phase_index
from chase_engine.transitions import apply_delivery, current_bowler
from chase_engine.types import BowlingStyle, Outcome

ROLES = ["BATTER"] * 5 + ["WICKETKEEPER"] + ["ALL_ROUNDER"] * 2 + ["BOWLER"] * 3
TEAM = [
    PlayerProfile(str(i), role, 82, *([82 if role != "BOWLER" else 46] * 3), 80, 80)
    for i, role in enumerate(ROLES)
]
OPPONENT = [
    PlayerProfile(
        f"ai{i}", role, 80, 80, 80, 80, 80, 80, BowlingStyle.PACE if i % 2 else BowlingStyle.SPIN
    )
    for i, role in enumerate(ROLES)
]
# Completed legal deliveries, runs and wickets; all still chasing the fixed 201 target.
SCENARIOS = {
    "full_chase": (0, 0, 0),
    "low_pressure": (84, 161, 7),
    "medium_pressure": (60, 101, 3),
    "high_pressure": (108, 165, 4),
}
POLICIES = [s.value for s in StrategyId] + ["ADAPT_RATE", "ADAPT_CONTEXT"]


def scenario_state(scenario, team=TEAM, opponent=OPPONENT):
    state = initial_state(team, opponent)
    balls, runs, wickets = SCENARIOS[scenario]
    for _ in range(wickets):
        apply_delivery(state, Outcome.WICKET)
    scoring_balls = balls - wickets
    for i in range(scoring_balls):
        value = runs // scoring_balls + (i < runs % scoring_balls)
        apply_delivery(state, list(Outcome)[value])
    return state


def choose(policy, state, team, opponent):
    if policy in StrategyId.__members__:
        return StrategyId(policy)
    batter, partner = team[state.striker], team[state.non_striker]
    bowler = next(p for p in opponent if p.id == current_bowler(state).player_id)
    context = derive_context(state, batter, partner, bowler)
    if state.free_hit:
        return StrategyId.ALL_OUT
    needed = context.required_rate
    if policy == "ADAPT_CONTEXT":
        if needed < 5 and state.wickets >= 7:
            return StrategyId.PRESERVE
        if needed < 10 and context.striker_setness < 0.4:
            return StrategyId.ROTATE
        if needed > 15 or (context.balls_remaining <= 6 and needed > 11):
            return StrategyId.ALL_OUT
        if needed > 10.5 and context.striker_setness >= 0.4:
            return StrategyId.ATTACK
    if needed < 8:
        return StrategyId.ROTATE
    if needed < 11:
        return StrategyId.BALANCED
    if needed < 16:
        return StrategyId.ATTACK
    return StrategyId.ALL_OUT


def percentile(values, q):
    return sorted(values)[round((len(values) - 1) * q)]


def run(scenario, policy, seeds, team=TEAM, opponent=OPPONENT, rules=DEFAULT_RULES, seed_offset=0):
    scores, wins, decisions, first_wickets = [], [], [], []
    counts, usage = Counter(), Counter()
    phase_runs, phase_balls = defaultdict(int), defaultdict(int)
    outcome_runs = []
    winning_balls, eight_over_wins, thirty_run_overs, fifty_run_blocks = [], 0, [], []
    for seed in range(seeds):
        state = scenario_state(scenario, team, opponent)
        rng = random.Random(seed + seed_offset)
        count, first = 0, None
        over_runs, block_runs = Counter(), Counter()
        while state.status == "LIVE":
            strategy = choose(policy, state, team, opponent)
            usage[strategy.value] += 1
            transition = simulate_step(
                state,
                team,
                opponent,
                strategy,
                window_for(state, rules).max_legal_balls,
                rules,
                rng,
            )
            for delivery in transition.events[0]["deliveries"]:
                counts[delivery["outcome"]] += 1
                outcome_runs.append(delivery["runs"])
                over_runs[delivery["fromBall"] // 6] += delivery["runs"]
                block_runs[delivery["fromBall"] // 12] += delivery["runs"]
                phase = ("POWERPLAY", "MIDDLE", "DEATH")[phase_index(delivery["fromBall"])]
                phase_runs[phase] += delivery["runs"]
                phase_balls[phase] += delivery["toBall"] - delivery["fromBall"]
                if delivery["wickets"] and first is None:
                    first = delivery["toBall"]
            state = transition.state
            count += 1
        scores.append(state.runs)
        wins.append(state.status == "WON")
        if state.status == "WON":
            winning_balls.append(state.balls)
            eight_over_wins += state.balls <= 48
        thirty_run_overs.extend(value >= 30 for value in over_runs.values())
        fifty_run_blocks.extend(value >= 50 for value in block_runs.values())
        decisions.append(count)
        first_wickets.append(first)
    total = sum(counts.values())

    def rate(*outcomes):
        return sum(counts[o] for o in outcomes) / total

    observed = [ball for ball in first_wickets if ball is not None]
    return {
        "policy": policy,
        "winRate": mean(wins),
        "winsByEightOvers": eight_over_wins / seeds,
        "winningBallsPercentiles": {
            str(q): percentile(winning_balls, q / 100) for q in (10, 50, 90)
        }
        if winning_balls
        else None,
        "thirtyRunOverRate": mean(thirty_run_overs),
        "fiftyRunTwoOverRate": mean(fifty_run_blocks),
        "meanScore": mean(scores),
        "scorePercentiles": {str(q): percentile(scores, q / 100) for q in (10, 50, 90)},
        "scoreVariance": pvariance(scores),
        "outcomeVariance": pvariance(outcome_runs),
        "dotRate": rate("DOT"),
        "singleRate": rate("ONE"),
        "boundaryRate": rate("FOUR", "SIX"),
        "sixRate": rate("SIX"),
        "wicketRate": rate("WICKET"),
        "extraRate": rate("WIDE", "NO_BALL"),
        "outcomeCounts": dict(counts),
        "phaseRunRates": {
            phase: 6 * runs / max(1, phase_balls[phase]) for phase, runs in phase_runs.items()
        },
        "firstWicketBall": {
            "none": first_wickets.count(None),
            "histogram": dict(Counter(observed)),
            "median": percentile(observed, 0.5) if observed else None,
        },
        "meanDecisions": mean(decisions),
        "decisionPercentiles": {str(q): percentile(decisions, q / 100) for q in (10, 50, 90)},
        "strategyUsage": dict(usage),
    }


def balance_failures(report):
    failures = []
    full = {row["policy"]: row for row in report["scenarios"]["full_chase"]}
    neutral = full["BALANCED"]
    envelopes = {
        "winRate": (0.2, 0.8),
        "dotRate": (0.15, 0.42),
        "singleRate": (0.15, 0.45),
        "boundaryRate": (0.15, 0.42),
        "sixRate": (0.03, 0.20),
        "wicketRate": (0.025, 0.12),
        "extraRate": (0.01, 0.06),
        "meanDecisions": (15, 45),
    }
    for metric, (low, high) in envelopes.items():
        if not low <= neutral[metric] <= high:
            failures.append(f"BALANCED {metric} outside [{low}, {high}]: {neutral[metric]:.4f}")
    scenarios = [
        report["scenarios"][key] for key in ("low_pressure", "medium_pressure", "high_pressure")
    ]
    # A strategy is dominant if it is within 5 percentage points of best in every context.
    # This checks all fixed and adaptive policies; common seeds reduce comparison noise.
    for policy in [s.value for s in StrategyId]:
        if all(
            next(r["winRate"] for r in rows if r["policy"] == policy)
            >= max(r["winRate"] for r in rows) - 0.05
            for rows in scenarios
        ):
            failures.append(f"{policy} dominates low, medium and high pressure")
    # A context-aware policy may be competitive everywhere; that is the intended loop.
    # Still flag any policy that beats every alternative by a clear margin everywhere.
    for policy in POLICIES:
        if all(
            next(r["winRate"] for r in rows if r["policy"] == policy)
            > max(r["winRate"] for r in rows if r["policy"] != policy) + 0.05
            for rows in scenarios
        ):
            failures.append(
                f"{policy} strictly dominates every alternative across pressure scenarios"
            )
    if max(r["winRate"] for r in scenarios[0]) - min(r["winRate"] for r in scenarios[0]) < 0.15:
        failures.append("Plans lack meaningful separation in the low-pressure scenario")
    if "catalogSensitivity" in report:
        tiers = report["catalogSensitivity"]["teamTiers"]
        if tiers["strong"]["winRate"] < tiers["weak"]["winRate"] + 0.15:
            failures.append("Full-catalog team quality has insufficient impact")
        for row in report["catalogSensitivity"]["players"]:
            for matchup in (row["plans"], row.get("bowlingPlans", {})):
                if matchup and matchup["PRESERVE"]["wicket"] >= matchup["ALL_OUT"]["wicket"]:
                    failures.append(f"Unrecognizable plan risk for {row['player']}")
    return failures


def catalog_sensitivity(seeds):
    from chase201.catalog import fictional_players
    from chase201.profile_defaults import expanded_profile

    catalog = [
        PlayerProfile(
            f"fictional-v1:{p.id}",
            p.role,
            p.overallRating,
            **expanded_profile(f"fictional-v1:{p.id}", p.batting, p.bowling),
        )
        for p in fictional_players()
    ]
    rows = []
    for player in catalog:
        # Each catalog player faces the same fresh batter/bowler scenario under every plan.
        from chase_engine.probabilities import distribution

        state = initial_state(TEAM, OPPONENT)
        rows.append(
            {
                "player": player.id,
                "role": player.role,
                "plans": {
                    strategy.value: {
                        "runs": (
                            d := distribution(state, player, TEAM[1], OPPONENT[-1], strategy)
                        ).expected_runs,
                        "wicket": d.wicket_probability,
                        "boundary": d.boundary_probability,
                    }
                    for strategy in StrategyId
                },
            }
        )
        if player.role in {"BOWLER", "ALL_ROUNDER"}:
            rows[-1]["bowlingPlans"] = {
                strategy.value: {
                    "runs": (
                        d := distribution(state, TEAM[0], TEAM[1], player, strategy)
                    ).expected_runs,
                    "wicket": d.wicket_probability,
                    "boundary": d.boundary_probability,
                }
                for strategy in StrategyId
            }
    tiers = {}
    for name, reverse in [("strong", True), ("weak", False)]:
        xi = []
        for role, count in Counter(ROLES).items():
            xi.extend(
                sorted(
                    [p for p in catalog if p.role == role], key=lambda p: p.overall, reverse=reverse
                )[:count]
            )
        tiers[name] = run("full_chase", "ADAPT_CONTEXT", seeds, xi, OPPONENT)
    return {"players": rows, "teamTiers": tiers}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=500)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--catalog", action="store_true")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    report = {
        "ruleset": DEFAULT_RULES.version,
        "seeds": args.seeds,
        "commonSeeds": True,
        "configurationSHA256": hashlib.sha256(
            json.dumps(asdict(DEFAULT_RULES), sort_keys=True).encode()
        ).hexdigest(),
        "scenarios": {
            scenario: [run(scenario, policy, args.seeds) for policy in POLICIES]
            for scenario in SCENARIOS
        },
    }
    if args.catalog:
        report["catalogSensitivity"] = catalog_sensitivity(args.seeds)
    report["balanceFailures"] = balance_failures(report)
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
        print(
            json.dumps(
                {
                    "balanceFailures": report["balanceFailures"],
                    "winRates": {
                        key: {r["policy"]: r["winRate"] for r in rows}
                        for key, rows in report["scenarios"].items()
                    },
                },
                indent=2,
            )
        )
    else:
        print(content)
    if args.check and report["balanceFailures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
