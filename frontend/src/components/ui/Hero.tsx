import type { PropsWithChildren, ReactNode } from "react";

type HeroProps = PropsWithChildren<{
  eyebrow: string;
  title: string;
  subtitle: string;
  actions?: ReactNode;
}>;

export function Hero({ actions, eyebrow, subtitle, title, children }: HeroProps) {
  return (
    <section className="hero">
      <div className="hero-copy">
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {actions ? <div className="hero-actions">{actions}</div> : null}
      {children}
    </section>
  );
}
