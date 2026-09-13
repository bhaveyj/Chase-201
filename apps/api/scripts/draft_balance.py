"""Reproduce rating-stacking and burst-scoring exploits using actual draft/player logic."""

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from statistics import mean

from calibrate import run

from chase201.catalog import balanced_fictional_players, fictional_players
from chase201.draft_rules import ROLES, draft_offers, opponent_players, rating_band
from chase201.models import Player
from chase201.profile_defaults import expanded_profile
from chase_engine.engine import DEFAULT_RULES, RULESETS, PlayerProfile


def catalog(version):
    source = fictional_players() if version == "fictional-v1" else balanced_fictional_players()
    players, profiles = [], {}
    for p in source:
        player_id = f"{version}:{p.id}"
        players.append(Player(id=player_id, role=p.role, overall_rating=p.overallRating))
        profiles[player_id] = PlayerProfile(
            player_id,
            p.role,
            p.overallRating,
            **expanded_profile(player_id, p.batting, p.bowling),
        )
    return players, profiles


def characterize(seeds):
    old, old_profiles = catalog("fictional-v1")
    current, profiles = catalog("fictional-v2")
    unrestricted = []
    for role, count in Counter(ROLES).items():
        unrestricted.extend(
            sorted(
                [p for p in old if p.role == role],
                key=lambda p: p.overall_rating,
                reverse=True,
            )[:count]
        )
    # Stress the legal maximum even if a real disjoint offer draw would rarely offer it.
    best = []
    for position, role in enumerate(ROLES):
        band = rating_band(position)
        eligible = [
            p
            for p in current
            if p.role == role and p not in best and band.minimum <= p.overall_rating <= band.maximum
        ]
        best.append(
            max(
                eligible,
                key=lambda p: profiles[p.id].batting_control + profiles[p.id].batting_power,
            )
        )
    # Put both stars at the top: the rating restriction is independent of batting order.
    best.sort(
        key=lambda p: profiles[p.id].batting_control + profiles[p.id].batting_power, reverse=True
    )
    opposition = [profiles[p.id] for p in opponent_players(current, random.Random(201))]
    best_team = [profiles[p.id] for p in best]
    rows = {
        "unrestrictedV20": run(
            "full_chase",
            "ALL_OUT",
            seeds,
            [old_profiles[p.id] for p in unrestricted],
            opposition,
            RULESETS["v2.0"],
        ),
        "ratingCapOnly": run(
            "full_chase", "ALL_OUT", seeds, best_team, opposition, RULESETS["v2.0"]
        ),
        "cappedV21": {
            policy: run("full_chase", policy, seeds, best_team, opposition)
            for policy in ("ALL_OUT", "ATTACK", "BALANCED", "ADAPT_CONTEXT")
        },
    }
    # Vary offers, strongest available picks and opponents on every seed, as in real games.
    drafts = []
    for seed in range(seeds):
        rng = random.Random(seed)
        offers = draft_offers(current, rng)
        team = [profiles[max(options, key=lambda p: p.overall_rating).id] for options in offers]
        team.sort(key=lambda p: p.overall, reverse=True)
        opponent = [profiles[p.id] for p in opponent_players(current, rng)]
        # A single reproducible game per catalog draw; vary delivery randomness as well.
        drafts.append(run("full_chase", "ALL_OUT", 1, team, opponent, seed_offset=seed))
    rows["randomDraftsAllOut"] = {
        metric: mean(row[metric] for row in drafts)
        for metric in ("winRate", "winsByEightOvers", "fiftyRunTwoOverRate", "thirtyRunOverRate")
    }
    failures = []
    for name, row in (
        ("strongest legal XI", rows["cappedV21"]["ALL_OUT"]),
        ("random drafts", rows["randomDraftsAllOut"]),
    ):
        for metric, maximum in (
            ("winRate", 0.70),
            ("winsByEightOvers", 0.01),
            ("fiftyRunTwoOverRate", 0.05),
            ("thirtyRunOverRate", 0.04),
        ):
            if row[metric] > maximum:
                failures.append(f"{name}: {metric} exceeds {maximum}: {row[metric]}")
    return {
        "ruleset": DEFAULT_RULES.version,
        "seeds": seeds,
        "strongestRatings": [p.overall for p in best_team],
        "scenarios": rows,
        "balanceFailures": failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    report = characterize(args.seeds)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "balanceFailures": report["balanceFailures"],
                "randomDraftsAllOut": report["scenarios"]["randomDraftsAllOut"],
            }
        )
    )
    if args.check and report["balanceFailures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
