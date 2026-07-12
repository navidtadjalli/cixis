// Static backdrop: sky gradient, a few clouds, green field.
//
// This used to animate drifting clouds and one walking camel per occupied
// table. On the cafe's 3-core box Electron composites in software, so every
// moving layer costs CPU on the compositor thread and the cost grew with the
// order count — the POS got slowest exactly when it was busiest. Nothing here
// moves any more, so the backdrop paints once and then costs nothing.
const CLOUDS = [
  { left: "6%", top: "8%", scale: 1.0, opacity: 0.5 },
  { left: "27%", top: "16%", scale: 0.7, opacity: 0.4 },
  { left: "48%", top: "5%", scale: 1.3, opacity: 0.45 },
  { left: "69%", top: "22%", scale: 0.9, opacity: 0.35 },
  { left: "87%", top: "12%", scale: 0.6, opacity: 0.45 },
];

function Cloud({ opacity }: { opacity: number }) {
  return (
    <svg width="160" height="90" viewBox="0 0 160 90" fill="none" style={{ opacity }}>
      <g fill="#ffffff">
        <ellipse cx="50" cy="55" rx="40" ry="28" />
        <ellipse cx="85" cy="45" rx="45" ry="33" />
        <ellipse cx="115" cy="58" rx="35" ry="25" />
        <ellipse cx="80" cy="68" rx="60" ry="20" />
      </g>
    </svg>
  );
}

export function AnimatedBackground() {
  return (
    <div className="anim-bg" aria-hidden="true">
      <div className="anim-sky" />

      {CLOUDS.map((c, i) => (
        <div
          key={i}
          className="anim-cloud"
          style={{
            left: c.left,
            top: c.top,
            ["--cloud-scale" as string]: String(c.scale),
          }}
        >
          <Cloud opacity={c.opacity} />
        </div>
      ))}

      <div className="anim-field" />
    </div>
  );
}
