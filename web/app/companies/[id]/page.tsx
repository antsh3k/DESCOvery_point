"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { CompanySummary } from "@/components/CompanySummary";
import { MatchCard } from "@/components/MatchCard";
import { WeightControls } from "@/components/WeightControls";
import { api } from "@/lib/api";
import { compose, type Weights } from "@/lib/score";
import type { Company, Fund, Match } from "@/lib/types";

const DEFAULT_WEIGHTS: Weights = { thesis: 0.4, numeric: 0.35, strategy: 0.25 };

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
          thesis: settings.weight_thesis,
          numeric: settings.weight_numeric,
          strategy: settings.weight_strategy,
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

  async function saveWeights() {
    setSaving(true);
    try {
      await api.updateSettings({
        weight_thesis: weights.thesis,
        weight_numeric: weights.numeric,
        weight_strategy: weights.strategy,
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
            thesis: m.thesis_score,
            numeric: m.numeric_score,
            strategy: m.strategy_score,
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
      <CompanySummary company={company} />

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

      {error && company && (
        <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {ranked.length === 0 ? (
        <p className="text-slate-500">
          No matches yet. Run matching to score this company against the fund
          universe.
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
    </div>
  );
}
