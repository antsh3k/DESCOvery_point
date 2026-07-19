"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

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
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-semibold">Analyze a company</h1>
      <p className="mb-6 text-slate-600">
        Enter an SME&apos;s website URL. We&apos;ll extract its profile and
        shortlist the PE funds whose mandate fits best.
      </p>

      <form onSubmit={analyze} className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2 focus:border-accent focus:outline-none"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {loading && (
        <p className="mt-4 text-sm text-slate-500">
          Scraping and extracting — this can take a few seconds.
        </p>
      )}
      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
