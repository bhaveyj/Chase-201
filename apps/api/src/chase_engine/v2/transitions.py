"""Cricket accounting for one delivery. Mutates only the simulation's owned copy."""

from chase_engine.v2.rules import DEFAULT_RULES, Ruleset
from chase_engine.v2.types import Batting, Bowling, GameState, Outcome, PlayerProfile

RUNS = {
    Outcome.DOT: 0,
    Outcome.ONE: 1,
    Outcome.TWO: 2,
    Outcome.THREE: 3,
    Outcome.FOUR: 4,
    Outcome.SIX: 6,
}


def initial_state(user_team: list[PlayerProfile], opponent: list[PlayerProfile]) -> GameState:
    if len(user_team) != 11 or len({p.id for p in user_team}) != 11:
        raise ValueError("An XI must contain eleven unique players")
    bowlers = sorted(
        (p for p in opponent if p.role in {"BOWLER", "ALL_ROUNDER"}),
        key=lambda p: (-p.bowling_threat, -p.bowling_control, p.id),
    )
    if len(bowlers) != 5 or len({p.id for p in bowlers}) != 5:
        raise ValueError("The opponent must have five unique eligible bowlers")
    return GameState(
        batting=[Batting(p.id) for p in user_team], bowling=[Bowling(p.id) for p in bowlers]
    )


def current_bowler(state: GameState) -> Bowling:
    return state.bowling[(state.balls // 6) % len(state.bowling)]


def apply_delivery(state: GameState, outcome: Outcome, rules: Ruleset = DEFAULT_RULES) -> dict:
    if state.status != "LIVE":
        raise ValueError("Cannot play after innings completion")
    if state.free_hit and outcome == Outcome.WICKET:
        raise ValueError("A wicket cannot fall on a free hit in this ruleset")
    bowler, batter = current_bowler(state), state.batting[state.striker]
    over = state.balls // 6
    if len(state.over_bowlers) <= over:
        if bowler.balls >= rules.bowling_quota or (
            state.over_bowlers and state.over_bowlers[-1] == bowler.player_id
        ):
            raise ValueError("Invalid bowling schedule")
        state.over_bowlers.append(bowler.player_id)
    before_runs, before_balls, before_wickets = state.runs, state.balls, state.wickets
    if outcome in (Outcome.WIDE, Outcome.NO_BALL):
        state.runs += 1
        bowler.runs += 1
        state.partnership_runs += 1
        if outcome == Outcome.WIDE:
            state.wides += 1
        else:
            state.no_balls += 1
            state.free_hit = True
    else:
        state.balls += 1
        bowler.balls += 1
        batter.balls += 1
        state.partnership_balls += 1
        state.free_hit = False
        if outcome == Outcome.WICKET:
            state.wickets += 1
            bowler.wickets += 1
            batter.out = True
            state.partnership_runs = state.partnership_balls = 0
            state.last_wicket_ball = state.balls
            if state.wickets < rules.wicket_limit:
                state.striker = state.next_batter
                state.next_batter += 1
        else:
            runs = RUNS[outcome]
            state.runs += runs
            bowler.runs += runs
            batter.runs += runs
            batter.fours += int(outcome == Outcome.FOUR)
            batter.sixes += int(outcome == Outcome.SIX)
            state.partnership_runs += runs
            if runs % 2:
                state.striker, state.non_striker = state.non_striker, state.striker
    state.recent_outcomes = [*state.recent_outcomes, outcome.value][-6:]
    if state.runs >= rules.target:
        state.status = "WON"
    elif state.wickets >= rules.wicket_limit or state.balls >= rules.legal_balls:
        state.status = "TIED" if state.runs == rules.target - 1 else "LOST"
    if state.balls > before_balls and state.balls % 6 == 0 and state.status == "LIVE":
        state.striker, state.non_striker = state.non_striker, state.striker
    return {
        "outcome": outcome.value,
        "fromBall": before_balls,
        "toBall": state.balls,
        "runs": state.runs - before_runs,
        "wickets": state.wickets - before_wickets,
        "batterId": batter.player_id,
        "bowlerId": bowler.player_id,
        "freeHit": state.free_hit,
    }
