import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';
import { parseCSVFile, validateCSVStructure, getCSVPreview, formatCSVErrors } from '../../lib/csvParser';

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

export function PerformanceUpload() {
  const [advertisers, setAdvertisers] = useState<Advertiser[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [insertions, setInsertions] = useState<Insertion[]>([]);
  const [selectedAdvertiser, setSelectedAdvertiser] = useState(0);
  const [selectedCampaign, setSelectedCampaign] = useState(0);
  const [selectedInsertion, setSelectedInsertion] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [csvPreview, setCsvPreview] = useState<string[][]>([]);
  const [csvErrors, setCsvErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setMessage('');
      setResult(null);
      setCsvErrors([]);
      
      try {
        // Parse CSV with proper handling
        const parseResult = await parseCSVFile(selectedFile);
        
        // Validate structure for performance data
        const validation = validateCSVStructure(parseResult.data, [
          'Creator', 'Clicks', 'Unique', 'Flagged', 'Execution Date', 'Status'
        ]);
        
        if (!validation.isValid) {
          setCsvErrors(validation.errors);
          toast.error('CSV validation failed. Please check the file format.');
          return;
        }
        
        // Format parsing errors if any
        if (parseResult.errors.length > 0) {
          const formattedErrors = formatCSVErrors(parseResult.errors);
          setCsvErrors(formattedErrors);
          toast.warning(`CSV parsing warnings: ${formattedErrors.length} issues found`);
        }
        
        // Set preview
        const preview = getCSVPreview(parseResult.data, 5);
        setCsvPreview(preview);
        
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to parse CSV';
        setCsvErrors([errorMessage]);
        toast.error(`CSV parsing failed: ${errorMessage}`);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedInsertion) return;

    setLoading(true);
    setMessage('');

    try {
      const data = await api.uploadPerformance(selectedInsertion, file);
      setResult(data);
      setMessage('Upload successful!');
      toast.success(`Performance data uploaded successfully! ${data.inserted_rows} rows inserted.`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setMessage(`Error: ${errorMessage}`);
      toast.error(`Upload failed: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Performance Upload</h1>
        <p className="mt-2 text-gray-600">
          Upload performance data for an insertion
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload Performance Data</CardTitle>
          <CardDescription>
            Select advertiser, campaign, and insertion, then upload your CSV file
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

            <div>
              <label htmlFor="file" className="block text-sm font-medium text-gray-700">
                CSV File *
              </label>
              <Input
                id="file"
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                required
                className="mt-1"
              />
            </div>

            {csvPreview.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">CSV Preview (first 5 rows):</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 border border-gray-300">
                    <thead className="bg-gray-50">
                      <tr>
                        {csvPreview[0]?.map((header, index) => (
                          <th key={index} className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {csvPreview.slice(1).map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {row.map((cell, cellIndex) => (
                            <td key={cellIndex} className="px-3 py-2 text-sm text-gray-900">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <Button type="submit" disabled={loading || !file || !selectedInsertion || csvErrors.length > 0}>
              {loading ? 'Uploading...' : 'Upload Performance Data'}
            </Button>
            
            {csvErrors.length > 0 && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
                <h4 className="text-sm font-medium text-red-800 mb-2">CSV Issues:</h4>
                <ul className="text-sm text-red-700 list-disc list-inside">
                  {csvErrors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            )}

            {message && (
              <div className={`text-sm ${message.includes('Error') ? 'text-red-600' : 'text-green-600'}`}>
                {message}
              </div>
            )}

            {result && (
              <div className="mt-4 p-4 bg-gray-50 rounded-md">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Upload Results:</h4>
                <div className="text-sm text-gray-600">
                  <p>Performance Upload ID: {result.perf_upload_id}</p>
                  <p>Inserted Rows: {result.inserted_rows}</p>
                  <p>Unmatched Count: {result.unmatched_count}</p>
                  {result.unmatched_examples && result.unmatched_examples.length > 0 && (
                    <div>
                      <p className="font-medium">Unmatched Examples:</p>
                      <ul className="list-disc list-inside ml-2">
                        {result.unmatched_examples.map((example: string, index: number) => (
                          <li key={index}>{example}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
