// Client-side composite recompute, mirroring app/services/matching/score.py.
// Lets the dashboard re-weight and re-sort instantly without re-running the LLM.

export interface Weights {
  mandate: number;
  strategy: number;
  value_creation: number;
}

export interface DimensionScores {
  mandate: number | null;
  strategy: number | null;
  value_creation: number | null;
}

export function compose(
  scores: DimensionScores,
  weights: Weights,
): { composite: number | null; effective: Partial<Weights> } {
  const dims: [keyof Weights, number | null][] = [
    ["mandate", scores.mandate],
    ["strategy", scores.strategy],
    ["value_creation", scores.value_creation],
  ];
  const present = dims.filter(
    ([k, v]) => v !== null && weights[k] > 0,
  ) as [keyof Weights, number][];
  const total = present.reduce((s, [k]) => s + weights[k], 0);
  if (present.length === 0 || total === 0) {
    return { composite: null, effective: {} };
  }
  const effective: Partial<Weights> = {};
  let composite = 0;
  for (const [k, v] of present) {
    const w = weights[k] / total;
    effective[k] = Math.round(w * 10000) / 10000;
    composite += v * w;
  }
  return { composite: Math.round(composite * 100) / 100, effective };
}
