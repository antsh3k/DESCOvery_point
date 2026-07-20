"use client";

import { useState } from "react";

import type { Fund, Match } from "@/lib/types";

import { Badge } from "./Badge";
import { ScoreBar } from "./ScoreBar";
import { PILLARS } from "@/lib/pillars";
import { money, moneyCompact, moneyRange, shortDate } from "@/lib/format";

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

function DetailRow({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="text-sm text-ink">{value}</dd>
    </div>
  );
}

function FundDetails({ fund }: { fund: Fund }) {
  const ebitda = moneyRange(fund.ebitda_min_usd_m, fund.ebitda_max_usd_m);
  const revenue = moneyRange(fund.revenue_min_usd_m, fund.revenue_max_usd_m);
  const check = moneyRange(fund.check_size_min_usd_m, fund.check_size_max_usd_m);

  // Regulatory fields (Form ADV / Form D) — straight from the filing, not
  // LLM-inferred; absent for seed/manual/url_extracted funds.
  const hasRegulatoryData =
    fund.gross_asset_value_usd !== null ||
    fund.amount_raised_usd !== null ||
    fund.investor_count !== null ||
    fund.filing_date !== null ||
    fund.auditor_name !== null ||
    fund.prime_broker_name !== null ||
    fund.custodian_name !== null;

  return (
    <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Mandate
        </p>
        <dl className="grid gap-3 sm:grid-cols-3">
          <DetailRow label="Stage" value={fund.stage} />
          <DetailRow label="Check size" value={check} />
          <DetailRow label="EBITDA" value={ebitda} />
          <DetailRow label="Revenue" value={revenue} />
        </dl>
        {fund.sectors.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {fund.sectors.map((s) => (
              <Badge key={s} tone="blue">
                {s}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {hasRegulatoryData && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Regulatory filing data
          </p>
          <dl className="grid gap-3 sm:grid-cols-3">
            <DetailRow label="Fund size (AUM)" value={moneyCompact(fund.gross_asset_value_usd)} />
            <DetailRow label="Amount raised" value={moneyCompact(fund.amount_raised_usd)} />
            <DetailRow
              label="Investors"
              value={fund.investor_count !== null ? String(fund.investor_count) : null}
            />
            <DetailRow label="Last filing" value={shortDate(fund.filing_date)} />
            <DetailRow label="Auditor" value={fund.auditor_name} />
            <DetailRow label="Prime broker" value={fund.prime_broker_name} />
            <DetailRow label="Custodian" value={fund.custodian_name} />
            <DetailRow label="Fund type" value={fund.fund_type_raw} />
          </dl>
        </div>
      )}

      <div className="flex flex-wrap gap-4 text-sm">
        {fund.website_url && (
          <a
            href={fund.website_url}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
          >
            Fund / firm website →
          </a>
        )}
        {fund.source_url && fund.source_url !== fund.website_url && (
          <a
            href={fund.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
          >
            Where this data came from →
          </a>
        )}
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
  const [expanded, setExpanded] = useState(false);
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
        {PILLARS.map(({ key, label, description, how }) => (
          <ScoreBar
            key={key}
            label={label}
            hint={description}
            detail={how}
            value={match[`${key}_score`]}
          />
        ))}
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

      <button
        onClick={() => setExpanded((v) => !v)}
        className="mt-4 flex items-center gap-1 text-sm font-medium text-accent hover:underline"
      >
        {expanded ? "Hide details" : "Show all details & source"}
        <span className={`transition-transform ${expanded ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>

      {expanded && <FundDetails fund={fund} />}
    </article>
  );
}
