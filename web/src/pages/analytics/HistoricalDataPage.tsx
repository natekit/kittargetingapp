import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { api } from '../../api';
import { Advertiser, Insertion, HistoricalDataResponse } from '../../types';

export function HistoricalDataPage() {
  const [advertisers, setAdvertisers] = useState<Advertiser[]>([]);
  const [insertions, setInsertions] = useState<Insertion[]>([]);
  const [loading, setLoading] = useState(false);
  const [historicalData, setHistoricalData] = useState<HistoricalDataResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    advertiser_id: 0,
    insertion_id: 0,
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
          const data = await api.getInsertions(formData.advertiser_id);
          setInsertions(data);
        } catch (error) {
          console.error('Error fetching insertions:', error);
        }
      };
      fetchInsertions();
    } else {
      setInsertions([]);
    }
  }, [formData.advertiser_id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setHistoricalData(null);
    setError(null);

    try {
      const data = await api.getHistoricalData(
        formData.advertiser_id || undefined,
        formData.insertion_id || undefined
      );
      setHistoricalData(data);
    } catch (error) {
      console.error('Error fetching historical data:', error);
      setError('Failed to fetch historical data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Historical Data Viewer</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Select Data Source</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="advertiser_id" className="block text-sm font-medium text-gray-700">
                  Advertiser
                </label>
                <select
                  id="advertiser_id"
                  value={formData.advertiser_id}
                  onChange={(e) => setFormData({ ...formData, advertiser_id: parseInt(e.target.value) || 0, insertion_id: 0 })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value={0}>Select advertiser</option>
                  {advertisers.map((advertiser) => (
                    <option key={advertiser.advertiser_id} value={advertiser.advertiser_id}>
                      {advertiser.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="insertion_id" className="block text-sm font-medium text-gray-700">
                  Insertion (Optional)
                </label>
                <select
                  id="insertion_id"
                  value={formData.insertion_id}
                  onChange={(e) => setFormData({ ...formData, insertion_id: parseInt(e.target.value) || 0 })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  disabled={!formData.advertiser_id}
                >
                  <option value={0}>All insertions</option>
                  {insertions.map((insertion) => (
                    <option key={insertion.insertion_id} value={insertion.insertion_id}>
                      Insertion {insertion.insertion_id} (${insertion.cpc} CPC)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Button type="submit" disabled={loading || !formData.advertiser_id}>
              {loading ? 'Loading...' : 'View Historical Data'}
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

      {historicalData && (
        <>
          {/* Summary Statistics */}
          <Card>
            <CardHeader>
              <CardTitle>Summary Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Total Creators</div>
                  <div className="text-2xl font-bold">{historicalData.summary.total_creators}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Creators with Clicks</div>
                  <div className="text-2xl font-bold">{historicalData.summary.creators_with_clicks}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Creators with Conversions</div>
                  <div className="text-2xl font-bold">{historicalData.summary.creators_with_conversions}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Total Clicks</div>
                  <div className="text-2xl font-bold">{historicalData.summary.total_clicks.toLocaleString()}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Total Conversions</div>
                  <div className="text-2xl font-bold">{historicalData.summary.total_conversions.toLocaleString()}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="text-sm text-gray-500">Overall CVR</div>
                  <div className="text-2xl font-bold">{(historicalData.summary.overall_cvr * 100).toFixed(2)}%</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Creator Details */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Creator Performance Data</CardTitle>
                <Button 
                  onClick={() => api.downloadHistoricalDataCSV(
                    formData.advertiser_id || undefined,
                    formData.insertion_id || undefined
                  )}
                  variant="outline"
                >
                  Download CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">
                        Creator
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                        Demographics
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-40">
                        Performance
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">
                        Recent Activity
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {historicalData.creators.map((creator: any) => (
                      <tr key={creator.creator_id} className="hover:bg-gray-50">
                        {/* Creator Info */}
                        <td className="px-4 py-4">
                          <div className="space-y-1">
                            <div className="text-sm font-medium text-gray-900 truncate" title={creator.name}>
                              {creator.name}
                            </div>
                            <div className="text-xs text-gray-500">ID: {creator.acct_id}</div>
                            <div className="text-xs text-gray-500">Topic: {creator.topic || 'N/A'}</div>
                          </div>
                        </td>
                        
                        {/* Demographics */}
                        <td className="px-4 py-4">
                          <div className="space-y-1">
                            <div className="text-xs text-gray-900">
                              <span className="font-medium">Age:</span> {creator.age_range || 'N/A'}
                            </div>
                            <div className="text-xs text-gray-900">
                              <span className="font-medium">Gender:</span> {creator.gender_skew || 'N/A'}
                            </div>
                            <div className="text-xs text-gray-900">
                              <span className="font-medium">Location:</span> {creator.location || 'N/A'}
                            </div>
                            {creator.interests && (
                              <div className="text-xs text-gray-500 mt-1 truncate" title={creator.interests}>
                                {creator.interests}
                              </div>
                            )}
                          </div>
                        </td>
                        
                        {/* Performance */}
                        <td className="px-4 py-4">
                          <div className="space-y-2">
                            <div className="flex justify-between items-center">
                              <span className="text-xs text-gray-500">Clicks:</span>
                              <span className="text-sm font-medium">{creator.total_clicks.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-xs text-gray-500">Conversions:</span>
                              <span className="text-sm font-medium">{creator.total_conversions.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-xs text-gray-500">CVR:</span>
                              <span className="text-sm font-medium text-blue-600">
                                {(creator.cvr * 100).toFixed(2)}%
                              </span>
                            </div>
                            {creator.conservative_click_estimate && (
                              <div className="flex justify-between items-center">
                                <span className="text-xs text-gray-500">Estimate:</span>
                                <span className="text-sm font-medium">{creator.conservative_click_estimate}</span>
                              </div>
                            )}
                          </div>
                        </td>
                        
                        {/* Recent Activity */}
                        <td className="px-4 py-4">
                          <div className="space-y-3">
                            {creator.recent_clicks.length > 0 && (
                              <div>
                                <div className="text-xs font-medium text-gray-700 mb-1">Recent Clicks</div>
                                <div className="space-y-1">
                                  {creator.recent_clicks.slice(0, 2).map((click: any, idx: number) => (
                                    <div key={idx} className="text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded">
                                      {new Date(click.execution_date).toLocaleDateString()}: {click.unique_clicks} clicks
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {creator.recent_conversions.length > 0 && (
                              <div>
                                <div className="text-xs font-medium text-gray-700 mb-1">Recent Conversions</div>
                                <div className="space-y-1">
                                  {creator.recent_conversions.slice(0, 2).map((conv: any, idx: number) => (
                                    <div key={idx} className="text-xs text-gray-600 bg-green-50 px-2 py-1 rounded">
                                      {conv.period}: {conv.conversions} conversions
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {creator.recent_clicks.length === 0 && creator.recent_conversions.length === 0 && (
                              <div className="text-xs text-gray-400 italic">No recent activity</div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
