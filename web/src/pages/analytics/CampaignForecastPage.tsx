import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { CampaignForecastChart } from '../../components/CampaignForecastChart';
import { api } from '../../api';
import { Campaign, CampaignForecastResponse } from '../../types';

export function CampaignForecastPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [forecastData, setForecastData] = useState<CampaignForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number>(0);

  useEffect(() => {
    const fetchCampaigns = async () => {
      try {
        const data = await api.getCampaigns();
        setCampaigns(data);
      } catch (error) {
        console.error('Error fetching campaigns:', error);
      }
    };
    fetchCampaigns();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCampaignId) return;

    setLoading(true);
    setForecastData(null);
    setError(null);

    try {
      const data = await api.getCampaignForecast(selectedCampaignId);
      console.log('Forecast data received:', data);
      console.log('First forecast item:', data.forecast_data[0]);
      setForecastData(data);
    } catch (error) {
      console.error('Error fetching campaign forecast:', error);
      setError('Failed to fetch campaign forecast. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getForecastMethodColor = (method: string) => {
    switch (method) {
      case 'current_month':
        return 'bg-green-100 text-green-800';
      case 'other_campaigns':
        return 'bg-blue-100 text-blue-800';
      case 'conservative_estimate':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getForecastMethodLabel = (method: string) => {
    switch (method) {
      case 'current_month':
        return 'Current Month';
      case 'other_campaigns':
        return 'Other Campaigns';
      case 'conservative_estimate':
        return 'Conservative Estimate';
      default:
        return method;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Campaign Forecasting</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Select Campaign to Forecast</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="campaign_id" className="block text-sm font-medium text-gray-700">
                Campaign
              </label>
              <select
                id="campaign_id"
                value={selectedCampaignId}
                onChange={(e) => setSelectedCampaignId(parseInt(e.target.value) || 0)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value={0}>Select campaign</option>
                {campaigns.map((campaign) => (
                  <option key={campaign.campaign_id} value={campaign.campaign_id}>
                    {campaign.name} (ID: {campaign.campaign_id})
                  </option>
                ))}
              </select>
            </div>

            <Button type="submit" disabled={loading || !selectedCampaignId}>
              {loading ? 'Loading...' : 'Generate Forecast'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-red-800">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-red-700">{error}</div>
          </CardContent>
        </Card>
      )}

      {forecastData && (
        <>
          {/* Summary Statistics */}
          <Card>
            <CardHeader>
              <CardTitle>Forecast Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Campaign</div>
                  <div className="text-lg font-bold">{forecastData.campaign_name}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Future Insertions</div>
                  <div className="text-2xl font-bold">{forecastData.future_insertions_count}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Total Forecasted Clicks</div>
                  <div className="text-2xl font-bold">{forecastData.total_forecasted_clicks.toLocaleString()}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Total Forecasted Spend</div>
                  <div className="text-2xl font-bold">${forecastData.total_forecasted_spend.toLocaleString()}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Forecast Details */}
          <Card>
            <CardHeader>
              <CardTitle>Forecast Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Creator
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Insertion Period
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Execution Date
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        CPC
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Forecasted Clicks
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Forecasted Spend
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Method
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {forecastData.forecast_data.map((placement) => (
                      <tr key={placement.placement_id} className="hover:bg-gray-50">
                        <td className="px-4 py-4">
                          <div className="space-y-1">
                            <div className="text-sm font-medium text-gray-900">{placement.creator_name}</div>
                            <div className="text-xs text-gray-500">ID: {placement.creator_acct_id}</div>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900">
                          <div className="font-medium">
                            {new Date(placement.insertion_month_start).toLocaleDateString('en-US', { 
                              month: 'short', 
                              year: 'numeric' 
                            })}
                          </div>
                          <div className="text-xs text-gray-500">
                            {new Date(placement.insertion_month_start).toLocaleDateString()} - {new Date(placement.insertion_month_end).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900">
                          <div className="font-medium">
                            {placement.execution_date ? 
                              new Date(placement.execution_date).toLocaleDateString('en-US', { 
                                month: 'short', 
                                day: 'numeric',
                                year: 'numeric' 
                              }) : 
                              'No date'
                            }
                          </div>
                          <div className="text-xs text-gray-500">
                            {placement.execution_date ? 
                              new Date(placement.execution_date).toLocaleDateString() : 
                              'Execution date not available'
                            }
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900">
                          ${placement.cpc.toFixed(4)}
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900">
                          <div className="font-medium">{placement.forecasted_clicks.toLocaleString()}</div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900">
                          <div className="font-medium">${placement.forecasted_spend.toLocaleString()}</div>
                        </td>
                        <td className="px-4 py-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getForecastMethodColor(placement.forecast_method)}`}>
                            {getForecastMethodLabel(placement.forecast_method)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Forecast Chart */}
          <CampaignForecastChart
            forecastData={forecastData.forecast_data}
            campaignName={forecastData.campaign_name}
            totalForecastedSpend={forecastData.total_forecasted_spend}
            totalForecastedClicks={forecastData.total_forecasted_clicks}
          />
        </>
      )}
    </div>
  );
}
