import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';

interface Campaign {
  campaign_id: number;
  advertiser_id: number;
  name: string;
  start_date: string;
  end_date: string;
}

export function InsertionForm() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [formData, setFormData] = useState({
    campaign_id: 0,
    month_start: '',
    month_end: '',
    cpc: '',
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

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
    setLoading(true);
    setMessage('');

    try {
      await api.createInsertion({
        ...formData,
        campaign_id: formData.campaign_id,
        cpc: parseFloat(formData.cpc),
      });
      setMessage('Insertion created successfully!');
      setFormData({
        campaign_id: 0,
        month_start: '',
        month_end: '',
        cpc: '',
      });
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create Insertion</CardTitle>
        <CardDescription>
          Add a new insertion for a campaign
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="campaign" className="block text-sm font-medium text-gray-700">
              Campaign *
            </label>
            <select
              id="campaign"
              value={formData.campaign_id}
              onChange={(e) => setFormData({ ...formData, campaign_id: parseInt(e.target.value) })}
              required
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value={0}>Select a campaign</option>
              {campaigns.map((campaign) => (
                <option key={campaign.campaign_id} value={campaign.campaign_id}>
                  {campaign.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="month_start" className="block text-sm font-medium text-gray-700">
                Month Start *
              </label>
              <Input
                id="month_start"
                type="date"
                value={formData.month_start}
                onChange={(e) => setFormData({ ...formData, month_start: e.target.value })}
                required
                className="mt-1"
              />
            </div>

            <div>
              <label htmlFor="month_end" className="block text-sm font-medium text-gray-700">
                Month End *
              </label>
              <Input
                id="month_end"
                type="date"
                value={formData.month_end}
                onChange={(e) => setFormData({ ...formData, month_end: e.target.value })}
                required
                className="mt-1"
              />
            </div>
          </div>

          <div>
            <label htmlFor="cpc" className="block text-sm font-medium text-gray-700">
              CPC (Cost Per Click) *
            </label>
            <Input
              id="cpc"
              type="number"
              step="0.01"
              min="0"
              value={formData.cpc}
              onChange={(e) => setFormData({ ...formData, cpc: e.target.value })}
              required
              className="mt-1"
              placeholder="0.45"
            />
          </div>

          <Button type="submit" disabled={loading}>
            {loading ? 'Creating...' : 'Create Insertion'}
          </Button>

          {message && (
            <div className={`text-sm ${message.includes('Error') ? 'text-red-600' : 'text-green-600'}`}>
              {message}
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
