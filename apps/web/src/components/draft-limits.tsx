import type { Draft } from "@/lib/api";

export function DraftLimits({ draft }: { draft: Draft }) {
  if (
    !["balanced-v1", "tradeoffs-v1", "simple-v1", "real-players-v1"].includes(
      draft.selectionRuleset ?? "open-v1",
    )
  )
    return null;
  const stars = draft.slots.filter((s) => (s.minimumRating ?? 1) >= 90);
  const core = draft.slots.filter((s) => (s.maximumRating ?? 100) < 90);
  const specialists = draft.slots.filter((s) => s.ratingLabel === "Specialist");
  const realPlayers = draft.selectionRuleset === "real-players-v1";
  return (
    <aside className="draft-limits" aria-label="XI rating limits">
      <div>
        <strong>Two stars. A balanced XI.</strong>
        <p>
          {realPlayers
            ? "One batter and one all-rounder rated 90–100. Five core players rated 75–89. A keeper and three bowlers rated 75–100."
            : "One batter and one all-rounder rated 90–92. Nine players rated 78–85."}
        </p>
      </div>
      <div className="draft-limit-counts" aria-live="polite">
        {stars.map((slot) => (
          <span key={slot.id} data-filled={!!slot.selectedPlayerId}>
            {slot.role === "BATTER" ? "Star batter" : "Star all-rounder"}
            <b>{slot.selectedPlayerId ? "1" : "0"}/1</b>
          </span>
        ))}
        <span data-filled={core.every((s) => s.selectedPlayerId)}>
          Core players
          <b>
            {core.filter((s) => s.selectedPlayerId).length}/{core.length}
          </b>
        </span>
        {realPlayers && (
          <span data-filled={specialists.every((s) => s.selectedPlayerId)}>
            Specialists
            <b>
              {specialists.filter((s) => s.selectedPlayerId).length}/
              {specialists.length}
            </b>
          </span>
        )}
      </div>
    </aside>
  );
}
