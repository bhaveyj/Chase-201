from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Literal, Protocol

Intent = Literal["DEFEND", "ROTATE", "ATTACK"]
Risk = Literal["PROTECT_WICKETS", "BALANCED", "MAXIMIZE_RUNS"]


class RandomSource(Protocol):
    def random(self) -> float: ...


@dataclass(frozen=True)
class Player:
    id: str
    batting: float
    bowling: float
    role: str


@dataclass(frozen=True)
class Strategy:
    intent: Intent = "ROTATE"
    risk_focus: Risk = "BALANCED"


@dataclass(frozen=True)
class Ruleset:
    version: str = "v1.0"
    target: int = 201
    legal_balls: int = 120
    wicket_limit: int = 10
    bowling_quota: int = 24
    scoring_scale: float = 1.0


RULESETS = {"v1.0": Ruleset()}


@dataclass
class Batting:
    player_id: str
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    out: bool = False


@dataclass
class Bowling:
    player_id: str
    runs: int = 0
    balls: int = 0
    wickets: int = 0


@dataclass
class GameState:
    runs: int = 0
    wickets: int = 0
    balls: int = 0
    wides: int = 0
    no_balls: int = 0
    striker: int = 0
    non_striker: int = 1
    next_batter: int = 2
    free_hit: bool = False
    status: str = "LIVE"
    batting: list[Batting] = field(default_factory=list)
    bowling: list[Bowling] = field(default_factory=list)
    over_bowlers: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> GameState:
        return cls(
            **{
                **raw,
                "batting": [Batting(**b) for b in raw["batting"]],
                "bowling": [Bowling(**b) for b in raw["bowling"]],
            }
        )


@dataclass
class Transition:
    state: GameState
    events: list[dict]


def initial_state(user_team: list[Player], opponent: list[Player]) -> GameState:
    if len(user_team) != 11 or len({p.id for p in user_team}) != 11:
        raise ValueError("An XI must contain eleven unique players")
    bowlers = sorted(
        (p for p in opponent if p.role in {"BOWLER", "ALL_ROUNDER"}),
        key=lambda p: (-p.bowling, p.id),
    )
    if len(bowlers) != 5:
        raise ValueError("The opponent must have five eligible bowlers")
    return GameState(
        batting=[Batting(p.id) for p in user_team], bowling=[Bowling(p.id) for p in bowlers]
    )


def decision_window(balls: int) -> int:
    """Legal balls per decision, except the finish which is one delivery (including extras)."""
    for end, size in [(36, 18), (72, 12), (96, 6), (108, 3), (120, 1)]:
        if balls < end:
            return min(size - (balls % size), end - balls)
    return 0


def _binomial(n: int, p: float, rng: RandomSource) -> int:
    """Inverse CDF samples a count directly; it does not generate individual deliveries."""
    p = max(0.0, min(1.0, p))
    if p == 1:
        return n
    u, cumulative = rng.random(), 0.0
    for k in range(n + 1):
        cumulative += math.comb(n, k) * p**k * (1 - p) ** (n - k)
        if u < cumulative:
            return k
    return n


def _counts(n: int, weights: list[float], rng: RandomSource) -> list[int]:
    result = []
    for i, weight in enumerate(weights[:-1]):
        k = _binomial(n, weight / sum(weights[i:]), rng)
        result.append(k)
        n -= k
    return [*result, n]


def _probabilities(
    state: GameState, batter: Player, bowler: Player, strategy: Strategy, rules: Ruleset
) -> list[float]:
    aggression = {"DEFEND": -0.26, "ROTATE": 0.0, "ATTACK": 0.29}[strategy.intent]
    risk = {"PROTECT_WICKETS": -0.13, "BALANCED": 0.0, "MAXIMIZE_RUNS": 0.15}[strategy.risk_focus]
    edge = (batter.batting - bowler.bowling) / 100
    phase = 0.08 if state.balls < 36 else (0.13 if state.balls >= 96 else 0.0)
    required = (rules.target - state.runs) * 6 / max(1, rules.legal_balls - state.balls)
    pressure = max(0.0, min(0.25, (required - 10) / 45))
    power = max(0.5, 1 + aggression + risk + edge + phase - state.wickets * 0.008)
    wicket = min(0.18, max(0.009, 0.049 * (1 + aggression * 1.9 + risk * 2 + pressure - edge)))
    if state.free_hit:
        wicket = 0
    # Outcomes: dot, two, four, six, single, wicket, wide, no-ball.
    weights = [
        0.28 / power,
        0.09,
        0.18 * power * rules.scoring_scale,
        0.065 * power * rules.scoring_scale,
        0.28,
        wicket,
        0.018,
        0.009,
    ]
    total = sum(weights)
    return [p / total for p in weights]


def _finish(state: GameState, rules: Ruleset) -> None:
    if state.runs >= rules.target:
        state.status = "WON"
    elif state.wickets >= rules.wicket_limit or state.balls >= rules.legal_balls:
        state.status = "TIED" if state.runs == rules.target - 1 else "LOST"


