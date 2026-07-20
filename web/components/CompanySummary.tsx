import type { Company, CompanySource } from "@/lib/types";

import { Badge } from "./Badge";
import { SourceCite } from "./SourceCite";
import { money, statusTone, timeAgo } from "@/lib/format";

function StatCard({
  icon,
  label,
  value,
  sources,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sources?: CompanySource[];
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <span className="text-slate-400">{icon}</span>
        {label}
        {sources && <SourceCite sources={sources} />}
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
function RefreshIcon({ spinning }: { spinning?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={spinning ? "h-4 w-4 animate-spin" : "h-4 w-4"}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5" />
    </svg>
  );
}

export function CompanySummary({
  company,
  enriching,
  onRefresh,
  refreshing,
}: {
  company: Company;
  enriching?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const location =
    [company.location_region, company.location_country]
      .filter(Boolean)
      .join(", ") || "—";

  // Prefer revenue as the headline size; fall back to employees, then unknown.
  const size =
    company.revenue_estimate_usd_m !== null
      ? `${money(company.revenue_estimate_usd_m)} revenue`
      : company.size_employees !== null
        ? `${company.size_employees} employees`
        : "—";

  // A handful of fields can be backfilled by web-search enrichment (see
  // merge_enrichment on the backend, which namespaces those confidences as
  // "enriched.<field>"); everything else always comes from the scraped site.
  const siteSources = company.sources.filter((s) => s.fetch_method !== "search");
  const searchSources = company.sources.filter((s) => s.fetch_method === "search");
  const enrichedFields = new Set(
    Object.keys(company.extraction_confidence ?? {})
      .filter((k) => k.startsWith("enriched."))
      .map((k) => k.slice("enriched.".length)),
  );
  // Only cite a source when the field actually has a value — an empty/"—"
  // fact wasn't established by anything, so there's nothing to point to.
  const sourcesFor = (field: string, hasValue: boolean): CompanySource[] | undefined =>
    hasValue ? (enrichedFields.has(field) ? searchSources : siteSources) : undefined;

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
          <p className="mt-1 text-xs text-slate-400">
            Updated {timeAgo(company.updated_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {enriching && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
              Enriching…
            </span>
          )}
          <Badge tone={statusTone(company.status)}>{company.status}</Badge>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              title={refreshing ? "Refreshing…" : "Refresh data"}
              aria-label={refreshing ? "Refreshing…" : "Refresh data"}
              className="rounded-lg border border-slate-300 bg-white p-2 text-ink hover:border-accent hover:text-accent disabled:opacity-50"
            >
              <RefreshIcon spinning={refreshing} />
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          icon={<IndustryIcon />}
          label="Industry"
          value={company.industry ?? "—"}
          sources={sourcesFor("industry", company.industry !== null)}
        />
        <StatCard
          icon={<LocationIcon />}
          label="Location"
          value={location}
          sources={sourcesFor(
            "location_country",
            company.location_region !== null || company.location_country !== null,
          )}
        />
        <StatCard
          icon={<SizeIcon />}
          label="Size"
          value={size}
          sources={sourcesFor(
            company.revenue_estimate_usd_m !== null ? "revenue_estimate_usd_m" : "size_employees",
            company.revenue_estimate_usd_m !== null || company.size_employees !== null,
          )}
        />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        {company.summary && (
          <>
            <div className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Company summary
              <SourceCite sources={siteSources} />
            </div>
            <p className="mb-5 text-sm leading-relaxed text-slate-700">
              {company.summary}
            </p>
          </>
        )}

        <dl className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Fact
            label="Employees"
            value={
              company.size_employees === null ? "—" : String(company.size_employees)
            }
            sources={sourcesFor("size_employees", company.size_employees !== null)}
          />
          <Fact
            label="Revenue"
            value={money(company.revenue_estimate_usd_m)}
            sources={sourcesFor(
              "revenue_estimate_usd_m",
              company.revenue_estimate_usd_m !== null,
            )}
          />
          <Fact
            label="EBITDA"
            value={
              company.ebitda_estimate_usd_m !== null && company.revenue_estimate_usd_m
                ? `${money(company.ebitda_estimate_usd_m)} (${Math.round(
                    (company.ebitda_estimate_usd_m / company.revenue_estimate_usd_m) * 100,
                  )}% margin)`
                : money(company.ebitda_estimate_usd_m)
            }
            sources={company.ebitda_estimate_usd_m !== null ? siteSources : undefined}
          />
          <Fact
            label="Ownership"
            value={company.ownership_status ?? "—"}
            sources={sourcesFor("ownership_status", company.ownership_status !== null)}
          />
          <Fact
            label="Sub-industry"
            value={company.sub_industry ?? "—"}
            sources={company.sub_industry !== null ? siteSources : undefined}
          />
          <Fact
            label="Growth"
            value={company.growth_trajectory ?? "—"}
            sources={sourcesFor("growth_trajectory", company.growth_trajectory !== null)}
          />
          <Fact
            label="Deal stage"
            value={company.deal_stage ?? "—"}
            sources={sourcesFor("deal_stage", company.deal_stage !== null)}
          />
        </dl>

        {company.investors.length > 0 && (
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Investors &amp; backers
              <SourceCite sources={sourcesFor("investors", true)} />
            </div>
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
            <div className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Top competitors
              <SourceCite sources={sourcesFor("competitors", true)} />
            </div>
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
            <div className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Business model
              <SourceCite sources={siteSources} />
            </div>
            <p className="text-sm text-slate-700">{company.business_model}</p>
          </div>
        )}

        {company.products.length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Products &amp; services
              <SourceCite sources={siteSources} />
            </div>
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
    </section>
  );
}

function Fact({
  label,
  value,
  sources,
}: {
  label: string;
  value: string;
  sources?: CompanySource[];
}) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-xs uppercase tracking-wide text-slate-400">
        {label}
        {sources && <SourceCite sources={sources} />}
      </dt>
      <dd className="text-sm text-ink">{value}</dd>
    </div>
  );
}
