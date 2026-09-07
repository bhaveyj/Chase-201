"""Reproducible ruleset report; fictional benchmark XIs, never a real-player claim."""

import argparse
import json
import random
from statistics import mean

from chase_engine.engine import (
    Player,
    Ruleset,
    Strategy,
    decision_window,
    initial_state,
    simulate_step,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=1000)
    args = parser.parse_args()
    roles = ["BATTER"] * 5 + ["WICKETKEEPER"] + ["ALL_ROUNDER"] * 2 + ["BOWLER"] * 3
    team = [
        Player(str(i), 82 if role != "BOWLER" else 46, 80, role) for i, role in enumerate(roles)
    ]
    opponent = [Player(f"ai{i}", 80, 80, role) for i, role in enumerate(roles)]
    report = {
        "ruleset": "v1.0",
        "seeds": args.seeds,
        "benchmark": "fictional batting 82, tail 46, bowling 80",
        "strategies": [],
    }
    for strategy in [
        Strategy("DEFEND", "PROTECT_WICKETS"),
        Strategy(),
        Strategy("ATTACK", "MAXIMIZE_RUNS"),
    ]:
        samples, first_windows = [], []
        for seed in range(args.seeds):
            state = initial_state(team, opponent)
            revision = 0
            while state.status == "LIVE":
                state = simulate_step(
                    state,
                    team,
                    opponent,
                    strategy,
                    decision_window(state.balls),
                    Ruleset(),
                    random.Random(seed * 1000 + revision),
                ).state
                if revision == 0:
                    first_windows.append(state)
                revision += 1
            samples.append(state)
        report["strategies"].append(
            {
                "intent": strategy.intent,
                "riskFocus": strategy.risk_focus,
                "winRate": sum(s.status == "WON" for s in samples) / args.seeds,
                "meanRuns": round(mean(s.runs for s in samples), 2),
                "meanWickets": round(mean(s.wickets for s in samples), 2),
                "first18BallsRuns": round(mean(s.runs for s in first_windows), 2),
                "first18BallsWickets": round(mean(s.wickets for s in first_windows), 2),
            }
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
