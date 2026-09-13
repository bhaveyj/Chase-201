import type { Draft } from "@/lib/api";

export function DraftLimits({ draft }: { draft: Draft }) {
  if (draft.selectionRuleset !== "balanced-v1") return null;
  const stars = draft.slots.filter((s) => (s.minimumRating ?? 1) >= 90);
  const core = draft.slots.filter((s) => (s.maximumRating ?? 100) <= 85);
  return (
    <aside className="draft-limits" aria-label="XI rating limits">
      <div>
        <strong>Two stars. A balanced XI.</strong>
        <p>
          One batter and one all-rounder rated 90–92. Nine players rated 78–85.
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
          Core players<b>{core.filter((s) => s.selectedPlayerId).length}/9</b>
        </span>
      </div>
    </aside>
  );
}
