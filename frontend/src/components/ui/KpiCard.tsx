type KpiCardProps = {
  label: string;
  value: string | number;
  hint?: string;
};

export function KpiCard({ hint, label, value }: KpiCardProps) {
  return (
    <article className="kpi-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </article>
  );
}
