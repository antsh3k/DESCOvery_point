// TypeScript mirrors of the FastAPI response schemas.

export interface CompanySource {
  id: string;
  source_url: string;
  page_title: string | null;
  fetch_method: string;
  snippet: string | null;
}

export interface ProgressEvent {
  label: string;
  detail: string | null;
  at: string;
}

export interface Company {
  id: string;
  url: string;
  name: string | null;
  industry: string | null;
  sub_industry: string | null;
  location_country: string | null;
  location_region: string | null;
  size_employees: number | null;
  revenue_estimate_usd_m: number | null;
  ebitda_estimate_usd_m: number | null;
  products: string[];
  summary: string | null;
  business_model: string | null;
  ownership_status: string | null;
  investors: string[];
  competitors: string[];
  growth_trajectory: string | null;
  deal_stage: string | null;
  extraction_confidence: Record<string, number> | null;
  status: string;
  enrichment_status: string;
  progress: ProgressEvent[];
  sources: CompanySource[];
  created_at: string;
  updated_at: string;
}

export interface CompanyListItem {
  id: string;
  url: string;
  name: string | null;
  industry: string | null;
  location_country: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Fund {
  id: string;
  name: string;
  firm: string | null;
  website_url: string | null;
  source_url: string | null;
  sectors: string[];
  geographies: string[];
  check_size_min_usd_m: number | null;
  check_size_max_usd_m: number | null;
  ebitda_min_usd_m: number | null;
  ebitda_max_usd_m: number | null;
  revenue_min_usd_m: number | null;
  revenue_max_usd_m: number | null;
  stage: string | null;
  thesis: string | null;
  provenance: string;
  mandate_source: string;
  mandate_confidence: number | null;
  // Regulatory metadata (Form ADV / Form D) — straight from the filing, not
  // LLM-inferred; null for seed/manual/url_extracted funds.
  fund_type_raw: string | null;
  gross_asset_value_usd: number | null;
  amount_raised_usd: number | null;
  investor_count: number | null;
  filing_date: string | null;
  auditor_name: string | null;
  prime_broker_name: string | null;
  custodian_name: string | null;
  regulatory_id: string | null;
}

export interface MatchProgress {
  done: number;
  total: number;
}

export interface Match {
  id: string;
  company_id: string;
  fund_id: string;
  run_id: string;
  passed_hard_filters: boolean;
  mandate_score: number | null;
  strategy_score: number | null;
  value_creation_score: number | null;
  composite_score: number | null;
  matched_on: Record<string, unknown> | null;
  rationale: string | null;
  rank: number | null;
  weights_used: Record<string, number> | null;
}

export interface Settings {
  id: string;
  weight_mandate: number;
  weight_strategy: number;
  weight_value_creation: number;
  llm_provider: string;
  llm_model: string | null;
  scrape_max_pages: number;
}

export interface FundInput {
  name: string;
  firm?: string | null;
  website_url?: string | null;
  source_url?: string | null;
  sectors: string[];
  geographies: string[];
  check_size_min_usd_m?: number | null;
  check_size_max_usd_m?: number | null;
  ebitda_min_usd_m?: number | null;
  ebitda_max_usd_m?: number | null;
  revenue_min_usd_m?: number | null;
  revenue_max_usd_m?: number | null;
  stage?: string | null;
  thesis?: string | null;
}
