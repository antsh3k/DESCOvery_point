export function ScoreBar({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | null;
  hint?: string;
}) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span title={hint} className={hint ? "cursor-help" : undefined}>
          {label}
        </span>
        <span>{value === null ? "n/a" : Math.round(value)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-100">
        <div
          className={`h-1.5 rounded-full ${value === null ? "bg-slate-300" : "bg-accent"}`}
          style={{ width: `${value === null ? 100 : pct}%`, opacity: value === null ? 0.3 : 1 }}
        />
      </div>
    </div>
  );
}
