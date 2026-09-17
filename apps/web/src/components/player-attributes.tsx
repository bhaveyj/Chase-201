import type { Player } from "@/lib/api";

export function attributeDescription(player: Player) {
  return player.battingPlaystyle
    ? `, ${player.battingPlaystyle}. Control ${player.battingControl}, Rotation ${player.battingRotation}, Power ${player.battingPower} out of 100`
    : "";
}

export function PlayerAttributes({ player }: { player: Player }) {
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
