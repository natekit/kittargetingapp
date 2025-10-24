import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';
import { downloadAsCsv } from '../../lib/csv';
import type { Advertiser, Insertion, PlanResponse } from '../../types';

export function PlannerPage() {
  const [advertisers, setAdvertisers] = useState<Advertiser[]>([]);
  const [insertions, setInsertions] = useState<Insertion[]>([]);
  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    category: '',
    advertiser_id: 0,
    insertion_id: 0,
    cpc: '',
    budget: '',
    target_cpa: '',
    advertiser_avg_cvr: '',
    horizon_days: 30,
    // Smart matching fields
    target_age_range: '',
    target_gender_skew: '',
    target_location: '',
    target_interests: '',
    use_smart_matching: true,
    // Creator filtering fields
    include_acct_ids: '',
    exclude_acct_ids: '',
    // Email export field
    email: '',
  });

  useEffect(() => {
    const fetchAdvertisers = async () => {
      try {
        const data = await api.getAdvertisers();
        setAdvertisers(data);
      } catch (error) {
        console.error('Error fetching advertisers:', error);
      }
    };
    fetchAdvertisers();
  }, []);

  useEffect(() => {
    if (formData.advertiser_id) {
      const fetchInsertions = async () => {
        try {
          const campaigns = await api.getCampaigns(formData.advertiser_id);
          const allInsertions: Insertion[] = [];
          for (const campaign of campaigns) {
            const insertions = await api.getInsertions(campaign.campaign_id);
            allInsertions.push(...insertions);
          }
          setInsertions(allInsertions);
        } catch (error) {
          console.error('Error fetching insertions:', error);
        }
      };
      fetchInsertions();
    }
  }, [formData.advertiser_id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setPlan(null);
    setError(null);

    try {
      const requestData: any = {
        budget: parseFloat(formData.budget),
        horizon_days: formData.horizon_days,
      };
      
      // Add optional fields only if they have values
      if (formData.target_cpa && formData.target_cpa.trim() !== '') {
        requestData.target_cpa = parseFloat(formData.target_cpa);
      }
      
      if (formData.advertiser_avg_cvr && formData.advertiser_avg_cvr.trim() !== '') {
        requestData.advertiser_avg_cvr = parseFloat(formData.advertiser_avg_cvr);
      }

      if (formData.category) {
        requestData.category = formData.category;
      } else if (formData.advertiser_id) {
        requestData.advertiser_id = formData.advertiser_id;
      }

      if (formData.insertion_id) {
        requestData.insertion_id = formData.insertion_id;
      } else if (formData.cpc) {
        requestData.cpc = parseFloat(formData.cpc);
      }

      // Add smart matching fields if using smart matching
      if (formData.use_smart_matching) {
        if (formData.target_age_range) {
          requestData.target_age_range = formData.target_age_range;
        }
        if (formData.target_gender_skew) {
          requestData.target_gender_skew = formData.target_gender_skew;
        }
        if (formData.target_location) {
          requestData.target_location = formData.target_location;
        }
        if (formData.target_interests) {
          requestData.target_interests = formData.target_interests;
        }
        requestData.use_smart_matching = formData.use_smart_matching;
      }

      // Add creator filtering fields
      if (formData.include_acct_ids && formData.include_acct_ids.trim() !== '') {
        requestData.include_acct_ids = formData.include_acct_ids.trim();
      }
      if (formData.exclude_acct_ids && formData.exclude_acct_ids.trim() !== '') {
        requestData.exclude_acct_ids = formData.exclude_acct_ids.trim();
      }
      
      // Add email field
      if (formData.email && formData.email.trim() !== '') {
        requestData.email = formData.email.trim();
      }

      const data = formData.use_smart_matching 
        ? await api.createSmartPlan(requestData)
        : await api.createPlan(requestData);
      
      // Check if plan has no creators
      if (data.picked_creators.length === 0) {
        setError(getNoResultsMessage(requestData));
      } else {
        setPlan(data);
        
        // Auto-download CSV if email was provided
        if (formData.email && formData.email.trim() !== '') {
          console.log('Auto-downloading CSV for email:', formData.email);
          console.log('DEBUG: First creator data:', data.picked_creators[0]);
          const csvData = data.picked_creators.map(creator => ({
            'Creator ID': creator.creator_id,
            'Name': creator.name,
            'Account ID': creator.acct_id,
            'Expected CVR': creator.expected_cvr.toFixed(4),
            'Expected CPA': creator.expected_cpa ? `$${creator.expected_cpa.toFixed(2)}` : 'N/A',
            'Clicks Per Day': creator.clicks_per_day.toFixed(2),
            'Expected Clicks': creator.expected_clicks.toFixed(2),
            'Expected Spend': `$${creator.expected_spend.toFixed(2)}`,
            'Expected Conversions': creator.expected_conversions.toFixed(2),
            'Value Ratio': creator.value_ratio.toFixed(4),
            'Recommended Placements': creator.recommended_placements,
            'Median Clicks Per Placement': creator.median_clicks_per_placement ? creator.median_clicks_per_placement.toFixed(2) : 'N/A'
          }));
          
          console.log('DEBUG: CSV data sample:', csvData[0]);
          
          const headers = [
            'Creator ID', 'Name', 'Account ID', 'Expected CVR', 'Expected CPA', 
            'Clicks Per Day', 'Expected Clicks', 'Expected Spend', 'Expected Conversions',
            'Value Ratio', 'Recommended Placements', 'Median Clicks Per Placement'
          ];
          
          console.log('DEBUG: CSV headers:', headers);
          
          downloadAsCsv('kit_targeting_plan', csvData, headers);
        }
      }
    } catch (error) {
      console.error('Error creating plan:', error);
      setError('Failed to create plan. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getNoResultsMessage = (requestData: any): string => {
    const hasTargetCpa = requestData.target_cpa && requestData.target_cpa > 0;
    const hasAdvertiserCvr = requestData.advertiser_avg_cvr && requestData.advertiser_avg_cvr > 0;
    
    if (hasTargetCpa) {
      return `No creators found that meet your target CPA of $${requestData.target_cpa}. Try:
      • Increasing your target CPA to $${(requestData.target_cpa * 2).toFixed(2)} or higher
      • Removing the target CPA constraint to see all available creators
      • Adding a higher advertiser average CVR to improve creator estimates`;
    }
    
    if (hasAdvertiserCvr) {
      return `No creators found with sufficient performance data. This could be because:
      • Creators don't have enough historical clicks or conversions
      • The advertiser average CVR of ${(requestData.advertiser_avg_cvr * 100).toFixed(1)}% may be too low
      • Try increasing the advertiser average CVR or removing it to use default estimates`;
    }
    
    return `No creators found with sufficient performance data. This could be because:
    • Creators don't have enough historical clicks or conversions
    • No performance data has been uploaded for this advertiser/category
    • Try uploading performance data first, or contact support for assistance`;
  };

  const exportToCsv = () => {
    if (!plan) return;

    const headers = [
      'Creator ID',
      'Name',
      'Account ID',
      'Expected CVR',
      'Expected CPA',
      'Clicks Per Day',
      'Expected Clicks',
      'Expected Spend',
      'Expected Conversions',
      'Value Ratio'
    ];
    
    const csvData = plan.picked_creators.map(creator => [
      creator.creator_id,
      creator.name,
      creator.acct_id,
      creator.expected_cvr.toFixed(4),
      creator.expected_cpa ? creator.expected_cpa.toFixed(2) : 'N/A',
      creator.clicks_per_day.toFixed(2),
      creator.expected_clicks.toFixed(0),
      creator.expected_spend.toFixed(2),
      creator.expected_conversions.toFixed(0),
      creator.value_ratio.toFixed(6)
    ]);

    downloadAsCsv('plan', csvData, headers);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Planner</h1>
        <p className="mt-2 text-gray-600">
          Create budget allocation plans for creators
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Plan Parameters</CardTitle>
          <CardDescription>
            Configure your budget allocation plan
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="category" className="block text-sm font-medium text-gray-700">
                  Category
                </label>
                <Input
                  id="category"
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value, advertiser_id: 0 })}
                  placeholder="e.g., News"
                  className="mt-1"
                />
              </div>

              <div>
                <label htmlFor="advertiser" className="block text-sm font-medium text-gray-700">
                  Or Select Advertiser
                </label>
                <select
                  id="advertiser"
                  value={formData.advertiser_id}
                  onChange={(e) => setFormData({ ...formData, advertiser_id: parseInt(e.target.value), category: '' })}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value={0}>Select advertiser</option>
                  {advertisers.map((advertiser) => (
                    <option key={advertiser.advertiser_id} value={advertiser.advertiser_id}>
                      {advertiser.name} {advertiser.category && `(${advertiser.category})`}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="insertion" className="block text-sm font-medium text-gray-700">
                  Insertion (for CPC)
                </label>
                <select
                  id="insertion"
                  value={formData.insertion_id}
                  onChange={(e) => setFormData({ ...formData, insertion_id: parseInt(e.target.value), cpc: '' })}
                  disabled={!formData.advertiser_id}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
                >
                  <option value={0}>Select insertion</option>
                  {insertions.map((insertion) => (
                    <option key={insertion.insertion_id} value={insertion.insertion_id}>
                      {insertion.month_start} to {insertion.month_end} (CPC: ${insertion.cpc})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="cpc" className="block text-sm font-medium text-gray-700">
                  Or Enter CPC
                </label>
                <Input
                  id="cpc"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.cpc}
                  onChange={(e) => setFormData({ ...formData, cpc: e.target.value, insertion_id: 0 })}
                  placeholder="0.45"
                  className="mt-1"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label htmlFor="budget" className="block text-sm font-medium text-gray-700">
                  Budget *
                </label>
                <Input
                  id="budget"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.budget}
                  onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
                  required
                  className="mt-1"
                  placeholder="25000"
                />
              </div>

              <div>
                <label htmlFor="target_cpa" className="block text-sm font-medium text-gray-700">
                  Target CPA (Optional)
                </label>
                <Input
                  id="target_cpa"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.target_cpa}
                  onChange={(e) => setFormData({ ...formData, target_cpa: e.target.value })}
                  className="mt-1"
                  placeholder="3.25"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Leave blank to prioritize by CVR instead of CPA. 
                  <br />
                  <span className="text-amber-600 font-medium">Tip:</span> If no results appear, try increasing this value or removing it entirely.
                </p>
              </div>

              <div>
                <label htmlFor="advertiser_avg_cvr" className="block text-sm font-medium text-gray-700">
                  Advertiser Average CVR (Optional)
                </label>
                <Input
                  id="advertiser_avg_cvr"
                  type="number"
                  min="0"
                  max="1"
                  step="0.001"
                  value={formData.advertiser_avg_cvr}
                  onChange={(e) => setFormData({ ...formData, advertiser_avg_cvr: e.target.value })}
                  className="mt-1"
                  placeholder="0.025"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Use your advertiser's average CVR for better fallback estimates (e.g., 0.025 = 2.5%)
                  <br />
                  <span className="text-amber-600 font-medium">Tip:</span> Higher values (0.05-0.15) may help more creators qualify for your plan.
                </p>
              </div>

              <div>
                <label htmlFor="horizon_days" className="block text-sm font-medium text-gray-700">
                  Horizon Days
                </label>
                <Input
                  id="horizon_days"
                  type="number"
                  min="1"
                  value={formData.horizon_days}
                  onChange={(e) => setFormData({ ...formData, horizon_days: parseInt(e.target.value) || 30 })}
                  className="mt-1"
                />
              </div>
            </div>

            {/* Smart Matching Toggle */}
            <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="use_smart_matching"
                  checked={formData.use_smart_matching}
                  onChange={(e) => setFormData({ ...formData, use_smart_matching: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="use_smart_matching" className="text-sm font-medium text-gray-700">
                  Use Smart Matching (Recommended)
                </label>
              </div>
              <p className="text-xs text-gray-600 mt-1">
                Smart matching uses demographics, topics, and similarity to find better creator matches and improve budget utilization.
              </p>
            </div>

            {/* Target Demographics Section */}
            {formData.use_smart_matching && (
              <div className="mt-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Target Demographics (Optional)</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="target_age_range" className="block text-sm font-medium text-gray-700">
                      Target Age Range
                    </label>
                    <select
                      id="target_age_range"
                      value={formData.target_age_range}
                      onChange={(e) => setFormData({ ...formData, target_age_range: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    >
                      <option value="">Select age range</option>
                      <option value="18-24">18-24</option>
                      <option value="25-34">25-34</option>
                      <option value="35-44">35-44</option>
                      <option value="45-54">45-54</option>
                      <option value="55-64">55-64</option>
                      <option value="25-44">25-44</option>
                      <option value="25-54">25-54</option>
                      <option value="35-54">35-54</option>
                      <option value="35-64">35-64</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="target_gender_skew" className="block text-sm font-medium text-gray-700">
                      Target Gender
                    </label>
                    <select
                      id="target_gender_skew"
                      value={formData.target_gender_skew}
                      onChange={(e) => setFormData({ ...formData, target_gender_skew: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    >
                      <option value="">Select gender</option>
                      <option value="mostly men">Mostly Men</option>
                      <option value="mostly women">Mostly Women</option>
                      <option value="even split">Even Split</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="target_location" className="block text-sm font-medium text-gray-700">
                      Target Location
                    </label>
                    <select
                      id="target_location"
                      value={formData.target_location}
                      onChange={(e) => setFormData({ ...formData, target_location: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    >
                      <option value="">Select location</option>
                      <option value="US">United States</option>
                      <option value="UK">United Kingdom</option>
                      <option value="AU">Australia</option>
                      <option value="NZ">New Zealand</option>
                      <option value="CA">Canada</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="target_interests" className="block text-sm font-medium text-gray-700">
                      Target Interests
                    </label>
                    <Input
                      id="target_interests"
                      type="text"
                      value={formData.target_interests}
                      onChange={(e) => setFormData({ ...formData, target_interests: e.target.value })}
                      className="mt-1"
                      placeholder="cooking, fitness, travel, technology"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Comma-separated list of interests (e.g., cooking, fitness, travel)
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Creator Filtering Section */}
            <div className="border-t pt-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Creator Filtering (Optional)</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="include_acct_ids" className="block text-sm font-medium text-gray-700">
                    Ensure These Creators Are Included
                  </label>
                  <Input
                    id="include_acct_ids"
                    type="text"
                    value={formData.include_acct_ids}
                    onChange={(e) => setFormData({ ...formData, include_acct_ids: e.target.value })}
                    className="mt-1"
                    placeholder="12345,67890,11111"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Comma-separated list of Acct IDs to guarantee inclusion in the plan
                  </p>
                </div>

                <div>
                  <label htmlFor="exclude_acct_ids" className="block text-sm font-medium text-gray-700">
                    Exclude These Creators
                  </label>
                  <Input
                    id="exclude_acct_ids"
                    type="text"
                    value={formData.exclude_acct_ids}
                    onChange={(e) => setFormData({ ...formData, exclude_acct_ids: e.target.value })}
                    className="mt-1"
                    placeholder="99999,88888"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Comma-separated list of Acct IDs to exclude from the plan
                  </p>
                </div>
              </div>
            </div>

            {/* Email Export Section */}
            <div className="border-t pt-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Email Export (Optional)</h3>
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                  Email Address
                </label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="mt-1"
                  placeholder="your-email@example.com"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Enter an email address to receive the plan as a CSV attachment
                </p>
              </div>
            </div>

            <Button type="submit" disabled={loading}>
              {loading ? 'Creating Plan...' : 'Create Plan'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-red-800">No Plan Generated</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-red-700 whitespace-pre-line">
              {error}
            </div>
            <div className="mt-4">
              <Button 
                onClick={() => setError(null)} 
                variant="outline" 
                className="border-red-300 text-red-700 hover:bg-red-100"
              >
                Try Again
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {plan && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>Plan Results</CardTitle>
                <CardDescription>
                  {plan.picked_creators.length} creators selected
                  {plan.picked_creators.length > 50 && (
                    <span className="ml-2 text-orange-600 font-medium">
                      (Large plan - showing first 20, full data in CSV)
                    </span>
                  )}
                </CardDescription>
              </div>
              <Button onClick={exportToCsv} variant="outline">
                Export CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-gray-50 p-4 rounded-md">
                <div className="text-sm text-gray-500">Total Spend</div>
                <div className="text-2xl font-bold">${plan.total_spend.toLocaleString()}</div>
              </div>
              <div className="bg-gray-50 p-4 rounded-md">
                <div className="text-sm text-gray-500">Total Conversions</div>
                <div className="text-2xl font-bold">{plan.total_conversions.toFixed(0)}</div>
              </div>
              <div className="bg-gray-50 p-4 rounded-md">
                <div className="text-sm text-gray-500">Blended CPA</div>
                <div className="text-2xl font-bold">${plan.blended_cpa.toFixed(2)}</div>
              </div>
              <div className="bg-gray-50 p-4 rounded-md">
                <div className="text-sm text-gray-500">Budget Utilization</div>
                <div className="text-2xl font-bold">{(plan.budget_utilization * 100).toFixed(1)}%</div>
              </div>
            </div>

            <div className="mb-4 text-sm text-gray-600">
              Showing first 20 of {plan.picked_creators.length} creators. Full list available in CSV download.
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Creator
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Expected CVR
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Expected CPA
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Expected Clicks
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Expected Spend
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Expected Conversions
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Placements
                    </th>
                    {formData.use_smart_matching && (
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Matching Rationale
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {plan.picked_creators.slice(0, 20).map((creator) => {
                    try {
                      return (
                    <tr key={creator.creator_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{creator.name}</div>
                        <div className="text-sm text-gray-500">{creator.acct_id}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {(creator.expected_cvr * 100).toFixed(2)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {creator.expected_cpa ? `$${creator.expected_cpa.toFixed(2)}` : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {creator.expected_clicks.toFixed(0)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        ${creator.expected_spend.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {creator.expected_conversions.toFixed(0)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <div className="font-medium">
                          {creator.recommended_placements || 1}
                        </div>
                        {creator.median_clicks_per_placement && (
                          <div className="text-xs text-gray-500">
                            {creator.median_clicks_per_placement.toFixed(0)} clicks/placement
                          </div>
                        )}
                      </td>
                      {formData.use_smart_matching && (
                        <td className="px-6 py-4 text-sm text-gray-900">
                          <div className="max-w-xs">
                            <div className="text-xs text-gray-600 mb-1">
                              {creator.matching_rationale || 'Historical performance data available'}
                            </div>
                            {creator.tier && (
                              <div className="flex items-center space-x-2">
                                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                  creator.tier === 1 ? 'bg-green-100 text-green-800' :
                                  creator.tier === 2 ? 'bg-blue-100 text-blue-800' :
                                  creator.tier === 3 ? 'bg-yellow-100 text-yellow-800' :
                                  'bg-purple-100 text-purple-800'
                                }`}>
                                  Tier {creator.tier}
                                </span>
                                {creator.combined_score && (
                                  <span className="text-xs text-gray-500">
                                    Score: {(creator.combined_score * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                      );
                    } catch (error) {
                      console.error('Error rendering creator:', creator.creator_id, error);
                      return (
                        <tr key={creator.creator_id} className="bg-red-50">
                          <td colSpan={formData.use_smart_matching ? 7 : 6} className="px-6 py-4 text-sm text-red-600">
                            Error rendering creator: {creator.name || creator.creator_id}
                          </td>
                        </tr>
                      );
                    }
                  })}
                </tbody>
              </table>
            </div>
            
            {/* Smart Matching Legend */}
            {formData.use_smart_matching && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h4 className="text-sm font-medium text-gray-900 mb-3">Matching Tier Legend</h4>
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Tier 1
                    </span>
                    <span className="text-gray-600">Historical performance data</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Tier 2
                    </span>
                    <span className="text-gray-600">Topic/keyword matches to high performers</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      Tier 3
                    </span>
                    <span className="text-gray-600">Demographic alignment with target audience</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                      Tier 4
                    </span>
                    <span className="text-gray-600">Similar to high-performing creators</span>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
