import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';

interface Advertiser {
  advertiser_id: number;
  name: string;
  category?: string;
}

interface Campaign {
  campaign_id: number;
  advertiser_id: number;
  name: string;
}

interface Insertion {
  insertion_id: number;
  campaign_id: number;
  month_start: string;
  month_end: string;
  cpc: number;
}

export function ManualConversionForm() {
  const [advertisers, setAdvertisers] = useState<Advertiser[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [insertions, setInsertions] = useState<Insertion[]>([]);
  const [selectedAdvertiser, setSelectedAdvertiser] = useState(0);
  const [selectedCampaign, setSelectedCampaign] = useState(0);
  const [selectedInsertion, setSelectedInsertion] = useState(0);
  const [dateRange, setDateRange] = useState({
    start: '',
    end: '',
  });
  const [acctId, setAcctId] = useState('');
  const [conversions, setConversions] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

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
    if (selectedAdvertiser) {
      const fetchCampaigns = async () => {
        try {
          const data = await api.getCampaigns(selectedAdvertiser);
          setCampaigns(data);
          setSelectedCampaign(0);
          setSelectedInsertion(0);
        } catch (error) {
          console.error('Error fetching campaigns:', error);
        }
      };
      fetchCampaigns();
    }
  }, [selectedAdvertiser]);

  useEffect(() => {
    if (selectedCampaign) {
      const fetchInsertions = async () => {
        try {
          const data = await api.getInsertions(selectedCampaign);
          setInsertions(data);
          setSelectedInsertion(0);
        } catch (error) {
          console.error('Error fetching insertions:', error);
        }
      };
      fetchInsertions();
    }
  }, [selectedCampaign]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAdvertiser || !selectedCampaign || !selectedInsertion || !dateRange.start || !dateRange.end || !acctId || !conversions) return;

    setLoading(true);
    setResult(null);

    try {
      // Use the simple endpoint to directly insert conversion
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/simple-conversion?advertiser_id=${selectedAdvertiser}&campaign_id=${selectedCampaign}&insertion_id=${selectedInsertion}&range_start=${dateRange.start}&range_end=${dateRange.end}&acct_id=${acctId}&conversions=${conversions}`);
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setResult(data);
      toast.success(`Conversion added successfully!`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      toast.error(`Failed to add conversion: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manual Conversion Entry</CardTitle>
        <CardDescription>
          Add conversion data manually without CSV upload
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label htmlFor="advertiser" className="block text-sm font-medium text-gray-700">
                Advertiser *
              </label>
              <select
                id="advertiser"
                value={selectedAdvertiser}
                onChange={(e) => setSelectedAdvertiser(parseInt(e.target.value))}
                required
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

            <div>
              <label htmlFor="campaign" className="block text-sm font-medium text-gray-700">
                Campaign *
              </label>
              <select
                id="campaign"
                value={selectedCampaign}
                onChange={(e) => setSelectedCampaign(parseInt(e.target.value))}
                required
                disabled={!selectedAdvertiser}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
              >
                <option value={0}>Select campaign</option>
                {campaigns.map((campaign) => (
                  <option key={campaign.campaign_id} value={campaign.campaign_id}>
                    {campaign.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="insertion" className="block text-sm font-medium text-gray-700">
                Insertion *
              </label>
              <select
                id="insertion"
                value={selectedInsertion}
                onChange={(e) => setSelectedInsertion(parseInt(e.target.value))}
                required
                disabled={!selectedCampaign}
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
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="start_date" className="block text-sm font-medium text-gray-700">
                Range Start Date *
              </label>
              <Input
                id="start_date"
                type="date"
                value={dateRange.start}
                onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                required
                className="mt-1"
              />
            </div>

            <div>
              <label htmlFor="end_date" className="block text-sm font-medium text-gray-700">
                Range End Date *
              </label>
              <Input
                id="end_date"
                type="date"
                value={dateRange.end}
                onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                required
                className="mt-1"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="acct_id" className="block text-sm font-medium text-gray-700">
                Account ID *
              </label>
              <Input
                id="acct_id"
                type="text"
                value={acctId}
                onChange={(e) => setAcctId(e.target.value)}
                placeholder="24707"
                required
                className="mt-1"
              />
            </div>

            <div>
              <label htmlFor="conversions" className="block text-sm font-medium text-gray-700">
                Conversions *
              </label>
              <Input
                id="conversions"
                type="number"
                value={conversions}
                onChange={(e) => setConversions(e.target.value)}
                placeholder="1"
                required
                className="mt-1"
              />
            </div>
          </div>

          <Button type="submit" disabled={loading || !selectedAdvertiser || !selectedCampaign || !selectedInsertion || !dateRange.start || !dateRange.end || !acctId || !conversions}>
            {loading ? 'Adding...' : 'Add Conversion'}
          </Button>

          {result && (
            <div className="mt-4 p-4 bg-green-50 rounded-md">
              <h4 className="text-sm font-medium text-green-800 mb-2">Success!</h4>
              <div className="text-sm text-green-700">
                <p>Conversion Upload ID: {result.conv_upload_id}</p>
                <p>Creator ID: {result.creator_id}</p>
                <p>Conversion ID: {result.conversion_id}</p>
                <p>Success: {result.success ? 'Yes' : 'No'}</p>
              </div>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
