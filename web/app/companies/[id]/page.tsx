"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ActivityFeed } from "@/components/ActivityFeed";
import { CompanySummary } from "@/components/CompanySummary";
import { MatchCard } from "@/components/MatchCard";
import { WeightControls } from "@/components/WeightControls";
import { api } from "@/lib/api";
import { compose, type Weights } from "@/lib/score";
import type { Company, Fund, Match } from "@/lib/types";

const DEFAULT_WEIGHTS: Weights = {
  mandate: 0.4,
  strategy: 0.35,
  value_creation: 0.25,
};

export default function CompanyPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [company, setCompany] = useState<Company | null>(null);
  const [funds, setFunds] = useState<Record<string, Fund>>({});
  const [matches, setMatches] = useState<Match[]>([]);
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [loading, setLoading] = useState(true);
  const [matching, setMatching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [c, fundList, existing, settings] = await Promise.all([
          api.getCompany(id),
          api.listFunds(),
          api.getMatches(id),
          api.getSettings(),
        ]);
        if (!active) return;
        setCompany(c);
        setFunds(Object.fromEntries(fundList.map((f) => [f.id, f])));
        setMatches(existing);
        setWeights({
          mandate: settings.weight_mandate,
          strategy: settings.weight_strategy,
          value_creation: settings.weight_value_creation,
        });
      } catch (err) {
        if (active)
          setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [id]);

  // The whole pipeline runs in the background; poll while it's working.
  const failed = company?.status === "failed";
  const extracting =
    company?.status === "pending" || company?.status === "scraped";
  const enriching =
    company?.enrichment_status === "pending" ||
    company?.enrichment_status === "running";
  const active = !failed && (extracting || enriching);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(async () => {
      try {
        setCompany(await api.getCompany(id));
      } catch {
        /* transient — keep the last good state and retry next tick */
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [active, id]);

  async function runMatch() {
    setMatching(true);
    setError(null);
    try {
      setMatches(await api.matchCompany(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Matching failed");
    } finally {
      setMatching(false);
    }
  }

  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      setCompany(await api.refreshCompany(id));
      setMatches([]); // stale matches are cleared server-side on refresh
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function saveWeights() {
    setSaving(true);
    try {
      await api.updateSettings({
        weight_mandate: weights.mandate,
        weight_strategy: weights.strategy,
        weight_value_creation: weights.value_creation,
      });
    } finally {
      setSaving(false);
    }
  }

  // Re-rank live: recompute composite from stored sub-scores + current weights.
  const ranked = useMemo(() => {
    return matches
      .map((m) => ({
        match: m,
        composite: compose(
          {
            mandate: m.mandate_score,
            strategy: m.strategy_score,
            value_creation: m.value_creation_score,
          },
          weights,
        ).composite,
      }))
      .sort((a, b) => (b.composite ?? -1) - (a.composite ?? -1));
  }, [matches, weights]);

  if (loading) return <p className="text-slate-500">Loading…</p>;
  if (error && !company)
    return <p className="text-red-700">{error}</p>;
  if (!company) return null;

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-accent"
      >
        ← Back to analyze
      </Link>

      {failed ? (
        <section className="rounded-xl border border-red-200 bg-red-50 p-6">
          <h1 className="text-lg font-semibold text-red-800">
            Couldn’t analyze {company.url}
          </h1>
          <p className="mt-1 text-sm text-red-700">
            The site couldn’t be fetched or read. Check the URL and try again.
          </p>
          <div className="mt-4">
            <ActivityFeed progress={company.progress} active={false} failed />
          </div>
        </section>
      ) : extracting ? (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="mb-4 flex items-center gap-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
            <h1 className="text-lg font-semibold text-ink">
              Analyzing {company.name ?? company.url}
            </h1>
          </div>
          <ActivityFeed progress={company.progress} active />
        </section>
      ) : (
        <CompanySummary
          company={company}
          enriching={enriching}
          onRefresh={refresh}
          refreshing={refreshing}
        />
      )}

      {enriching && !extracting && (
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Gathering supplemental firmographics
          </p>
          <ActivityFeed progress={company.progress} active />
        </section>
      )}

      {!extracting && !failed && (
        <>
          <WeightControls
            weights={weights}
            onChange={setWeights}
            onSave={saveWeights}
            saving={saving}
          />

          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              Fund shortlist{" "}
              {ranked.length > 0 && (
                <span className="text-slate-400">({ranked.length})</span>
              )}
            </h2>
            <button
              onClick={runMatch}
              disabled={matching}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {matching
                ? "Matching…"
                : ranked.length > 0
                  ? "Re-run matching"
                  : "Run matching"}
            </button>
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          {ranked.length === 0 ? (
            <p className="text-slate-500">
              No matches yet. Run matching to score this company against the
              fund universe.
            </p>
          ) : (
            <div className="space-y-4">
              {ranked.map(({ match, composite }, i) => {
                const fund = funds[match.fund_id];
                if (!fund) return null;
                return (
                  <MatchCard
                    key={match.id}
                    fund={fund}
                    match={match}
                    composite={composite}
                    rank={i + 1}
                  />
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
