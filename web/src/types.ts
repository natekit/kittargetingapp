// API Response Types
export interface Advertiser {
  advertiser_id: number;
  name: string;
  category?: string;
}

export interface Campaign {
  campaign_id: number;
  advertiser_id: number;
  name: string;
  start_date: string;
  end_date: string;
  notes?: string;
}

export interface Insertion {
  insertion_id: number;
  campaign_id: number;
  month_start: string;
  month_end: string;
  cpc: number;
}

export interface Creator {
  creator_id: number;
  owner_email: string;
  acct_id: string;
  name: string;
  topic?: string;
}

export interface CreatorStats {
  creator_id: number;
  name: string;
  acct_id: string;
  clicks: number;
  conversions: number;
  cvr: number;
  expected_cpa?: number;
}

export interface PlanCreator {
  creator_id: number;
  name: string;
  acct_id: string;
  expected_cvr: number;
  expected_cpa: number;
  clicks_per_day: number;
  expected_clicks: number;
  expected_spend: number;
  expected_conversions: number;
  value_ratio: number;
  // Smart matching fields
  matching_rationale?: string;
  tier?: number;
  performance_score?: number;
  demographic_score?: number;
  topic_score?: number;
  similarity_score?: number;
  combined_score?: number;
}

export interface PlanResponse {
  picked_creators: PlanCreator[];
  total_spend: number;
  total_conversions: number;
  blended_cpa: number;
  budget_utilization: number;
}

export interface PerformanceUploadResponse {
  perf_upload_id: number;
  inserted_rows: number;
  unmatched_count: number;
  unmatched_examples: string[];
}

export interface ConversionsUploadResponse {
  conv_upload_id: number;
  replaced_rows: number;
  inserted_rows: number;
}

export interface SyncResult {
  upserted: number;
  skipped: number;
  total_processed: number;
  errors?: string[];
}

export interface HistoricalDataSummary {
  total_creators: number;
  creators_with_clicks: number;
  creators_with_conversions: number;
  total_clicks: number;
  total_conversions: number;
  overall_cvr: number;
}

export interface CreatorHistoricalData {
  creator_id: number;
  name: string;
  acct_id: string;
  topic: string;
  age_range: string;
  gender_skew: string;
  location: string;
  interests: string;
  conservative_click_estimate: number;
  total_clicks: number;
  total_conversions: number;
  cvr: number;
  recent_clicks: Array<{
    execution_date: string;
    clicks: number;
    unique_clicks: number;
    flagged: boolean;
  }>;
  recent_conversions: Array<{
    period: string;
    conversions: number;
  }>;
}

export interface HistoricalDataResponse {
  summary: HistoricalDataSummary;
  creators: CreatorHistoricalData[];
}
