"""500+ common seeds: ordinary offers, legal specialist XIs, pressure and burst gates."""

import argparse
import json
import random
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from benchmark_v3 import SCENARIOS, run

from chase201.catalog import tradeoff_fictional_players
from chase201.draft_rules import ROLES, opponent_players, rating_band
from chase201.tradeoffs import DraftProfile, allocate, shuffled_allocation
from chase_engine.types import BowlingStyle, PlayerProfile, StrategyId


def catalog():
    source = tradeoff_fictional_players()
    players = [
        DraftProfile(
            p.id, p.role, p.overallRating, (p.batting_control, p.batting_rotation, p.batting_power)
        )
        for p in source
    ]
    profiles = {
        p.id: PlayerProfile(
            p.id,
            p.role,
            p.overallRating,
            p.batting_control,
            p.batting_rotation,
            p.batting_power,
            p.bowling_control,
            p.bowling_threat,
            BowlingStyle(p.bowling_style),
        )
        for p in source
    }
    return players, profiles


def value(player, policy):
    if policy == "OVR":
        return player.overall_rating
    return player.attributes[{"SURVIVAL": 0, "ROTATION": 1, "BOUNDARIES": 2}[policy]]


def characterize(seeds):
    players, profiles = catalog()
    by_id = {p.id: p for p in players}
    allocation = allocate(players)
    policies = ("OVR", "SURVIVAL", "ROTATION", "BOUNDARIES")
    metrics = (
        "winRate",
        "meanScore",
        "wicketRate",
        "boundaryRate",
        "winsByEightOvers",
        "fiftyRunTwoOverRate",
        "thirtyRunOverRate",
    )
    samples = defaultdict(list)
    for seed in range(seeds):
        rng = random.Random(seed)
        offers = shuffled_allocation(allocation, rng)
        opponent = [profiles[p.id] for p in opponent_players(players, random.Random(seed + 10000))]
        for drafting in policies:
            picks = [
                max((by_id[i] for i in group), key=lambda p: value(p, drafting)) for group in offers
            ]
            # Both stars can open; role and uniqueness constraints concern selection, not order.
            picks.sort(key=lambda p: (p.role != "BOWLER", value(p, drafting)), reverse=True)
            team = [profiles[p.id] for p in picks]
            for scenario in SCENARIOS:
                for mode in StrategyId:
                    row = run(scenario, mode.value, 1, team, opponent, seed_offset=seed)
                    samples[(scenario, drafting, mode.value)].append(row)
        if (seed + 1) % 100 == 0:
            print(f"Ordinary drafts: {seed + 1}/{seeds} common seeds", flush=True)
    ordinary = {
        scenario: {
            drafting: {
                mode.value: {
                    metric: mean(r[metric] for r in samples[(scenario, drafting, mode.value)])
                    for metric in metrics
                }
                for mode in StrategyId
            }
            for drafting in policies
        }
        for scenario in SCENARIOS
    }
    strong = {}
    for drafting in policies[1:]:
        picks = []
        for position, role in enumerate(ROLES):
            band = rating_band(position)
            eligible = [
                p
                for p in players
                if p.role == role
                and p not in picks
                and band.minimum <= p.overall_rating <= band.maximum
            ]
            picks.append(max(eligible, key=lambda p: value(p, drafting)))
        picks.sort(key=lambda p: (p.role != "BOWLER", value(p, drafting)), reverse=True)
        team = [profiles[p.id] for p in picks]
        opponent = [profiles[p.id] for p in opponent_players(players, random.Random(201))]
        strong[drafting] = {
            "players": [asdict(p) for p in picks],
            "scenarios": {
                scenario: {
                    mode.value: run(scenario, mode.value, seeds, team, opponent)
                    for mode in StrategyId
                }
                for scenario in SCENARIOS
            },
        }
        print(f"Strong legal XI: {drafting}", flush=True)
    failures = []
    # Each mode must win a meaningful, common-seed context in the ordinary catalog.
    for mode in StrategyId:
        if not any(
            rows[mode.value]["winRate"] >= max(r["winRate"] for r in rows.values())
            and rows[mode.value]["winRate"] >= 0.05
            for scenario in ordinary.values()
            for rows in scenario.values()
        ):
            failures.append(f"{mode.value} has no useful winning context")
        if all(
            rows[mode.value]["winRate"] >= max(r["winRate"] for r in rows.values())
            for scenario in ordinary.values()
            for rows in scenario.values()
        ):
            failures.append(f"{mode.value} dominates every context")
    if not any(
        max(scenario[p][mode.value]["winRate"] for p in policies[1:])
        > scenario["OVR"][mode.value]["winRate"] + 0.05
        for scenario in ordinary.values()
        for mode in StrategyId
    ):
        failures.append("Specialist drafting lacks a useful advantage over highest OVR")
    stress = {f"ordinary/{p}": ordinary["full_chase"][p]["AGGRESSIVE"] for p in policies}
    stress.update(
        {f"strong/{p}": row["scenarios"]["full_chase"]["AGGRESSIVE"] for p, row in strong.items()}
    )
    for name, row in stress.items():
        for metric, limit in (
            ("winsByEightOvers", 0.01),
            ("fiftyRunTwoOverRate", 0.05),
            ("thirtyRunOverRate", 0.04),
        ):
            if row[metric] > limit:
                failures.append(f"{name}: {metric} {row[metric]} > {limit}")
    return {
        "ruleset": "v3.0",
        "catalog": "fictional-v3",
        "seeds": seeds,
        "scenarioPrefixes": SCENARIOS,
        "ordinaryDrafts": ordinary,
        "strongLegalXIs": strong,
        "balanceFailures": failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.seeds < 1 or (args.check and args.seeds < 500):
        parser.error("Acceptance checks require at least 500 seeds")
    report = characterize(args.seeds)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"seeds": args.seeds, "balanceFailures": report["balanceFailures"]}))
    if args.check and report["balanceFailures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
