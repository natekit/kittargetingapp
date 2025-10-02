import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';
import { downloadAsCsv } from '../../lib/csv';

interface CreatorStats {
  creator_id: number;
  name: string;
  acct_id: string;
  clicks: number;
  conversions: number;
  cvr: number;
  expected_cpa?: number;
}

export function LeaderboardPage() {
  const [creators, setCreators] = useState<CreatorStats[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    category: '',
    limit: 50,
    cpc: '',
  });

  const fetchLeaderboard = async () => {
    setLoading(true);
    try {
      const data = await api.getLeaderboard(
        filters.category || undefined,
        filters.limit,
        filters.cpc ? parseFloat(filters.cpc) : undefined
      );
      setCreators(data);
    } catch (error) {
      console.error('Error fetching leaderboard:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaderboard();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchLeaderboard();
  };

  const exportToCsv = () => {
    const headers = ['Creator ID', 'Name', 'Account ID', 'Clicks', 'Conversions', 'CVR', 'Expected CPA'];
    const csvData = creators.map(creator => [
      creator.creator_id,
      creator.name,
      creator.acct_id,
      creator.clicks,
      creator.conversions,
      creator.cvr.toFixed(4),
      creator.expected_cpa?.toFixed(2) || ''
    ]);

    downloadAsCsv('leaderboard', csvData, headers);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Leaderboard</h1>
        <p className="mt-2 text-gray-600">
          View creator performance metrics and rankings
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>
            Filter and sort the leaderboard by category and other criteria
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label htmlFor="category" className="block text-sm font-medium text-gray-700">
                  Category
                </label>
                <Input
                  id="category"
                  type="text"
                  value={filters.category}
                  onChange={(e) => setFilters({ ...filters, category: e.target.value })}
                  placeholder="e.g., News"
                  className="mt-1"
                />
              </div>

              <div>
                <label htmlFor="limit" className="block text-sm font-medium text-gray-700">
                  Limit
                </label>
                <Input
                  id="limit"
                  type="number"
                  min="1"
                  max="1000"
                  value={filters.limit}
                  onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value) || 50 })}
                  className="mt-1"
                />
              </div>

              <div>
                <label htmlFor="cpc" className="block text-sm font-medium text-gray-700">
                  CPC (for Expected CPA)
                </label>
                <Input
                  id="cpc"
                  type="number"
                  step="0.01"
                  min="0"
                  value={filters.cpc}
                  onChange={(e) => setFilters({ ...filters, cpc: e.target.value })}
                  placeholder="0.45"
                  className="mt-1"
                />
              </div>
            </div>

            <Button type="submit" disabled={loading}>
              {loading ? 'Loading...' : 'Apply Filters'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Creator Leaderboard</CardTitle>
              <CardDescription>
                {creators.length} creators found
              </CardDescription>
            </div>
            <Button onClick={exportToCsv} variant="outline">
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8">
              <div className="text-gray-500">Loading leaderboard...</div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Creator
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Account ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Clicks
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Conversions
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      CVR
                    </th>
                    {filters.cpc && (
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Expected CPA
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {creators.map((creator) => (
                    <tr key={creator.creator_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {creator.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {creator.acct_id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {creator.clicks.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {creator.conversions.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {(creator.cvr * 100).toFixed(2)}%
                      </td>
                      {filters.cpc && (
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {creator.expected_cpa ? `$${creator.expected_cpa.toFixed(2)}` : '-'}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
