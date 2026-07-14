import type { PropsWithChildren } from "react";

type BadgeProps = PropsWithChildren<{
  tone?:
    | "neutral"
    | "info"
    | "success"
    | "warning"
    | "danger"
    | "department"
    | "muted";
}>;

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
