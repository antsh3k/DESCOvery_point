import type { Company } from "@/lib/types";

import { Badge } from "./Badge";
import { SourceList } from "./SourceList";
import { money, statusTone } from "@/lib/format";

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <span className="text-slate-400">{icon}</span>
        {label}
      </div>
      <div className="text-sm font-medium text-ink">{value}</div>
    </div>
  );
}

const iconCls = "h-4 w-4";

function IndustryIcon() {
  return (
    <svg viewBox="0 0 24 24" className={iconCls} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 21h18M4 21V8l6-4v17M14 21V10l6 3v8M8 9v0M8 13v0M8 17v0" />
    </svg>
  );
}
function LocationIcon() {
  return (
    <svg viewBox="0 0 24 24" className={iconCls} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}
function SizeIcon() {
  return (
    <svg viewBox="0 0 24 24" className={iconCls} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1A4 4 0 0 1 16 11" />
    </svg>
  );
}

export function CompanySummary({
  company,
  analyzedWith,
  enriching,
}: {
  company: Company;
  analyzedWith?: string | null;
  enriching?: boolean;
}) {
  const location =
    [company.location_region, company.location_country]
      .filter(Boolean)
      .join(", ") || "unknown";

  // Prefer revenue as the headline size; fall back to employees, then unknown.
  const size =
    company.revenue_estimate_usd_m !== null
      ? `${money(company.revenue_estimate_usd_m)} revenue`
      : company.size_employees !== null
        ? `${company.size_employees} employees`
        : "not disclosed";

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink">
            {company.name ?? company.url}
          </h1>
          <a
            href={company.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-accent hover:underline"
          >
            {company.url} ↗
          </a>
        </div>
        <div className="flex items-center gap-2">
          {enriching && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
              Enriching…
            </span>
          )}
          {analyzedWith && (
            <Badge tone="slate">Analyzed with {analyzedWith}</Badge>
          )}
          <Badge tone={statusTone(company.status)}>{company.status}</Badge>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={<IndustryIcon />} label="Industry" value={company.industry ?? "unknown"} />
        <StatCard icon={<LocationIcon />} label="Location" value={location} />
        <StatCard icon={<SizeIcon />} label="Size" value={size} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        {company.summary && (
          <>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Company summary
            </p>
            <p className="mb-5 text-sm leading-relaxed text-slate-700">
              {company.summary}
            </p>
          </>
        )}

        <dl className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Fact
            label="Employees"
            value={
              company.size_employees === null
                ? "not disclosed"
                : String(company.size_employees)
            }
          />
          <Fact label="Revenue" value={money(company.revenue_estimate_usd_m)} />
          <Fact label="EBITDA" value={money(company.ebitda_estimate_usd_m)} />
          <Fact label="Ownership" value={company.ownership_status ?? "unknown"} />
          <Fact label="Sub-industry" value={company.sub_industry ?? "—"} />
        </dl>

        {company.investors.length > 0 && (
          <div className="mb-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Investors &amp; backers
            </p>
            <div className="flex flex-wrap gap-1.5">
              {company.investors.map((inv) => (
                <Badge key={inv} tone="slate">
                  {inv}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {company.competitors.length > 0 && (
          <div className="mb-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Top competitors
            </p>
            <div className="flex flex-wrap gap-1.5">
              {company.competitors.map((c) => (
                <Badge key={c} tone="amber">
                  {c}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {company.business_model && (
          <div className="mb-5">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Business model
            </p>
            <p className="text-sm text-slate-700">{company.business_model}</p>
          </div>
        )}

        {company.products.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Products &amp; services
            </p>
            <div className="flex flex-wrap gap-1.5">
              {company.products.map((p) => (
                <Badge key={p} tone="blue">
                  {p}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>

      <details className="group rounded-xl border border-slate-200 bg-white p-4">
        <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-ink">
          Cited sources ({company.sources.length})
          <span className="text-slate-400 transition group-open:rotate-180">⌄</span>
        </summary>
        <div className="mt-4">
          <SourceList sources={company.sources} />
        </div>
      </details>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="text-sm text-ink">{value}</dd>
    </div>
  );
}
