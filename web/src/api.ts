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
  async getAdvertisers() {
    return this.request('/api/advertisers');
  }

  async createAdvertiser(data: { name: string; category?: string }) {
    return this.request('/api/advertisers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Campaigns
  async getCampaigns(advertiserId?: number) {
    const params = advertiserId ? `?advertiser_id=${advertiserId}` : '';
    return this.request(`/api/campaigns${params}`);
  }

  async createCampaign(data: {
    advertiser_id: number;
    name: string;
    start_date: string;
    end_date: string;
    notes?: string;
  }) {
    return this.request('/api/campaigns', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Insertions
  async getInsertions(campaignId?: number) {
    const params = campaignId ? `?campaign_id=${campaignId}` : '';
    return this.request(`/api/insertions${params}`);
  }

  async createInsertion(data: {
    campaign_id: number;
    month_start: string;
    month_end: string;
    cpc: number;
  }) {
    return this.request('/api/insertions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Creators
  async getCreators() {
    return this.request('/api/creators');
  }

  // Seed creators
  async seedCreators(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    
    return this.request('/api/seed/creators', {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  // Uploads
  async uploadPerformance(insertionId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    
    return this.request(`/api/uploads/performance?insertion_id=${insertionId}`, {
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
  ) {
    const formData = new FormData();
    formData.append('file', file);
    
    const params = new URLSearchParams({
      advertiser_id: advertiserId.toString(),
      campaign_id: campaignId.toString(),
      insertion_id: insertionId.toString(),
      range_start: rangeStart,
      range_end: rangeEnd,
    });
    
    return this.request(`/api/uploads/conversions?${params}`, {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  // Analytics
  async getLeaderboard(category?: string, limit = 50, cpc?: number) {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    params.append('limit', limit.toString());
    if (cpc) params.append('cpc', cpc.toString());
    
    return this.request(`/api/leaderboard?${params}`);
  }

  async createPlan(data: {
    category?: string;
    advertiser_id?: number;
    insertion_id?: number;
    cpc?: number;
    budget: number;
    target_cpa: number;
    horizon_days: number;
  }) {
    return this.request('/api/plan', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient(API_URL);
