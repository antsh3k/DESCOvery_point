"use client";

import { PILLARS } from "@/lib/pillars";
import type { Weights } from "@/lib/score";

export function WeightControls({
  weights,
  onChange,
  onSave,
  saving,
}: {
  weights: Weights;
  onChange: (w: Weights) => void;
  onSave?: () => void;
  saving?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Scoring weights</h2>
        {onSave && (
          <button
            onClick={onSave}
            disabled={saving}
            className="text-xs text-accent hover:underline disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save as default"}
          </button>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {PILLARS.map(({ key, label, description }) => (
          <label key={key} className="text-sm">
            <div className="mb-1 flex justify-between text-slate-500">
              <span>{label}</span>
              <span>{Math.round(weights[key] * 100)}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={weights[key]}
              onChange={(e) =>
                onChange({ ...weights, [key]: Number(e.target.value) })
              }
              className="w-full accent-accent"
            />
            <p className="mt-1 text-xs leading-snug text-slate-400">
              {description}
            </p>
          </label>
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Weights renormalise over the dimensions a fund actually has — a company
        with no disclosed financials is never penalised for the gap.
      </p>
    </div>
  );
}
