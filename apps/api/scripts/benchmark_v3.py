"""Common-seed scenario/policy report and broad balance gates for fictional cricket."""

import random
from collections import Counter, defaultdict
from statistics import mean, pvariance

from chase_engine.engine import (
    DEFAULT_RULES,
    PlayerProfile,
    StrategyId,
    initial_state,
    simulate_step,
    window_for,
)
from chase_engine.rules import phase_index
from chase_engine.transitions import apply_delivery
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
    rate = (201 - state.runs) * 6 / max(1, 120 - state.balls)
    if state.free_hit or rate > 11.5:
        return StrategyId.AGGRESSIVE
    if rate < 7:
        return StrategyId.DEFENSIVE
    return StrategyId.BALANCED


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
