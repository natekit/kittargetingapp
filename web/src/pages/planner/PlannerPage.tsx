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
  const [formData, setFormData] = useState({
    category: '',
    advertiser_id: 0,
    insertion_id: 0,
    cpc: '',
    budget: '',
    target_cpa: '',
    advertiser_avg_cvr: '',
    horizon_days: 30,
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

      const data = await api.createPlan(requestData);
      setPlan(data);
    } catch (error) {
      console.error('Error creating plan:', error);
    } finally {
      setLoading(false);
    }
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
      creator.expected_cpa.toFixed(2),
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
                  Leave blank to prioritize by CVR instead of CPA
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

            <Button type="submit" disabled={loading}>
              {loading ? 'Creating Plan...' : 'Create Plan'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {plan && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>Plan Results</CardTitle>
                <CardDescription>
                  {plan.picked_creators.length} creators selected
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
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {plan.picked_creators.map((creator) => (
                    <tr key={creator.creator_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{creator.name}</div>
                        <div className="text-sm text-gray-500">{creator.acct_id}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {(creator.expected_cvr * 100).toFixed(2)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        ${creator.expected_cpa.toFixed(2)}
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
