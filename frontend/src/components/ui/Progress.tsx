type ProgressProps = {
  label: string;
  value: number;
  max: number;
};

export function Progress({ label, max, value }: ProgressProps) {
  const width = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;

  return (
    <div className="progress-block">
      <div className="progress-copy">
        <span>{label}</span>
        <strong>{width}%</strong>
      </div>
      <div className="progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
