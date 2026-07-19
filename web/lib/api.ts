// Typed client for the thesis_match FastAPI backend.

import type {
  Company,
  CompanyListItem,
  Fund,
  FundInput,
  Match,
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

export const api = {
  createCompany: (url: string) =>
    request<Company>("/companies", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  listCompanies: (limit = 12) =>
    request<CompanyListItem[]>(`/companies?limit=${limit}`),
  getCompany: (id: string) => request<Company>(`/companies/${id}`),
  matchCompany: (id: string) =>
    request<Match[]>(`/companies/${id}/match`, { method: "POST" }),
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
