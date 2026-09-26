"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CircleDot, Target } from "lucide-react";
import { api, APIError, Match, mergeDecisionMatch, overs, roleLabel } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { ErrorPanel, GoogleLink, Loading, useSession } from "./common";

import { V2Plans } from "./v2-plans";
import { BattingPlans, LegacyPlans } from "./batting-plans";

export function Scorecard({ match }: { match: Match }) {
  const s = match.state;
  const names = new Map(
    [...match.team, ...match.opponent].map((p) => [p.id, p.name]),
  );
  return (
    <div className="scorecards">
      <div className="table-panel">
        <div className="panel-title">
          <h2>Batting scorecard</h2>
          <span>YOUR XI</span>
        </div>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Your team batting performance</caption>
            <thead>
              <tr>
                <th scope="col">Batter</th>
                <th scope="col">R</th>
                <th scope="col">B</th>
                <th scope="col">4s</th>
                <th scope="col">6s</th>
                <th scope="col">SR</th>
              </tr>
            </thead>
            <tbody>
              {s.batting.map((b, i) => (
                <tr
                  key={b.player_id}
                  className={
                    s.status === "LIVE" &&
                    (i === s.striker || i === s.non_striker)
                      ? "at-crease"
                      : ""
                  }
                >
                  <th scope="row">
                    {names.get(b.player_id)}
                    {s.status === "LIVE" && i === s.striker && (
                      <span aria-label="On strike"> *</span>
                    )}
                    <small>
                      {b.out
                        ? "out"
                        : b.balls || i < s.next_batter
                          ? "not out"
                          : "did not bat"}
                    </small>
                  </th>
                  <td className="bold">{b.runs}</td>
                  <td>{b.balls}</td>
                  <td>{b.fours}</td>
                  <td>{b.sixes}</td>
                  <td>
                    {b.balls ? ((b.runs / b.balls) * 100).toFixed(1) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">
                  Extras{" "}
                  <small>
                    Wd {s.wides} · Nb {s.no_balls}
                  </small>
                </th>
                <td>{s.wides + s.no_balls}</td>
                <td colSpan={4} />
              </tr>
              <tr>
                <th scope="row">
                  Total <small>{overs(s.balls)} overs</small>
                </th>
                <td colSpan={5}>
                  {s.runs}/{s.wickets}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
      <div className="table-panel">
        <div className="panel-title">
          <h2>Bowling figures</h2>
          <span>OPPOSITION</span>
        </div>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              Opposition bowling performance
            </caption>
            <thead>
              <tr>
                <th scope="col">Bowler</th>
                <th scope="col">O</th>
                <th scope="col">R</th>
                <th scope="col">W</th>
                <th scope="col">Econ</th>
              </tr>
            </thead>
            <tbody>
              {s.bowling.map((b) => (
                <tr key={b.player_id}>
                  <th scope="row">{names.get(b.player_id)}</th>
                  <td>{overs(b.balls)}</td>
                  <td>{b.runs}</td>
                  <td className="bold">{b.wickets}</td>
                  <td>{b.balls ? ((b.runs / b.balls) * 6).toFixed(2) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="scorecard-note">
          <CircleDot size={17} />
          <p>Maximum four overs per bowler. No consecutive overs.</p>
        </div>
      </div>
    </div>
  );
}

export function MatchScreen({
  id,
  result = false,
}: {
  id: string;
  result?: boolean;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const session = useSession();
  const query = useQuery({
    queryKey: ["match", id],
    queryFn: () => api.match(id),
  });
  const strategy = useUI((s) => s.strategy);
  const setStrategy = useUI((s) => s.setStrategy);
  const v2Strategy = useUI((s) => s.v2Strategy);
  const setV2Strategy = useUI((s) => s.setV2Strategy);
  useEffect(() => {
    setStrategy("BALANCED");
    setV2Strategy("BALANCED");
  }, [id, setStrategy, setV2Strategy]);
  const legacyStrategy = useUI((s) => s.legacyStrategy);
  const setLegacyStrategy = useUI((s) => s.setLegacyStrategy);
  const m = query.data;
  const action = useMutation({
    mutationFn: () =>
      api.decide(
        session.data!,
        m!,
        m?.rulesetVersion === "v1.0"
          ? legacyStrategy
          : m?.rulesetVersion === "v3.0" ||
              m?.rulesetVersion === "v3.1" ||
              m?.rulesetVersion === "v3.2" ||
              m?.rulesetVersion === "v3.3" ||
              m?.rulesetVersion === "v3.4" ||
              m?.rulesetVersion === "v3.5"
            ? strategy
            : v2Strategy,
        crypto.randomUUID(),
      ),
    onSuccess: (next) => {
      const previous = client.getQueryData<Match>(["match", id]);
      const merged = mergeDecisionMatch(previous, next);
      if (merged) {
        client.setQueryData<Match>(["match", id], merged);
      } else {
        void client.invalidateQueries({ queryKey: ["match", id] });
      }
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: ["match", id] });
    },
  });
  useEffect(() => {
    if (m && m.state.status !== "LIVE" && !result)
      router.replace(`/match/${id}/result`);
  }, [m, id, result, router]);
  if (query.isPending || session.isPending)
    return <Loading label="Checking the scoreboard…" />;
  if (query.error || !m)
    return (
      <section className="page-width">
        <ErrorPanel error={query.error} retry={() => void query.refetch()} />
      </section>
    );
  const s = m.state;
  const needed = Math.max(0, m.target - s.runs),
    left = 120 - s.balls;
  const live = s.status === "LIVE";
  const legacy = m.rulesetVersion === "v1.0";
  const windowLabel =
    s.balls >= 108 || (!legacy && s.free_hit)
      ? "delivery"
      : m.decisionWindow % 6 !== 0
        ? `${m.decisionWindow} ${m.decisionWindow === 1 ? "ball" : "balls"}`
        : `${m.decisionWindow / 6} ${m.decisionWindow === 6 ? "over" : "overs"}`;
  const lastEvent = m.events.at(-1);
  const phase =
    s.balls < 36
      ? "POWERPLAY"
      : s.balls < 72
        ? "BUILD THE CHASE"
        : s.balls < 96
          ? "MAKE YOUR MOVE"
          : "THE FINISH";
  if (result && live)
    return (
      <section className="page-width">
        <h1>Your chase is still on.</h1>
        <Link className="button primary" href={`/match/${id}`}>
          Return to match <ArrowRight size={18} />
        </Link>
      </section>
    );
  return (
    <section className="page-width match-page">
      <div className="match-heading">
        <p className="eyebrow">
          <span className="live-dot" />
          {live ? "CHASE IN PROGRESS" : "MATCH COMPLETE"}
        </p>
        <span className="subtle">T20 · TARGET {m.target}</span>
      </div>
      {!live && (
        <div className={`result-title ${s.status.toLowerCase()}`}>
          <span className="result-icon">
            {s.status === "WON" ? <Check size={30} /> : <Target size={30} />}
          </span>
          <p className="eyebrow">
            {s.status === "WON"
              ? "THAT’S HOW YOU BRING IT HOME"
              : s.status === "TIED"
                ? "NOTHING BETWEEN THE SIDES"
                : "THE GAME KEEPS YOU HUMBLE"}
          </p>
          <h1>
            {s.status === "WON" ? (
              <>
                Chase <em>conquered.</em>
              </>
            ) : s.status === "TIED" ? (
              <>
                Honours <em>even.</em>
              </>
            ) : (
              <>
                So close to
                <br />
                <em>another story.</em>
              </>
            )}
          </h1>
          <p>
            {s.status === "WON"
              ? `You won by ${10 - s.wickets} wickets with ${left} balls to spare.`
              : s.status === "TIED"
                ? `${m.target - 1} apiece. The match is tied. No super over.`
                : `The opposition won by ${m.target - 1 - s.runs} runs.`}
          </p>
        </div>
      )}
      <div className="scoreboard" aria-live="polite" aria-atomic="true">
        <div className="score-main">
          <span>YOUR XI</span>
          <strong>
            {s.runs}
            <span>/{s.wickets}</span>
          </strong>
          <p>
            {overs(s.balls)} <span>/ 20 overs</span>
          </p>
        </div>
        <div className="score-stats">
          <div>
            <span>{live ? "RUNS NEEDED" : "TARGET"}</span>
            <strong>{live ? needed : m.target}</strong>
          </div>
          <div>
            <span>BALLS LEFT</span>
            <strong>{left}</strong>
          </div>
          <div>
            <span>REQUIRED RATE</span>
            <strong>
              {live && left ? ((needed / left) * 6).toFixed(2) : "—"}
            </strong>
          </div>
          <div>
            <span>CURRENT RATE</span>
            <strong>
              {s.balls ? ((s.runs / s.balls) * 6).toFixed(2) : "0.00"}
            </strong>
          </div>
        </div>
        <div className="chase-track">
          <i
            style={{ width: `${Math.min(100, (s.runs / m.target) * 100)}%` }}
          />
        </div>
        <div className="scoreboard-bottom">
          <span>
            {live
              ? `${needed} runs from ${left} balls. ${10 - s.wickets} wickets in hand.`
              : s.status === "WON"
                ? "Target reached. Job done."
                : "End of innings."}
          </span>
          <span>
            {s.free_hit && live ? "FREE HIT NEXT" : live ? phase : "FULL TIME"}
          </span>
        </div>
      </div>
      {live && (
        <>
          <div className="crease-strip">
            {[s.striker, s.non_striker].map((index, i) => (
              <div key={index}>
                <span className="crease-marker">
                  {i === 0 ? <CircleDot size={17} /> : <span />}
                </span>
                <span>
                  {m.team[index].name}
                  <small>
                    {i === 0 ? "ON STRIKE" : "NON-STRIKER"} ·{" "}
                    {m.team[index].overallRating} OVR
                  </small>
                  <small>
                    {roleLabel[m.team[index].role]}
                    {m.context &&
                      ` · ${i === 0 ? m.context.strikerSetness : m.context.nonStrikerSetness}`}
                  </small>
                </span>
                <strong>
                  {s.batting[index].runs}
                  <small> ({s.batting[index].balls})</small>
                </strong>
              </div>
            ))}
            <div className="bowler-current">
              <span>
                Bowling
                <small>
                  {
                    m.opponent.find(
                      (p) =>
                        p.id ===
                        s.bowling[Math.floor(s.balls / 6) % 5].player_id,
                    )?.name
                  }
                </small>
                {m.upcomingBowlers?.[0] && (
                  <small>
                    {m.upcomingBowlers[0].overallRating} OVR ·{" "}
                    {m.upcomingBowlers[0].style === "PACE" ? "Pace" : "Spin"}
                  </small>
                )}
              </span>
            </div>
          </div>
          {!legacy && (
            <div className="match-context" aria-label="Chase context">
              <div>
                <span>Pressure</span>
                <strong>{m.context?.pressure}</strong>
                <small>{m.context?.matchup}</small>
              </div>
              <div>
                <span>Partnership</span>
                <strong>{s.partnership_runs} runs</strong>
                <small>from {s.partnership_balls} balls</small>
              </div>
              <div className="recent-deliveries">
                <span>Last six deliveries</span>
                <ol aria-label="Last six deliveries, oldest first">
                  {s.recent_outcomes?.map((outcome, index) => (
                    <li
                      key={index}
                      className={`recent-ball ${outcome.toLowerCase()}`}
                      aria-label={outcome.replaceAll("_", " ").toLowerCase()}
                    >
                      {
                        {
                          DOT: "·",
                          ONE: "1",
                          TWO: "2",
                          THREE: "3",
                          FOUR: "4",
                          SIX: "6",
                          WICKET: "W",
                          WIDE: "Wd",
                          NO_BALL: "Nb",
                        }[outcome]
                      }
                    </li>
                  ))}
                </ol>
                {!s.recent_outcomes?.length && (
                  <small>Ready for the first ball</small>
                )}
              </div>
            </div>
          )}
          <div className="play-layout">
            <div className="strategy-panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">CAPTAIN’S CALL</p>
                  <h2>How do you play this?</h2>
                </div>
                <span className="window-badge">
                  NEXT: {windowLabel.toUpperCase()}
                </span>
              </div>
              {!legacy && (
                <>
                  {lastEvent?.interruption === "WICKET" && (
                    <p className="interruption-note" role="status">
                      Wicket—choose a plan for the new batter.{" "}
                      {m.team[s.striker].name} is on strike.
                    </p>
                  )}
                  {s.free_hit && (
                    <p className="interruption-note" role="status">
                      Free hit—choose your plan for one delivery. Your wicket is
                      protected.
                    </p>
                  )}
                  {(m.upcomingBowlers?.length ?? 0) > 1 && (
                    <p className="upcoming-spell">
                      Two-over game plan ·{" "}
                      {m.upcomingBowlers
                        ?.map(
                          (bowler) =>
                            `Over ${bowler.over}: ${bowler.name} (${bowler.overallRating}, ${bowler.style === "PACE" ? "pace" : "spin"})`,
                        )
                        .join(" · ")}
                    </p>
                  )}
                </>
              )}
              {legacy ? (
                <LegacyPlans
                  strategy={legacyStrategy}
                  onChange={setLegacyStrategy}
                  disabled={action.isPending}
                />
              ) : m.rulesetVersion !== "v3.0" &&
                m.rulesetVersion !== "v3.1" &&
                m.rulesetVersion !== "v3.2" &&
                m.rulesetVersion !== "v3.3" &&
                m.rulesetVersion !== "v3.4" &&
                m.rulesetVersion !== "v3.5" ? (
                <V2Plans
                  strategy={v2Strategy}
                  assessments={m.strategyAssessments}
                  onChange={setV2Strategy}
                  disabled={action.isPending}
                />
              ) : (
                <BattingPlans
                  strategy={strategy}
                  assessments={m.strategyAssessments}
                  requiresVariation={
                    m.rulesetVersion === "v3.2" || m.rulesetVersion === "v3.4"
                  }
                  adaptsToRepetition={
                    m.rulesetVersion === "v3.3" ||
                    m.rulesetVersion === "v3.4" ||
                    m.rulesetVersion === "v3.5"
                  }
                  approachesUsed={m.state.approaches_used}
                  onChange={setStrategy}
                  disabled={action.isPending}
                />
              )}
              <button
                className="button primary play-button"
                disabled={action.isPending || !session.data}
                onClick={() => action.mutate()}
              >
                {action.isPending
                  ? "Playing it out…"
                  : `Play next ${windowLabel}`}
                <ArrowRight size={20} />
              </button>
              {action.isPending && (
                <p className="subtle" role="status">
                  Simulating the next passage of play and updating the scorecard…
                </p>
              )}
              {action.error instanceof APIError && action.error.status === 409 ? (
                <div className="error-panel" role="alert">
                  <strong>This match changed in another tab.</strong>
                  <p>The latest score has been loaded. Review it before choosing your next plan.</p>
                  <button className="text-link" onClick={() => action.reset()}>
                    Continue from latest state <ArrowRight size={16} />
                  </button>
                </div>
              ) : action.error ? (
                <ErrorPanel error={action.error} />
              ) : null}
              <p className="strategy-footnote">
                {legacy
                  ? "Your next call comes after this window."
                  : "A wicket or no-ball brings your next decision forward. Free hits get their own plan."}{" "}
                In the last two overs, you decide every delivery.
              </p>
            </div>
            <EventFeed match={m} />
          </div>
        </>
      )}
      {!live && (
        <div className="result-actions">
          <Link className="button primary" href="/play">
            Draft again. Chase again. <ArrowRight size={18} />
          </Link>
          <Link className="button secondary" href="/history">
            View match history
          </Link>
          {session.data?.kind !== "user" && (
            <GoogleLink label="Save this match with Google" />
          )}
        </div>
      )}
      <details className="scorecard-details" open={!live}>
        <summary>{live ? "View full scorecard" : "The full story"}</summary>
        <Scorecard match={m} />
      </details>
      {!live && <EventFeed match={m} />}
    </section>
  );
}

function EventFeed({ match }: { match: Match }) {
  return (
    <aside className="event-feed">
      <div className="panel-title">
        <h2>The chase so far</h2>
        <span className="live-dot" />
      </div>
      {match.events.length === 0 ? (
        <div className="empty-feed">
          <CircleDot size={26} />
          <p>
            A new innings.
            <br />
            Your first decision sets the tone.
          </p>
        </div>
      ) : (
        <ol tabIndex={0} aria-label="Match events, newest first">
          {[...match.events].reverse().map((e) => (
            <li
              key={`${e.revision}:${e.sequence}`}
              className={e.wickets ? "wicket-event" : ""}
            >
              <span className="event-over">
                {overs(e.toBall)}
                <small>OVERS</small>
              </span>
              <div>
                <strong>{e.label}</strong>
                <p>
                  {e.kind === "AGGREGATE"
                    ? `${overs(e.fromBall)}–${overs(e.toBall)} overs`
                    : "Delivery"}
                  {e.freeHit && " · Free hit next"}
                </p>
                {e.interruption === "WICKET" && (
                  <p className="event-interruption">
                    Wicket—choose a plan for the new batter.
                  </p>
                )}
                {e.interruption === "NO_BALL" && (
                  <p className="event-interruption">
                    No-ball—choose your free-hit plan.
                  </p>
                )}
              </div>
              <span className="event-score">
                {e.score}/{e.totalWickets}
              </span>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
