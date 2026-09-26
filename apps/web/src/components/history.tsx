"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock3 } from "lucide-react";
import { api, overs } from "@/lib/api";
import { ErrorPanel, GoogleLink, Loading, useSession } from "./common";

export function HistoryScreen() {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["history", offset],
    queryFn: () => api.history(offset),
    enabled: session.data?.kind === "user" || session.data?.kind === "guest",
  });
  if (session.isPending) return <Loading />;
  if (session.error)
    return (
      <section className="page-width">
        <ErrorPanel
          error={session.error}
          retry={() => void session.refetch()}
        />
      </section>
    );
  return (
    <section className="page-width history-page">
      <p className="eyebrow">THE RECORD BOOK</p>
      <h1>
        Every chase
        <br />
        <em>has a story.</em>
      </h1>
      <p className="lead-small">
        {session.data?.kind === "guest"
          ? "Your guest innings from this browser, kept for 30 days."
          : "Your innings, your decisions, your cricket history."}
      </p>
      {session.data?.kind === "anonymous" ? (
        <div className="history-empty">
          <Clock3 size={35} />
          <h2>Start your story.</h2>
          <p>
            Play as a guest to see your matches here for 30 days. Sign in later
            to save them to your account.
          </p>
          <GoogleLink />
          <Link className="text-link" href="/play">
            Start a chase <ArrowRight size={16} />
          </Link>
        </div>
      ) : query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorPanel error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <div className="history-list">
            {query.data.matches.length === 0 ? (
              <div className="history-empty">
                <h2>Your first chase is waiting.</h2>
                <Link className="button primary" href="/play">
                  Play your first chase <ArrowRight size={17} />
                </Link>
              </div>
            ) : (
              query.data.matches.map((m) => (
                <Link
                  href={`/match/${m.id}${m.status === "LIVE" ? "" : "/result"}`}
                  key={m.id}
                  className="history-card"
                >
                  <span className={`result-pill ${m.status.toLowerCase()}`}>
                    {m.status === "LIVE" ? "IN PROGRESS" : m.status}
                  </span>
                  <span className="history-score">
                    {m.runs}/{m.wickets}
                    <small>{overs(m.balls)} overs</small>
                  </span>
                  <span className="history-date">
                    {new Date(m.createdAt).toLocaleDateString(undefined, {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                    <small>Target 201</small>
                  </span>
                  <span className="history-cta">
                    {m.status === "LIVE" ? "Resume" : "Scorecard"}
                    <ArrowRight size={19} />
                  </span>
                </Link>
              ))
            )}
          </div>
          <div className="pagination">
            <button
              className="button secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              Previous
            </button>
            <button
              className="button secondary"
              disabled={query.data.nextOffset === null}
              onClick={() => setOffset(query.data.nextOffset!)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
