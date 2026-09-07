import type { Draft } from "@/lib/api";
import { roleLabel } from "@/lib/api";

const positions = [
  [28, 16],
  [72, 16],
  [18, 37],
  [82, 37],
  [50, 28],
  [50, 10],
  [22, 60],
  [78, 60],
  [25, 82],
  [50, 71],
  [75, 82],
];
const roleCode: Record<string, string> = {
  BATTER: "BAT",
  WICKETKEEPER: "WK",
  ALL_ROUNDER: "AR",
  BOWLER: "BWL",
};

export function SquadPitch({
  draft,
  active,
  onChoose,
}: {
  draft: Draft;
  active?: number;
  onChoose?: (index: number) => void;
}) {
  return (
    <div
      className="squad-field"
      role="group"
      aria-label="Your XI on the cricket field"
    >
      <div className="boundary" aria-hidden="true" />
      <div className="inner-ring" aria-hidden="true" />
      <div className="wicket-strip" aria-hidden="true" />
      {draft.slots.map((slot, i) => {
        const player = slot.options.find((p) => p.id === slot.selectedPlayerId);
        const contents = (
          <>
            <span className={`field-marker ${player ? "filled" : ""}`}>
              {player
                ? player.name
                    .split(" ")
                    .map((s) => s[0])
                    .slice(0, 2)
                    .join("")
                : "+"}
              {player && <small>{player.overallRating}</small>}
            </span>
            <span className="field-name">
              {player?.name.split(" ").at(-1) ||
                `${roleCode[slot.role]} ${i + 1}`}
            </span>
          </>
        );
        const style = {
          left: `${positions[i][0]}%`,
          top: `${positions[i][1]}%`,
        };
        return onChoose ? (
          <button
            key={slot.id}
            className={`field-player ${active === i ? "active" : ""}`}
            data-role={slot.role}
            style={style}
            onClick={() => onChoose(i)}
            aria-label={`Edit spot ${i + 1}: ${player?.name || roleLabel[slot.role]}`}
            aria-current={active === i ? "true" : undefined}
          >
            {contents}
          </button>
        ) : (
          <div
            key={slot.id}
            className="field-player"
            data-role={slot.role}
            style={style}
          >
            {contents}
          </div>
        );
      })}
      <span className="field-bottom-label">YOUR XI · THE 201 CHALLENGE</span>
    </div>
  );
}
