import type { Fund, Match } from "@/lib/types";

import { Badge } from "./Badge";
import { ScoreBar } from "./ScoreBar";
import { moneyRange } from "@/lib/format";

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

function FitScore({ value }: { value: number | null }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="w-28 shrink-0 text-right">
      <div className="text-3xl font-bold leading-none text-ink">
        {value === null ? "—" : Math.round(value)}
      </div>
      <div className="mt-1 text-xs uppercase tracking-wide text-slate-400">
        Fit score
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-slate-100">
        <div
          className="h-1.5 rounded-full bg-accent"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
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
  const check = moneyRange(fund.check_size_min_usd_m, fund.check_size_max_usd_m);

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 hover:shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white">
            {rank}
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold text-ink">{fund.name}</h3>
              {fund.mandate_source === "ai_inferred" && (
                <Badge tone="amber">AI-inferred mandate</Badge>
              )}
            </div>
            {fund.firm && <p className="text-sm text-slate-500">{fund.firm}</p>}
          </div>
        </div>
        <FitScore value={composite} />
      </div>

      {fund.thesis && (
        <p className="mt-3 text-sm italic text-slate-500">{fund.thesis}</p>
      )}

      {match.rationale && (
        <p className="mt-3 text-sm leading-relaxed text-slate-700">
          <span className="font-medium">Why this fits: </span>
          {match.rationale}
        </p>
      )}

      <div className="my-4 grid gap-3 sm:grid-cols-3">
        <ScoreBar label="Thesis" value={match.thesis_score} />
        <ScoreBar label="Numeric" value={match.numeric_score} />
        <ScoreBar label="Strategy" value={match.strategy_score} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {matchChip("sector", matched.sector)}
        {matchChip("geo", matched.geo, true)}
        {check && <Badge tone="slate">{check}</Badge>}
        {fund.sectors.slice(0, 3).map((s) => (
          <Badge key={s} tone="blue">
            {s}
          </Badge>
        ))}
        {fund.geographies.length > 0 && (
          <Badge tone="slate">{fund.geographies.join(", ")}</Badge>
        )}
      </div>

      {fund.source_url && (
        <a
          href={fund.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-block text-sm text-accent hover:underline"
        >
          Fund source →
        </a>
      )}
    </article>
  );
}
