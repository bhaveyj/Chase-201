"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  CircleDot,
  Shield,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";
import { api, Match, overs, Strategy } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { ErrorPanel, GoogleLink, Loading, useSession } from "./common";

const intents: {
  value: Strategy["intent"];
  title: string;
  description: string;
  icon: typeof Shield;
}[] = [
  {
    value: "DEFEND",
    title: "Defend",
    description: "Stay in. Build a platform.",
    icon: Shield,
  },
  {
    value: "ROTATE",
    title: "Rotate",
    description: "Find gaps. Keep it moving.",
    icon: TrendingUp,
  },
  {
    value: "ATTACK",
    title: "Attack",
    description: "Go big. Take them on.",
    icon: Zap,
  },
];
const risks: {
  value: Strategy["riskFocus"];
  title: string;
  description: string;
}[] = [
  {
    value: "PROTECT_WICKETS",
    title: "Protect wickets",
    description: "Keep your batters in the game.",
  },
  {
    value: "BALANCED",
    title: "Balanced",
    description: "A measured approach to the chase.",
  },
  {
    value: "MAXIMIZE_RUNS",
    title: "Maximize runs",
    description: "More scoring ambition, more wicket risk.",
  },
];

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
  const m = query.data;
  const action = useMutation({
    mutationFn: () =>
      api.decide(session.data!, m!, strategy, crypto.randomUUID()),
    onSuccess: (next) => client.setQueryData(["match", id], next),
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
  const needed = Math.max(0, 201 - s.runs),
    left = 120 - s.balls;
  const live = s.status === "LIVE";
  const windowLabel =
    s.balls >= 108
      ? "delivery"
      : m.decisionWindow === 3
        ? "3 balls"
        : `${m.decisionWindow / 6} ${m.decisionWindow === 6 ? "over" : "overs"}`;
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
        <span className="subtle">T20 · TARGET 201</span>
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
                ? "200 apiece. The match is tied. No super over."
                : `The opposition won by ${200 - s.runs} runs.`}
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
            <strong>{live ? needed : 201}</strong>
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
          <i style={{ width: `${Math.min(100, (s.runs / 201) * 100)}%` }} />
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
                  <small>{i === 0 ? "ON STRIKE" : "NON-STRIKER"}</small>
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
              </span>
            </div>
          </div>
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
              <fieldset disabled={action.isPending}>
                <legend>Batting intent</legend>
                <div className="intent-grid">
                  {intents.map(({ value, title, description, icon: Icon }) => (
                    <label
                      key={value}
                      className={`intent-option ${strategy.intent === value ? "selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name="intent"
                        value={value}
                        checked={strategy.intent === value}
                        onChange={() => setStrategy({ intent: value })}
                      />
                      <Icon size={23} />
                      <strong>{title}</strong>
                      <span>{description}</span>
                      <i>{strategy.intent === value && <Check size={12} />}</i>
                    </label>
                  ))}
                </div>
              </fieldset>
              <fieldset disabled={action.isPending} className="risk-field">
                <legend>Risk focus</legend>
                <div className="risk-options">
                  {risks.map(({ value, title }) => (
                    <label
                      key={value}
                      className={strategy.riskFocus === value ? "selected" : ""}
                    >
                      <input
                        type="radio"
                        name="risk"
                        checked={strategy.riskFocus === value}
                        onChange={() => setStrategy({ riskFocus: value })}
                      />
                      {title}
                    </label>
                  ))}
                </div>
                <p className="subtle">
                  {
                    risks.find((r) => r.value === strategy.riskFocus)
                      ?.description
                  }
                </p>
              </fieldset>
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
              {action.error && <ErrorPanel error={action.error} />}
              <p className="strategy-footnote">
                Your next call comes after this window. In the last two overs,
                you decide every delivery.
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
          {session.data?.kind !== "user" ? (
            <GoogleLink label="Save this match with Google" />
          ) : (
            <Link className="button secondary" href="/history">
              View match history
            </Link>
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
