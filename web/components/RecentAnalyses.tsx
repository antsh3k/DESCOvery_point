"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/Badge";
import { api } from "@/lib/api";
import { statusTone } from "@/lib/format";
import type { CompanyListItem } from "@/lib/types";

export function RecentAnalyses() {
  const [items, setItems] = useState<CompanyListItem[] | null>(null);

  useEffect(() => {
    api
      .listCompanies()
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  if (items === null || items.length === 0) return null;

  return (
    <section className="mt-16">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Recent analyses
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((c) => (
          <Link
            key={c.id}
            href={`/companies/${c.id}`}
            className="group rounded-xl border border-slate-200 bg-white p-4 transition hover:border-accent hover:shadow-sm"
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-ink group-hover:text-accent">
                {c.name ?? c.url}
              </h3>
              <Badge tone={statusTone(c.status)}>{c.status}</Badge>
            </div>
            <p className="mt-0.5 truncate text-xs text-slate-500">{c.url}</p>
            {c.industry && (
              <p className="mt-3 text-sm text-slate-600">{c.industry}</p>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
