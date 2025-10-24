import type { 
  Advertiser, 
  Campaign, 
  Insertion, 
  Creator, 
  CreatorStats, 
  PlanResponse,
  PerformanceUploadResponse,
  ConversionsUploadResponse,
  SyncResult,
  VectorUploadResult,
  HistoricalDataResponse,
  CampaignForecastResponse
} from './types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Advertisers
  async getAdvertisers(): Promise<Advertiser[]> {
    return this.request<Advertiser[]>('/api/advertisers');
  }

  async createAdvertiser(data: { name: string; category?: string }): Promise<Advertiser> {
    return this.request<Advertiser>('/api/advertisers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Campaigns
  async getCampaigns(advertiserId?: number): Promise<Campaign[]> {
    const params = advertiserId ? `?advertiser_id=${advertiserId}` : '';
    return this.request<Campaign[]>(`/api/campaigns${params}`);
  }

  async createCampaign(data: {
    advertiser_id: number;
    name: string;
    start_date: string;
    end_date: string;
    notes?: string;
  }): Promise<Campaign> {
    return this.request<Campaign>('/api/campaigns', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Insertions
  async getInsertions(campaignId?: number): Promise<Insertion[]> {
    const params = campaignId ? `?campaign_id=${campaignId}` : '';
    return this.request<Insertion[]>(`/api/insertions${params}`);
  }

  async createInsertion(data: {
    campaign_id: number;
    month_start: string;
    month_end: string;
    cpc: number;
  }): Promise<Insertion> {
    return this.request<Insertion>('/api/insertions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Creators
  async getCreators(): Promise<Creator[]> {
    return this.request<Creator[]>('/api/creators');
  }

  // Seed creators
  async seedCreators(file: File, syncMode: 'upsert' | 'full_sync' = 'upsert'): Promise<SyncResult> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('sync_mode', syncMode);
    
    return this.request<SyncResult>('/api/seed/creators', {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  // Uploads
  async uploadPerformance(insertionId: number, file: File): Promise<PerformanceUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    return this.request<PerformanceUploadResponse>(`/api/uploads/performance?insertion_id=${insertionId}`, {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  async uploadVectors(file: File): Promise<VectorUploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    return this.request<VectorUploadResult>('/api/vectors', {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  async uploadConversions(
    advertiserId: number,
    campaignId: number,
    insertionId: number,
    rangeStart: string,
    rangeEnd: string,
    file: File
  ): Promise<ConversionsUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    const params = new URLSearchParams({
      advertiser_id: advertiserId.toString(),
      campaign_id: campaignId.toString(),
      insertion_id: insertionId.toString(),
      range_start: rangeStart,
      range_end: rangeEnd,
    });
    
    return this.request<ConversionsUploadResponse>(`/api/uploads/conversions?${params}`, {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  // Analytics
  async getLeaderboard(advertiser_category?: string, creator_topic?: string, limit = 50, cpc?: number): Promise<CreatorStats[]> {
    const params = new URLSearchParams();
    if (advertiser_category) params.append('advertiser_category', advertiser_category);
    if (creator_topic) params.append('creator_topic', creator_topic);
    params.append('limit', limit.toString());
    if (cpc) params.append('cpc', cpc.toString());
    
    return this.request<CreatorStats[]>(`/api/leaderboard?${params}`);
  }

  async getFilterOptions(): Promise<{ advertiser_categories: string[]; creator_topics: string[] }> {
    return this.request<{ advertiser_categories: string[]; creator_topics: string[] }>('/api/filter-options');
  }

  async createPlan(data: {
    category?: string;
    advertiser_id?: number;
    insertion_id?: number;
    cpc?: number;
    budget: number;
    target_cpa?: number;
    horizon_days: number;
    advertiser_avg_cvr?: number;
    include_acct_ids?: string;
    exclude_acct_ids?: string;
    email?: string;
  }): Promise<PlanResponse> {
    return this.request<PlanResponse>('/api/plan', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async createSmartPlan(data: {
    category?: string;
    advertiser_id?: number;
    insertion_id?: number;
    cpc?: number;
    budget: number;
    target_cpa?: number;
    horizon_days: number;
    advertiser_avg_cvr?: number;
    target_age_range?: string;
    target_gender_skew?: string;
    target_location?: string;
    target_interests?: string;
    use_smart_matching?: boolean;
    include_acct_ids?: string;
    exclude_acct_ids?: string;
    email?: string;
  }): Promise<PlanResponse> {
    return this.request<PlanResponse>('/api/plan-smart', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getHistoricalData(advertiser_id?: number, insertion_id?: number): Promise<HistoricalDataResponse> {
    const params = new URLSearchParams();
    if (advertiser_id) params.append('advertiser_id', advertiser_id.toString());
    if (insertion_id) params.append('insertion_id', insertion_id.toString());
    
    return this.request<HistoricalDataResponse>(`/api/historical-data?${params}`);
  }

  async downloadHistoricalDataCSV(advertiser_id?: number, insertion_id?: number): Promise<void> {
    const params = new URLSearchParams();
    if (advertiser_id) params.append('advertiser_id', advertiser_id.toString());
    if (insertion_id) params.append('insertion_id', insertion_id.toString());
    
    const url = `${this.baseUrl}/api/historical-data-csv?${params}`;
    
    // Create a temporary link and trigger download
    const link = document.createElement('a');
    link.href = url;
    link.download = `historical_data_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async getCampaignForecast(campaign_id: number): Promise<CampaignForecastResponse> {
    return this.request<CampaignForecastResponse>(`/api/campaign-forecast?campaign_id=${campaign_id}`);
  }
}

export const api = new ApiClient(API_URL);
