export function Pitch({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`pitch-art ${compact ? "compact" : ""}`} aria-hidden="true">
      <div className="pitch-grain" />
      <svg viewBox="0 0 600 520" fill="none">
        <defs>
          <radialGradient id="field">
            <stop stopColor="#557c4f" />
            <stop offset="1" stopColor="#183a2a" />
          </radialGradient>
          <pattern
            id="stripes"
            width="90"
            height="90"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(-28)"
          >
            <rect width="45" height="90" fill="#bdd999" opacity=".07" />
          </pattern>
        </defs>
        <ellipse cx="300" cy="270" rx="268" ry="207" fill="url(#field)" />
        <ellipse cx="300" cy="270" rx="268" ry="207" fill="url(#stripes)" />
        <ellipse
          cx="300"
          cy="270"
          rx="249"
          ry="191"
          stroke="#e1ebc1"
          strokeOpacity=".55"
          strokeWidth="2"
        />
        <ellipse
          cx="300"
          cy="270"
          rx="134"
          ry="101"
          stroke="#e1ebc1"
          strokeOpacity=".35"
          strokeDasharray="6 7"
        />
        <g transform="rotate(-28 300 270)">
          <rect x="272" y="183" width="56" height="174" rx="4" fill="#c0b28c" />
          <rect x="278" y="195" width="44" height="150" fill="#b5a77f" />
          <path
            d="M261 207h78M261 333h78M282 192v27m36-27v27m-36 102v27m36-27v27"
            stroke="#fffae7"
            strokeWidth="2"
          />
          <path
            d="M295 198v-12m5 12v-12m5 12v-12m-10 160v-12m5 12v-12m5 12v-12"
            stroke="#fff"
            strokeWidth="3"
          />
          <circle cx="322" cy="316" r="8" fill="#d4f66a" />
          <path
            d="m324 324 8 16"
            stroke="#e9d4a1"
            strokeWidth="5"
            strokeLinecap="round"
          />
          <circle cx="268" cy="224" r="7" fill="#d4f66a" />
          <circle cx="302" cy="153" r="7" fill="#f4efe0" />
        </g>
        <g fill="#f4efe0">
          <circle cx="442" cy="179" r="5" />
          <circle cx="422" cy="388" r="5" />
          <circle cx="143" cy="283" r="5" />
          <circle cx="217" cy="126" r="5" />
          <circle cx="168" cy="395" r="5" />
          <circle cx="492" cy="290" r="5" />
          <circle cx="324" cy="428" r="5" />
        </g>
        <path
          d="M321 303 Q398 314 472 244"
          stroke="#d4f66a"
          strokeWidth="2"
          strokeDasharray="4 5"
        />
        <circle cx="472" cy="244" r="5" fill="#df6550" />
      </svg>
      <span className="field-caption">THE STAGE IS SET.</span>
      <span className="field-coordinate">20° / 120 BALLS</span>
    </div>
  );
}
