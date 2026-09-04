import type { ReactNode } from "react";

export type StatusTone = "primary" | "success" | "warning" | "danger" | "neutral";

export function StatusBadge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: StatusTone;
  className?: string;
}) {
  return (
    <span className={`status-badge status-badge-${tone}${className ? ` ${className}` : ""}`}>
      {children}
    </span>
  );
}
