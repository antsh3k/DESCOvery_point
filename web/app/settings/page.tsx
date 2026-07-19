"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Settings } from "@/lib/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch((e) => setError(e.message));
  }, []);

  function set<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((s) => (s ? { ...s, [key]: value } : s));
    setSaved(false);
  }

  async function save() {
    if (!settings) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateSettings({
        weight_thesis: settings.weight_thesis,
        weight_numeric: settings.weight_numeric,
        weight_strategy: settings.weight_strategy,
        llm_provider: settings.llm_provider,
        llm_model: settings.llm_model,
        scrape_max_pages: settings.scrape_max_pages,
      });
      setSettings(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (error && !settings) return <p className="text-red-700">{error}</p>;
  if (!settings) return <p className="text-slate-500">Loading…</p>;

  const input =
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-accent focus:outline-none";
  const label = "block text-xs uppercase tracking-wide text-slate-400 mb-1";

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold">Scoring weights</h2>
        <div className="grid grid-cols-3 gap-3">
          {(["weight_thesis", "weight_numeric", "weight_strategy"] as const).map(
            (key) => (
              <div key={key}>
                <label className={label}>{key.replace("weight_", "")}</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={settings[key]}
                  onChange={(e) => set(key, Number(e.target.value))}
                  className={input}
                />
              </div>
            ),
          )}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          These are the saved defaults. Weights are relative and renormalise over
          the dimensions a fund actually has — they need not sum to 1, and a
          company with no disclosed financials is never penalised for the gap. Use
          the sliders on a company page to explore weightings live.
        </p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
        <h2 className="text-sm font-semibold">LLM & scraping</h2>
        <div>
          <label className={label}>Provider</label>
          <select
            value={settings.llm_provider}
            onChange={(e) => set("llm_provider", e.target.value)}
            className={input}
          >
            <option value="anthropic">anthropic</option>
            <option value="openai">openai</option>
          </select>
        </div>
        <div>
          <label className={label}>Model override</label>
          <input
            value={settings.llm_model ?? ""}
            onChange={(e) => set("llm_model", e.target.value || null)}
            placeholder="(uses .env default)"
            className={input}
          />
        </div>
        <div>
          <label className={label}>Scrape max pages</label>
          <input
            type="number"
            min={1}
            max={50}
            value={settings.scrape_max_pages}
            onChange={(e) => set("scrape_max_pages", Number(e.target.value))}
            className={input}
          />
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-accent px-5 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {saved && <span className="text-sm text-green-700">Saved ✓</span>}
        {error && <span className="text-sm text-red-700">{error}</span>}
      </div>
    </div>
  );
}
