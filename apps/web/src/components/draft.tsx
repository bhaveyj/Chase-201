"use client";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleDot,
  Shield,
  Sparkles,
  Users,
} from "lucide-react";
import { api, roleLabel, type Draft } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { ErrorPanel, Loading, Steps, useSession } from "./common";
import { SquadPitch } from "./squad-pitch";
import { PlayerAttributes, attributeDescription } from "./player-attributes";
import { DraftLimits } from "./draft-limits";

export function DraftScreen({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const session = useSession();
  const query = useQuery({
    queryKey: ["draft", id],
    queryFn: () => api.draft(id),
  });
  const active = useUI((s) => s.activeSlot);
  const setActive = useUI((s) => s.setActiveSlot);
  const select = useMutation({
    mutationFn: ({ slot, player }: { slot: string; player: string }) =>
      api.select(session.data!, query.data!, slot, player, crypto.randomUUID()),
    onMutate: async ({ slot, player }) => {
      await queryClient.cancelQueries({ queryKey: ["draft", id] });
      const previous = queryClient.getQueryData<Draft>(["draft", id]);
      queryClient.setQueryData<Draft>(["draft", id], (current) =>
        current
          ? {
              ...current,
              battingOrder: [],
              slots: current.slots.map((item) =>
                item.id === slot ? { ...item, selectedPlayerId: player } : item,
              ),
            }
          : current,
      );
      return previous;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["draft", id], data);
    },
    onError: (_error, _variables, previous) => {
      if (previous) queryClient.setQueryData(["draft", id], previous);
      void queryClient.invalidateQueries({ queryKey: ["draft", id] });
    },
  });
  if (query.isPending || session.isPending)
    return <Loading label="Laying out your player options…" />;
  if (query.error || !query.data)
    return (
      <div className="page-width">
        <ErrorPanel error={query.error} retry={() => void query.refetch()} />
      </div>
    );
  const draft = query.data;
  const slot = draft.slots[Math.min(active, 10)];
  const picked = draft.slots.filter((s) => s.selectedPlayerId).length;
  if (draft.status === "CONFIRMED")
    return (
      <section className="page-width">
        <h1>Your XI is ready.</h1>
        <Link
          className="button primary"
          href={draft.matchId ? `/match/${draft.matchId}` : `/team/${id}`}
        >
          Continue <ArrowRight size={18} />
        </Link>
      </section>
    );
  return (
    <section className="page-width draft-page">
      <Steps current={0} />
      <div className="section-heading">
        <div>
          <p className="eyebrow">BUILD YOUR SIDE</p>
          <h1>
            Eleven spots.
            <br className="mobile-only" /> <em>Your call.</em>
          </h1>
          <p className="lead-small">
            Five options for each position. Find the players you believe in.
          </p>
        </div>
        <div className="draft-progress">
          <strong>
            {picked}
            <span>/11</span>
          </strong>
          <span>PLAYERS SELECTED</span>
          <div className="progress-track">
            <i style={{ width: `${(picked / 11) * 100}%` }} />
          </div>
        </div>
      </div>
      <DraftLimits draft={draft} />
      <div className="draft-layout">
        <aside className="squad-panel">
          <div className="panel-title">
            <Users size={18} />
            <h2>Your XI</h2>
            <span>{picked}/11</span>
          </div>
          <SquadPitch
            draft={draft}
            active={active}
            onChoose={(i) => {
              setActive(i);
              select.reset();
            }}
          />
          <div className="role-legend">
            <span data-role="BATTER">Batters</span>
            <span data-role="WICKETKEEPER">Keeper</span>
            <span data-role="ALL_ROUNDER">All-rounders</span>
            <span data-role="BOWLER">Bowlers</span>
          </div>
          <details className="squad-list-details">
            <summary>
              View team list <span>{picked}/11 selected</span>
            </summary>
            <ol className="slot-list">
              {draft.slots.map((s, i) => {
                const player = s.options.find(
                  (p) => p.id === s.selectedPlayerId,
                );
                return (
                  <li key={s.id}>
                    <button
                      className={slot.id === s.id ? "active" : ""}
                      onClick={() => {
                        setActive(i);
                        select.reset();
                      }}
                      aria-current={slot.id === s.id ? "true" : undefined}
                    >
                      <span className="slot-number">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span>
                        <strong>
                          {player?.name ||
                            `Choose ${roleLabel[s.role].toLowerCase()}`}
                        </strong>
                        <small>{roleLabel[s.role]}</small>
                      </span>
                      {player ? (
                        <Check size={15} className="selected-check" />
                      ) : (
                        <span className="empty-dot" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ol>
          </details>
        </aside>
        <div className="offers-panel">
          <div className="offer-heading">
            <span className="eyebrow">
              PICK {String(active + 1).padStart(2, "0")} / 11
            </span>
            <span className="tag">{roleLabel[slot.role]}</span>
          </div>
          <h2>
            {slot.role === "BATTER"
              ? "Build the backbone."
              : slot.role === "WICKETKEEPER"
                ? "Safe hands. Big moments."
                : slot.role === "ALL_ROUNDER"
                  ? "Bring a little of everything."
                  : "Round out your XI."}
          </h2>
          <p className="subtle">
            {[
              "balanced-v1",
              "tradeoffs-v1",
              "simple-v1",
              "real-players-v1",
            ].includes(draft.selectionRuleset ?? "open-v1")
              ? `${slot.ratingLabel} · ${slot.minimumRating}–${slot.maximumRating} OVR. Select one player.`
              : "Select one player to fill this spot."}
          </p>
          <p className="attribute-guide" id="attribute-guide">
            {["simple-v1", "real-players-v1"].includes(
              draft.selectionRuleset ?? "open-v1",
            ) ? (
              <>
                Your approach controls scoring and risk. Adapt your plans to the
                chase.
              </>
            ) : (
              <>
                <strong>Control</strong> helps survival and difficult
                deliveries. <strong>Rotation</strong> turns dots into singles
                and twos. <strong>Power</strong> creates boundaries, especially
                with Aggressive. All bars use the same 0–100 scale. Anchors lead
                with Control, Rotators with Rotation, Hitters with Power.
              </>
            )}
          </p>
          <div className="player-grid">
            {slot.options.map((player) => {
              const selected = player.id === slot.selectedPlayerId;
              const Icon =
                player.role === "BOWLER"
                  ? CircleDot
                  : player.role === "WICKETKEEPER"
                    ? Shield
                    : Sparkles;
              return (
                <button
                  key={player.id}
                  aria-pressed={selected}
                  aria-label={`Select ${player.name}, ${roleLabel[player.role]}, rating ${player.overallRating}${attributeDescription(player)}`}
                  aria-describedby="attribute-guide"
                  className={`player-card ${["simple-v1", "real-players-v1"].includes(draft.selectionRuleset ?? "open-v1") ? "simple-card" : ""} ${selected ? "selected" : ""}`}
                  data-role={player.role}
                  disabled={select.isPending || !session.data}
                  onClick={() =>
                    select.mutate({ slot: slot.id, player: player.id })
                  }
                >
                  <div className="card-top">
                    <Icon size={20} />
                    <span className="rating">
                      {player.overallRating}
                      <small>OVR</small>
                    </span>
                  </div>
                  <div className="player-monogram" aria-hidden="true">
                    {player.name
                      .split(" ")
                      .map((s) => s[0])
                      .join("")}
                  </div>
                  <div className="player-info">
                    <span>{roleLabel[player.role]}</span>
                    <h3>{player.name}</h3>
                  </div>
                  <PlayerAttributes player={player} />
                  <div className="card-select">
                    {selected ? (
                      <>
                        Selected <Check size={16} />
                      </>
                    ) : (
                      <>
                        Select player <span>+</span>
                      </>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
          {select.error && <ErrorPanel error={select.error} />}
          <div className="draft-controls">
            <button
              className="button secondary"
              disabled={active === 0 || select.isPending}
              onClick={() => setActive(active - 1)}
            >
              <ArrowLeft size={17} /> Previous
            </button>
            {active < 10 ? (
              <button
                className="button primary"
                disabled={!slot.selectedPlayerId || select.isPending}
                onClick={() => setActive(active + 1)}
              >
                Next position <ArrowRight size={17} />
              </button>
            ) : picked === 11 ? (
              <Link className="button primary" href={`/team/${id}`}>
                Set batting order <ArrowRight size={17} />
              </Link>
            ) : (
              <button
                className="button primary"
                onClick={() =>
                  setActive(draft.slots.findIndex((s) => !s.selectedPlayerId))
                }
              >
                Fill remaining spots <ArrowRight size={17} />
              </button>
            )}
          </div>
          <p className="draft-note">
            {[
              "balanced-v1",
              "tradeoffs-v1",
              "simple-v1",
              "real-players-v1",
            ].includes(draft.selectionRuleset ?? "open-v1")
              ? "Your two star picks can bat anywhere in the XI. Set the order next."
              : "No budgets. No credits. Just cricket judgment."}
          </p>
        </div>
      </div>
    </section>
  );
}
