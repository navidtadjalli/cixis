import type { HTMLAttributes, ReactNode } from "react";

type BadgeTone = "default" | "good" | "warn" | "bad" | "accent";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
  children: ReactNode;
};

const toneClasses: Record<BadgeTone, string> = {
  default: "border-border bg-surface-2 text-muted",
  good: "border-good/30 bg-good/10 text-good",
  warn: "border-warn/30 bg-warn/10 text-warn",
  bad: "border-bad/30 bg-bad/10 text-bad",
  accent: "border-accent/30 bg-accent/10 text-accent",
};

export function Badge({
  tone = "default",
  className = "",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold",
        toneClasses[tone],
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </span>
  );
}
