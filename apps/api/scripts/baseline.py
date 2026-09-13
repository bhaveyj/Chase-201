"""Characterize the frozen v1 engine with all nine choices and replay fixtures."""

import argparse
import hashlib
import json
import random
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from chase_engine import legacy


def characterize(seeds: int) -> dict:
    roles = ["BATTER"] * 5 + ["WICKETKEEPER"] + ["ALL_ROUNDER"] * 2 + ["BOWLER"] * 3
    team = [legacy.Player(str(i), 82 if r != "BOWLER" else 46, 80, r) for i, r in enumerate(roles)]
    opponent = [legacy.Player(f"ai{i}", 80, 80, r) for i, r in enumerate(roles)]
    report = {"ruleset": "v1.0", "seeds": seeds, "policies": []}
    for intent in ("DEFEND", "ROTATE", "ATTACK"):
        for risk in ("PROTECT_WICKETS", "BALANCED", "MAXIMIZE_RUNS"):
            first, final, fixtures = [], [], []
            for seed in range(seeds):
                state = legacy.initial_state(team, opponent)
                revision, trace = 0, []
                while state.status == "LIVE":
                    step = legacy.simulate_step(
                        state,
                        team,
                        opponent,
                        legacy.Strategy(intent, risk),
                        legacy.decision_window(state.balls),
                        legacy.Ruleset(),
                        random.Random(seed * 1000 + revision),
                    )
                    state = step.state
                    trace.append(asdict(step))
                    if revision == 0:
                        first.append(state)
                    revision += 1
                final.append(state)
                if seed < 3:
                    fixtures.append(
                        hashlib.sha256(json.dumps(trace, sort_keys=True).encode()).hexdigest()
                    )
            report["policies"].append(
                {
                    "intent": intent,
                    "riskFocus": risk,
                    "first18Runs": mean(s.runs for s in first),
                    "first18Wickets": mean(s.wickets for s in first),
                    "winRate": mean(s.status == "WON" for s in final),
                    "replaySHA256": fixtures,
                }
            )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = json.dumps(characterize(args.seeds), indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)
