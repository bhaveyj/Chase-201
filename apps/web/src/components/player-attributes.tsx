import type { Player } from "@/lib/api";

export function attributeDescription(player: Player) {
  if (!player.battingPlaystyle && player.battingRating != null)
    return `, Batting ${player.battingRating} out of 100`;
  return player.battingPlaystyle
    ? `, ${player.battingPlaystyle}. Control ${player.battingControl}, Rotation ${player.battingRotation}, Power ${player.battingPower} out of 100`
    : "";
}

export function PlayerAttributes({ player }: { player: Player }) {
  if (!player.battingPlaystyle && player.battingRating != null)
    return (
      <div className="player-attributes simple-batting" aria-hidden="true">
        <div className="attribute-row">
          <span>Batting</span>
          <span className="attribute-track">
            <i style={{ width: `${player.battingRating}%` }} />
          </span>
          <span>{player.battingRating}</span>
        </div>
      </div>
    );
  if (!player.battingPlaystyle) return null;
  return (
    <div className="player-attributes" aria-hidden="true">
      <strong className="playstyle">{player.battingPlaystyle}</strong>
      {(
        [
          ["Control", player.battingControl],
          ["Rotation", player.battingRotation],
          ["Power", player.battingPower],
        ] as const
      ).map(([label, value]) => (
        <div className="attribute-row" key={label}>
          <span>{label}</span>
          <span className="attribute-track">
            <i style={{ width: `${value ?? 0}%` }} />
          </span>
          <span>{value}</span>
        </div>
      ))}
    </div>
  );
}
