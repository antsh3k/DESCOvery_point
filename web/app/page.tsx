"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { RecentAnalyses } from "@/components/RecentAnalyses";
import { api } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const company = await api.createCompany(url.trim());
      router.push(`/companies/${company.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="pt-12 text-center sm:pt-24">
        <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm font-medium text-slate-600">
          <span className="text-accent">◆</span>
          AI PE buyer discovery for SMBs
        </span>

        <h1 className="mx-auto mt-8 max-w-3xl text-balance text-5xl font-bold tracking-tight text-ink sm:text-6xl lg:text-7xl">
          Turn a company URL into a PE buyer shortlist.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-xl text-slate-600 sm:text-2xl">
          We analyze the site, extract firmographics with cited sources, and rank
          private-equity funds by mandate fit.
        </p>

        <form
          onSubmit={analyze}
          className="mx-auto mt-10 flex max-w-2xl flex-col gap-3 sm:flex-row"
        >
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="acme-industries.com"
            className="flex-1 rounded-xl border border-slate-300 bg-white px-5 py-4 text-base shadow-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-ink px-8 py-4 text-base font-medium text-white transition hover:bg-slate-700 disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Analyze →"}
          </button>
        </form>

        {loading && (
          <p className="mt-5 text-base text-slate-500">
            Scraping and extracting — this can take a few seconds.
          </p>
        )}
        {error && (
          <p className="mx-auto mt-5 max-w-2xl rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>

      <RecentAnalyses />
    </div>
  );
}
