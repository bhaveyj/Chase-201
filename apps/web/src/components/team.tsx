"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  Flag,
} from "lucide-react";
import { api, roleLabel } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { ErrorPanel, Loading, Steps, useSession } from "./common";
import { SquadPitch } from "./squad-pitch";

export function TeamScreen({ id }: { id: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const session = useSession();
  const query = useQuery({
    queryKey: ["draft", id],
    queryFn: () => api.draft(id),
  });
  const ui = useUI();
  const draft = query.data;
  const players =
    draft?.slots.flatMap((s) =>
      s.options.filter((p) => p.id === s.selectedPlayerId),
    ) || [];
  const order =
    ui.draftId === id &&
    ui.pendingOrder &&
    ui.pendingOrder.length === players.length &&
    ui.pendingOrder.every((p) => players.some((x) => x.id === p))
      ? ui.pendingOrder
      : draft?.battingOrder.length
        ? draft.battingOrder
        : players.map((p) => p.id);
  const confirm = useMutation({
    mutationFn: async () => {
      let d = await api.draft(id);
      if (d.matchId) {
        router.push(`/match/${d.matchId}`);
        return;
      }
      const s = await api.session();
      if (d.status !== "CONFIRMED") {
        d = await api.order(s, d, order, crypto.randomUUID());
        client.setQueryData(["draft", id], d);
        d = await api.confirm(s, d, crypto.randomUUID());
        client.setQueryData(["draft", id], d);
      }
      const match = await api.createMatch(s, d, crypto.randomUUID());
      client.setQueryData(["match", match.id], match);
      router.push(`/match/${match.id}`);
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: ["draft", id] });
    },
  });
  if (query.isPending || session.isPending) return <Loading />;
  if (query.error || !draft)
    return (
      <section className="page-width">
        <ErrorPanel error={query.error} />
      </section>
    );
  if (players.length !== 11)
    return (
      <section className="page-width">
        <h1>Your XI needs a few more names.</h1>
        <Link className="button primary" href={`/draft/${id}`}>
          Complete your draft <ArrowRight size={18} />
        </Link>
      </section>
    );
  function move(index: number, delta: number) {
    const next = [...order];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    ui.editOrder(id, next);
  }
  return (
    <section className="page-width team-page">
      <Steps current={1} />
      <p className="eyebrow">THE TEAM SHEET</p>
      <h1>
        Set the tone.
        <br />
        <em>Set the order.</em>
      </h1>
      <p className="lead-small">
        Who opens? Who brings it home? Arrange your batting lineup.
      </p>
      <div className="team-layout">
        <ol className="batting-order">
          {order.map((playerId, i) => {
            const p = players.find((p) => p.id === playerId)!;
            return (
              <li key={p.id} data-role={p.role}>
                <span className="order-position">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="order-name">
                  <strong>{p.name}</strong>
                  <small>
                    {roleLabel[p.role]}{" "}
                    {i < 2 && <span className="opener-tag">OPENER</span>}
                  </small>
                </span>
                <span className="order-rating">
                  {p.overallRating}
                  <small>OVR</small>
                </span>
                <div className="reorder-buttons">
                  <button
                    className="icon-button"
                    aria-label={`Move ${p.name} up`}
                    disabled={
                      i === 0 ||
                      confirm.isPending ||
                      draft.status === "CONFIRMED"
                    }
                    onClick={() => move(i, -1)}
                  >
                    <ArrowUp size={17} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`Move ${p.name} down`}
                    disabled={
                      i === 10 ||
                      confirm.isPending ||
                      draft.status === "CONFIRMED"
                    }
                    onClick={() => move(i, 1)}
                  >
                    <ArrowDown size={17} />
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
        <aside className="team-confirm-panel">
          <SquadPitch draft={draft} />
          <Flag size={26} />
          <p className="eyebrow">YOUR MISSION</p>
          <h2>201 to win.</h2>
          <p>
            Your XI is ready. A balanced opposition is waiting. Once you
            confirm, this team is locked for the chase.
          </p>
          <ul className="checklist">
            {["5 batters", "1 wicketkeeper", "2 all-rounders", "3 bowlers"].map(
              (x) => (
                <li key={x}>
                  <Check size={16} />
                  {x}
                </li>
              ),
            )}
          </ul>
          <button
            className="button primary"
            disabled={confirm.isPending}
            onClick={() => confirm.mutate()}
          >
            {confirm.isPending
              ? "Taking the field…"
              : draft.status === "CONFIRMED"
                ? "Continue to chase"
                : "Confirm XI & play"}
            <ArrowRight size={18} />
          </button>
          {draft.status !== "CONFIRMED" && (
            <Link className="text-link" href={`/draft/${id}`}>
              <ArrowLeft size={16} /> Back to draft
            </Link>
          )}
          {confirm.error && <ErrorPanel error={confirm.error} />}
        </aside>
      </div>
    </section>
  );
}
