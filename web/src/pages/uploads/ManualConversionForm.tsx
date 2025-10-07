import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';

interface ManualFormData {
  advertiser_id: string;
  campaign_id: string;
  insertion_id: string;
  range_start: string;
  range_end: string;
  acct_id: string;
  conversions: string;
}

const ManualConversionForm: React.FC = () => {
  const [advertisers, setAdvertisers] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [insertions, setInsertions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const { toast } = useToast();

  const form = useForm<ManualFormData>({
    defaultValues: {
      advertiser_id: '',
      campaign_id: '',
      insertion_id: '',
      range_start: '',
      range_end: '',
      acct_id: '',
      conversions: '',
    },
  });

  const selectedAdvertiserId = form.watch('advertiser_id');
  const selectedCampaignId = form.watch('campaign_id');

  // Load advertisers on component mount
  React.useEffect(() => {
    const loadAdvertisers = async () => {
      try {
        const response = await fetch('/api/advertisers');
        if (!response.ok) throw new Error('Failed to fetch advertisers');
        const data = await response.json();
        setAdvertisers(data);
      } catch (error) {
        console.error('Error fetching advertisers:', error);
        toast({
          title: 'Error',
          description: 'Failed to load advertisers',
          variant: 'destructive',
        });
      }
    };
    loadAdvertisers();
  }, [toast]);

  // Load campaigns when advertiser changes
  React.useEffect(() => {
    if (!selectedAdvertiserId) {
      setCampaigns([]);
      setInsertions([]);
      form.setValue('campaign_id', '');
      form.setValue('insertion_id', '');
      return;
    }

    const loadCampaigns = async () => {
      try {
        const response = await fetch(`/api/campaigns?advertiser_id=${selectedAdvertiserId}`);
        if (!response.ok) throw new Error('Failed to fetch campaigns');
        const data = await response.json();
        setCampaigns(data);
        setInsertions([]);
        form.setValue('campaign_id', '');
        form.setValue('insertion_id', '');
      } catch (error) {
        console.error('Error fetching campaigns:', error);
        toast({
          title: 'Error',
          description: 'Failed to load campaigns',
          variant: 'destructive',
        });
      }
    };
    loadCampaigns();
  }, [selectedAdvertiserId, form, toast]);

  // Load insertions when campaign changes
  React.useEffect(() => {
    if (!selectedCampaignId) {
      setInsertions([]);
      form.setValue('insertion_id', '');
      return;
    }

    const loadInsertions = async () => {
      try {
        const response = await fetch(`/api/insertions?campaign_id=${selectedCampaignId}`);
        if (!response.ok) throw new Error('Failed to fetch insertions');
        const data = await response.json();
        setInsertions(data);
        form.setValue('insertion_id', '');
      } catch (error) {
        console.error('Error fetching insertions:', error);
        toast({
          title: 'Error',
          description: 'Failed to load insertions',
          variant: 'destructive',
        });
      }
    };
    loadInsertions();
  }, [selectedCampaignId, form, toast]);

  const onSubmit = async (data: ManualFormData) => {
    setLoading(true);
    setResult(null);
    
    try {
      const params = new URLSearchParams({
        advertiser_id: data.advertiser_id,
        campaign_id: data.campaign_id,
        insertion_id: data.insertion_id,
        range_start: data.range_start,
        range_end: data.range_end,
        acct_id: data.acct_id,
        conversions: data.conversions,
      });

      const response = await fetch(`/api/simple-conversion?${params}`);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();
      setResult(result);

      toast({
        title: 'Success',
        description: `Conversion uploaded successfully! Upload ID: ${result.conv_upload_id}`,
      });

      form.reset();
    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: 'Upload Failed',
        description: error instanceof Error ? error.message : 'Unknown error occurred',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manual Conversion Entry</CardTitle>
        <CardDescription>
          Manually enter conversion data for a specific creator
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="advertiser_id"
                rules={{ required: 'Please select an advertiser' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Advertiser</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select advertiser" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {advertisers.map((advertiser) => (
                          <SelectItem key={advertiser.advertiser_id} value={advertiser.advertiser_id.toString()}>
                            {advertiser.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="campaign_id"
                rules={{ required: 'Please select a campaign' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Campaign</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value} disabled={!selectedAdvertiserId}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select campaign" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {campaigns.map((campaign) => (
                          <SelectItem key={campaign.campaign_id} value={campaign.campaign_id.toString()}>
                            {campaign.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="insertion_id"
                rules={{ required: 'Please select an insertion' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Insertion</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value} disabled={!selectedCampaignId}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select insertion" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {insertions.map((insertion) => (
                          <SelectItem key={insertion.insertion_id} value={insertion.insertion_id.toString()}>
                            {insertion.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="range_start"
                rules={{ required: 'Please enter start date' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Start Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="range_end"
                rules={{ required: 'Please enter end date' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>End Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="acct_id"
                rules={{ required: 'Please enter account ID' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Account ID</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., 24707" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="conversions"
                rules={{ required: 'Please enter conversions', pattern: { value: /^\d+$/, message: 'Must be a number' } }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Conversions</FormLabel>
                    <FormControl>
                      <Input type="number" placeholder="e.g., 1" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? 'Uploading...' : 'Upload Conversion'}
            </Button>
          </form>
        </Form>

        {result && (
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
            <h4 className="font-semibold text-green-800 mb-2">Upload Result:</h4>
            <p><strong>Conversion Upload ID:</strong> {result.conv_upload_id}</p>
            <p><strong>Creator ID:</strong> {result.creator_id}</p>
            <p><strong>Conversion ID:</strong> {result.conversion_id}</p>
            <p><strong>Success:</strong> {result.success ? 'Yes' : 'No'}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ManualConversionForm;
