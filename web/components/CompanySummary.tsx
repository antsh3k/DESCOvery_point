import type { Company } from "@/lib/types";

import { Badge } from "./Badge";
import { SourceList } from "./SourceList";

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="text-sm text-ink">{value}</dd>
    </div>
  );
}

function money(v: number | null): string {
  return v === null ? "not disclosed" : `$${v}m`;
}

export function CompanySummary({ company }: { company: Company }) {
  const location =
    [company.location_region, company.location_country]
      .filter(Boolean)
      .join(", ") || "unknown";

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {company.name ?? company.url}
          </h1>
          <a
            href={company.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-accent hover:underline"
          >
            {company.url}
          </a>
        </div>
        <Badge tone={company.status === "extracted" ? "green" : "amber"}>
          {company.status}
        </Badge>
      </div>

      {company.summary && (
        <p className="mb-5 text-sm leading-relaxed text-slate-700">
          {company.summary}
        </p>
      )}

      <dl className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Fact label="Industry" value={company.industry ?? "unknown"} />
        <Fact label="Location" value={location} />
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
        <Fact
          label="Business model"
          value={company.business_model ?? "unknown"}
        />
      </dl>

      {company.products.length > 0 && (
        <div className="mb-5">
          <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">
            Products
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

      <div>
        <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">
          Sources
        </p>
        <SourceList sources={company.sources} />
      </div>
    </section>
  );
}
