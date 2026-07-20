// Small presentation helpers shared across the UI.

/** A USD-millions range like `$5–30m`, or null when neither bound is known. */
export function moneyRange(
  min: number | null,
  max: number | null,
): string | null {
  if (min === null && max === null) return null;
  if (min !== null && max !== null) return `$${min}–${max}m`;
  if (min !== null) return `$${min}m+`;
  return `up to $${max}m`;
}

/** A single USD-millions figure, or the given fallback when missing. */
export function money(v: number | null, fallback = "not disclosed"): string {
  return v === null ? fallback : `$${v}m`;
}

/** Badge tone for a company analysis status. */
export function statusTone(status: string): string {
  if (status === "extracted") return "green";
  if (status === "failed") return "red";
  return "amber";
}

/** Relative "last updated" label, e.g. "2h ago", falling back to a date. */
export function timeAgo(iso: string): string {
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
