"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/Badge";
import { api } from "@/lib/api";
import type { Fund, FundInput } from "@/lib/types";

function range(min: number | null, max: number | null): string {
  if (min === null && max === null) return "—";
  return `$${min ?? "?"}–${max ?? "?"}m`;
}

export default function FundsPage() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"url" | "manual">("url");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listFunds()
      .then(setFunds)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function prepend(fund: Fund) {
    setFunds((prev) => [fund, ...prev.filter((f) => f.id !== fund.id)]);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Fund universe</h1>
        <p className="text-slate-600">
          The seed dataset plus any funds you add. Spotted one that&apos;s
          missing? Add it by URL and we&apos;ll extract its mandate.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex gap-2 text-sm">
          {(["url", "manual"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1 ${
                mode === m
                  ? "bg-accent text-white"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {m === "url" ? "Add by URL" : "Add manually"}
            </button>
          ))}
        </div>
        {mode === "url" ? (
          <AddByUrl busy={busy} setBusy={setBusy} setError={setError} onAdd={prepend} />
        ) : (
          <AddManual busy={busy} setBusy={setBusy} setError={setError} onAdd={prepend} />
        )}
        {error && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>

      {loading ? (
        <p className="text-slate-500">Loading funds…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2">Fund</th>
                <th className="px-4 py-2">Sectors</th>
                <th className="px-4 py-2">Geo</th>
                <th className="px-4 py-2">EBITDA</th>
                <th className="px-4 py-2">Mandate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {funds.map((f) => (
                <tr key={f.id}>
                  <td className="px-4 py-2">
                    <div className="font-medium">{f.name}</div>
                    {f.source_url && (
                      <a
                        href={f.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-accent hover:underline"
                      >
                        source →
                      </a>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {f.sectors.slice(0, 3).join(", ")}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {f.geographies.join(", ")}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {range(f.ebitda_min_usd_m, f.ebitda_max_usd_m)}
                  </td>
                  <td className="px-4 py-2">
                    <Badge
                      tone={
                        f.mandate_source === "pending"
                          ? "slate"
                          : f.mandate_source === "ai_inferred"
                            ? "amber"
                            : "green"
                      }
                    >
                      {f.mandate_source}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface AddProps {
  busy: boolean;
  setBusy: (b: boolean) => void;
  setError: (e: string | null) => void;
  onAdd: (f: Fund) => void;
}

function AddByUrl({ busy, setBusy, setError, onAdd }: AddProps) {
  const [url, setUrl] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onAdd(await api.createFundFromURL(url.trim()));
      setUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex gap-2">
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://fund.com"
        disabled={busy}
        className="flex-1 rounded-lg border border-slate-300 px-3 py-2 focus:border-accent focus:outline-none"
      />
      <button
        disabled={busy}
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {busy ? "Extracting…" : "Extract & add"}
      </button>
    </form>
  );
}

function AddManual({ busy, setBusy, setError, onAdd }: AddProps) {
  const [form, setForm] = useState({
    name: "",
    firm: "",
    source_url: "",
    sectors: "",
    geographies: "",
    ebitda_min_usd_m: "",
    ebitda_max_usd_m: "",
    thesis: "",
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const toNum = (s: string) => (s.trim() === "" ? null : Number(s));
  const toList = (s: string) =>
    s.split(",").map((x) => x.trim()).filter(Boolean);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Name is required");
      return;
    }
    setBusy(true);
    setError(null);
    const payload: FundInput = {
      name: form.name.trim(),
      firm: form.firm.trim() || null,
      source_url: form.source_url.trim() || null,
      website_url: form.source_url.trim() || null,
      sectors: toList(form.sectors),
      geographies: toList(form.geographies),
      ebitda_min_usd_m: toNum(form.ebitda_min_usd_m),
      ebitda_max_usd_m: toNum(form.ebitda_max_usd_m),
      thesis: form.thesis.trim() || null,
    };
    try {
      onAdd(await api.createFund(payload));
      setForm({
        name: "",
        firm: "",
        source_url: "",
        sectors: "",
        geographies: "",
        ebitda_min_usd_m: "",
        ebitda_max_usd_m: "",
        thesis: "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-accent focus:outline-none";

  return (
    <form onSubmit={submit} className="grid gap-2 sm:grid-cols-2">
      <input className={input} placeholder="Name *" value={form.name} onChange={set("name")} />
      <input className={input} placeholder="Firm" value={form.firm} onChange={set("firm")} />
      <input className={input} placeholder="Sectors (comma-separated)" value={form.sectors} onChange={set("sectors")} />
      <input className={input} placeholder="Geographies (comma-separated)" value={form.geographies} onChange={set("geographies")} />
      <input className={input} placeholder="EBITDA min ($m)" value={form.ebitda_min_usd_m} onChange={set("ebitda_min_usd_m")} />
      <input className={input} placeholder="EBITDA max ($m)" value={form.ebitda_max_usd_m} onChange={set("ebitda_max_usd_m")} />
      <input className={`${input} sm:col-span-2`} placeholder="Source URL" value={form.source_url} onChange={set("source_url")} />
      <textarea className={`${input} sm:col-span-2`} placeholder="Thesis" value={form.thesis} onChange={set("thesis")} rows={2} />
      <button
        disabled={busy}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 sm:col-span-2"
      >
        {busy ? "Adding…" : "Add fund"}
      </button>
    </form>
  );
}
