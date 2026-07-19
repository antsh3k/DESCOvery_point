import type { Fund, Match } from "@/lib/types";

import { Badge } from "./Badge";
import { ScoreBar } from "./ScoreBar";

// `hardGate` chips (geo) show a red ✗ on a mismatch because a clear miss there
// excludes the fund. Informational chips (sector) never show red: a mismatch
// only means "no literal overlap" — the LLM judge decides real sector fit, so a
// red ✗ next to a strong match would be misleading.
function matchChip(label: string, value: unknown, hardGate = false) {
  if (value === true) return <Badge key={label} tone="green">{label} ✓</Badge>;
  if (value === false)
    return hardGate ? (
      <Badge key={label} tone="red">{label} ✗</Badge>
    ) : (
      <Badge key={label} tone="slate">{label} —</Badge>
    );
  return (
    <Badge key={label} tone="slate">
      {label} —
    </Badge>
  );
}

export function MatchCard({
  fund,
  match,
  composite,
  rank,
}: {
  fund: Fund;
  match: Match;
  composite: number | null;
  rank: number;
}) {
  const matched = (match.matched_on ?? {}) as Record<string, unknown>;
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-400">
              #{rank}
            </span>
            <h3 className="text-lg font-semibold">{fund.name}</h3>
            {fund.mandate_source === "ai_inferred" && (
              <Badge tone="amber">AI-inferred mandate</Badge>
            )}
          </div>
          {fund.firm && (
            <p className="text-sm text-slate-500">{fund.firm}</p>
          )}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-accent">
            {composite === null ? "—" : Math.round(composite)}
          </div>
          <div className="text-xs text-slate-400">composite</div>
        </div>
      </div>

      <div className="my-4 grid gap-3 sm:grid-cols-3">
        <ScoreBar label="Thesis" value={match.thesis_score} />
        <ScoreBar label="Numeric" value={match.numeric_score} />
        <ScoreBar label="Strategy" value={match.strategy_score} />
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {matchChip("sector", matched.sector)}
        {matchChip("geo", matched.geo, true)}
        {fund.sectors.slice(0, 3).map((s) => (
          <Badge key={s} tone="blue">
            {s}
          </Badge>
        ))}
      </div>

      {match.rationale && (
        <p className="mb-3 text-sm leading-relaxed text-slate-700">
          <span className="font-medium">Why this fits: </span>
          {match.rationale}
        </p>
      )}

      {fund.source_url && (
        <a
          href={fund.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-accent hover:underline"
        >
          Fund source →
        </a>
      )}
    </article>
  );
}
