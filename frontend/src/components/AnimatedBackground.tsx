import { useMemo } from "react";
import camelIcon from "../assets/camel.png";

type AnimatedBackgroundProps = {
  /** Number of camels to render — one per on-going order. */
  camelCount: number;
};

// Deterministic-ish pseudo random so layout stays stable between renders for a
// given index (no re-shuffling on every parent render).
function rand(seed: number) {
  const x = Math.sin(seed * 999.13) * 10000;
  return x - Math.floor(x);
}

const CLOUDS = [
  { top: "8%", scale: 1.0, duration: 90, delay: 0, opacity: 0.5 },
  { top: "16%", scale: 0.7, duration: 70, delay: -20, opacity: 0.4 },
  { top: "5%", scale: 1.3, duration: 120, delay: -50, opacity: 0.45 },
  { top: "22%", scale: 0.9, duration: 100, delay: -75, opacity: 0.35 },
  { top: "12%", scale: 0.6, duration: 60, delay: -35, opacity: 0.45 },
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

export function AnimatedBackground({ camelCount }: AnimatedBackgroundProps) {
  const camels = useMemo(() => {
    const n = Math.min(Math.max(camelCount, 0), 15);
    return Array.from({ length: n }, (_, i) => {
      const r1 = rand(i + 1);
      const r2 = rand(i + 100);
      const r3 = rand(i + 200);
      return {
        // vertical placement inside the green field band
        bottom: 4 + r1 * 60, // px from field floor
        size: 46 + Math.round(r2 * 34), // 46–80px
        duration: 18 + r3 * 26, // 18–44s
        delay: -Math.round(r1 * 40), // staggered start
        reverse: r2 > 0.5, // travel direction
      };
    });
  }, [camelCount]);

  return (
    <div className="anim-bg" aria-hidden="true">
      {/* sky */}
      <div className="anim-sky" />

      {/* drifting clouds */}
      {CLOUDS.map((c, i) => (
        <div
          key={i}
          className="anim-cloud"
          style={{
            top: c.top,
            ["--cloud-scale" as string]: String(c.scale),
            animationDuration: `${c.duration}s`,
            animationDelay: `${c.delay}s`,
          }}
        >
          <Cloud opacity={c.opacity} />
        </div>
      ))}

      {/* green field */}
      <div className="anim-field">
        {camels.map((cm, i) => (
          <img
            key={i}
            src={camelIcon}
            alt=""
            className={`anim-camel${cm.reverse ? " anim-camel--rev" : ""}`}
            style={{
              bottom: `${cm.bottom}px`,
              width: `${cm.size}px`,
              animationDuration: `${cm.duration}s`,
              animationDelay: `${cm.delay}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
