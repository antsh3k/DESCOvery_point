// Typed client for the DESCOvery_point FastAPI backend.

import type {
  Company,
  CompanyListItem,
  Fund,
  FundInput,
  Match,
  MatchProgress,
  Settings,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

// The match endpoint streams newline-delimited JSON progress events instead
// of blocking silently for the ~1-2 minutes a large fund universe can take.
// One JSON object per line: {"type":"start"}, {"type":"progress",done,total},
// then a final {"type":"done",matches} or {"type":"error",detail}.
async function streamMatch(
  id: string,
  onProgress?: (progress: MatchProgress) => void,
): Promise<Match[]> {
  const res = await fetch(`${BASE}/companies/${id}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(`${res.status}: ${detail}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (!line) continue;

      const event = JSON.parse(line);
      if (event.type === "progress") {
        onProgress?.({ done: event.done, total: event.total });
      } else if (event.type === "done") {
        return event.matches as Match[];
      } else if (event.type === "error") {
        throw new Error(event.detail ?? "Matching failed");
      }
    }
  }
  throw new Error("Match stream ended unexpectedly");
}

export const api = {
  createCompany: (url: string) =>
    request<Company>("/companies", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  listCompanies: (limit = 12) =>
    request<CompanyListItem[]>(`/companies?limit=${limit}`),
  getCompany: (id: string) => request<Company>(`/companies/${id}`),
  refreshCompany: (id: string) =>
    request<Company>(`/companies/${id}/refresh`, { method: "POST" }),
  matchCompany: (id: string, onProgress?: (progress: MatchProgress) => void) =>
    streamMatch(id, onProgress),
  getMatches: (id: string) => request<Match[]>(`/companies/${id}/matches`),

  listFunds: () => request<Fund[]>("/funds"),
  createFund: (fund: FundInput) =>
    request<Fund>("/funds", { method: "POST", body: JSON.stringify(fund) }),
  createFundFromURL: (url: string) =>
    request<Fund>("/funds/from-url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  getSettings: () => request<Settings>("/settings"),
  updateSettings: (patch: Partial<Settings>) =>
    request<Settings>("/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
};