def simulate_step(
    game_state: GameState,
    user_team: list[Player],
    opponent_team: list[Player],
    strategy_decision: Strategy,
    decision_window: int,
    ruleset: Ruleset,
    random_source: RandomSource,
) -> Transition:
    """Advance a decision without mutating inputs or reading global randomness.

    Early phases sample a geometric waiting time to a strike change, wicket, or extra,
    then a multinomial count of 0/2/4/6 outcomes in the intervening legal balls. This is
    aggregate simulation, not a delivery loop concealed by the API. Blocks are bounded
    by overs and the maximum possible winning score, so no legal ball occurs after a win.
    A free hit and a near-target block resolve separately to preserve exact semantics.
    The last two overs sample exactly one delivery; an extra opens another decision.
    """
    if game_state.status != "LIVE" or not 1 <= decision_window <= 18:
        raise ValueError("Cannot simulate a completed match or invalid window")
    s = copy.deepcopy(game_state)
    start = copy.deepcopy(s)
    end = min(ruleset.legal_balls, s.balls + decision_window)
    players = {p.id: p for p in [*user_team, *opponent_team]}
    delivery_mode = s.balls >= 108
    events: list[dict] = []
    attempts = 0
    forced_disruption = False
    while s.balls < end and s.status == "LIVE":
        attempts += 1
        if attempts > 1000:
            raise ValueError("Random source failed to produce legal play")
        over = s.balls // 6
        b = s.bowling[over % len(s.bowling)]
        if len(s.over_bowlers) <= over:
            if b.balls >= ruleset.bowling_quota or (
                s.over_bowlers and s.over_bowlers[-1] == b.player_id
            ):
                raise ValueError("Invalid bowling schedule")
            s.over_bowlers.append(b.player_id)
        bat = s.batting[s.striker]
        probs = _probabilities(
            s, players[bat.player_id], players[b.player_id], strategy_decision, ruleset
        )
        stable = sum(probs[:4])
        cap = min(end - s.balls, 6 - s.balls % 6, (ruleset.target - s.runs - 1) // 6)
        if delivery_mode or s.free_hit:
            cap = 0
        # One draw for the number of stable outcomes before the next disruptive event.
        waiting = (
            0
            if forced_disruption
            else int(math.log(max(1e-15, 1 - random_source.random())) / math.log(stable))
        )
        n = min(cap, waiting)
        before_runs, before_balls = s.runs, s.balls
        label = ""
        if n:
            # Retain the terminating event when the sampled waiting time ends inside
            # this block. Discarding it would systematically suppress wickets/singles.
            forced_disruption = waiting < cap
            counts = _counts(n, probs[:4], random_source)
            runs = sum(c * r for c, r in zip(counts, [0, 2, 4, 6], strict=True))
            bat.runs += runs
            bat.fours += counts[2]
            bat.sixes += counts[3]
            bat.balls += n
            b.runs += runs
            b.balls += n
            s.runs += runs
            s.balls += n
        else:
            # If waiting == 0, condition on a disruptive event. With cap == 0,
            # sample the complete distribution (free hit, finish, or near target).
            indexes = list(range(8)) if cap == 0 and not forced_disruption else list(range(4, 8))
            forced_disruption = False
            u = random_source.random() * sum(probs[i] for i in indexes)
            outcome = indexes[-1]
            for i in indexes:
                u -= probs[i]
                if u <= 0:
                    outcome = i
                    break
            if outcome in (6, 7):
                s.runs += 1
                b.runs += 1
                if outcome == 6:
                    s.wides += 1
                    label = "Wide"
                else:
                    s.no_balls += 1
                    s.free_hit = True
                    label = "No-ball · free hit"
            else:
                s.balls += 1
                b.balls += 1
                bat.balls += 1
                s.free_hit = False
                if outcome == 5:
                    s.wickets += 1
                    b.wickets += 1
                    bat.out = True
                    label = "Wicket"
                    if s.wickets < ruleset.wicket_limit:
                        s.striker = s.next_batter
                        s.next_batter += 1
                else:
                    runs = [0, 2, 4, 6, 1][outcome]
                    s.runs += runs
                    b.runs += runs
                    bat.runs += runs
                    bat.fours += int(runs == 4)
                    bat.sixes += int(runs == 6)
                    label = "Dot ball" if runs == 0 else f"{runs} run{'s' if runs != 1 else ''}"
                    if runs % 2:
                        s.striker, s.non_striker = s.non_striker, s.striker
        _finish(s, ruleset)
        if s.balls != before_balls and s.balls % 6 == 0 and s.status == "LIVE":
            s.striker, s.non_striker = s.non_striker, s.striker
        if delivery_mode:
            events.append(
                {
                    "kind": "DELIVERY",
                    "label": label,
                    "fromBall": before_balls,
                    "toBall": s.balls,
                    "runs": s.runs - before_runs,
                    "wickets": s.wickets - start.wickets,
                    "score": s.runs,
                    "totalWickets": s.wickets,
                    "batterId": bat.player_id,
                    "bowlerId": b.player_id,
                    "freeHit": s.free_hit,
                }
            )
            break
    if not delivery_mode:
        events.append(
            {
                "kind": "AGGREGATE",
                "label": f"{s.runs - start.runs} runs, {s.wickets - start.wickets} wickets",
                "fromBall": start.balls,
                "toBall": s.balls,
                "runs": s.runs - start.runs,
                "wickets": s.wickets - start.wickets,
                "score": s.runs,
                "totalWickets": s.wickets,
                "freeHit": s.free_hit,
            }
        )
    return Transition(s, events)
