import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';
import type { Advertiser } from '../../types';

interface FormErrors {
  advertiser_id?: string;
  name?: string;
  start_date?: string;
  end_date?: string;
  notes?: string;
}

export function CampaignForm() {
  const [advertisers, setAdvertisers] = useState<Advertiser[]>([]);
  const [formData, setFormData] = useState({
    advertiser_id: 0,
    name: '',
    start_date: '',
    end_date: '',
    notes: '',
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});

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

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    
    // Advertiser validation
    if (!formData.advertiser_id || formData.advertiser_id === 0) {
      newErrors.advertiser_id = 'Please select an advertiser';
    }
    
    // Name validation
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    } else if (formData.name.trim().length < 2) {
      newErrors.name = 'Name must be at least 2 characters';
    } else if (formData.name.trim().length > 255) {
      newErrors.name = 'Name must be less than 255 characters';
    }
    
    // Date validation
    if (!formData.start_date) {
      newErrors.start_date = 'Start date is required';
    }
    
    if (!formData.end_date) {
      newErrors.end_date = 'End date is required';
    } else {
      const endDate = new Date(formData.end_date);
      const startDate = new Date(formData.start_date);
      
      if (formData.start_date && endDate <= startDate) {
        newErrors.end_date = 'End date must be after start date';
      }
    }
    
    // Notes validation (optional but with length limit)
    if (formData.notes && formData.notes.length > 1000) {
      newErrors.notes = 'Notes must be less than 1000 characters';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    setMessage('');
    setErrors({});

    try {
      await api.createCampaign(formData);
      setMessage('Campaign created successfully!');
      setFormData({
        advertiser_id: 0,
        name: '',
        start_date: '',
        end_date: '',
        notes: '',
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setMessage(`Error: ${errorMessage}`);
      
      // Handle specific validation errors from the API
      if (errorMessage.includes('already exists') || errorMessage.includes('duplicate')) {
        setErrors({ name: 'A campaign with this name already exists for this advertiser' });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create Campaign</CardTitle>
        <CardDescription>
          Add a new campaign for an advertiser
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="advertiser" className="block text-sm font-medium text-gray-700">
              Advertiser *
            </label>
            <select
              id="advertiser"
              value={formData.advertiser_id}
              onChange={(e) => {
                setFormData({ ...formData, advertiser_id: parseInt(e.target.value) });
                if (errors.advertiser_id) {
                  setErrors({ ...errors, advertiser_id: undefined });
                }
              }}
              required
              className={`mt-1 block w-full rounded-md border px-3 py-2 focus:outline-none focus:ring-1 ${
                errors.advertiser_id 
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500' 
                  : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
              }`}
            >
              <option value={0}>Select an advertiser</option>
              {advertisers.map((advertiser) => (
                <option key={advertiser.advertiser_id} value={advertiser.advertiser_id}>
                  {advertiser.name} {advertiser.category && `(${advertiser.category})`}
                </option>
              ))}
            </select>
            {errors.advertiser_id && (
              <p className="mt-1 text-sm text-red-600">{errors.advertiser_id}</p>
            )}
          </div>

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700">
              Campaign Name *
            </label>
            <Input
              id="name"
              type="text"
              value={formData.name}
              onChange={(e) => {
                setFormData({ ...formData, name: e.target.value });
                if (errors.name) {
                  setErrors({ ...errors, name: undefined });
                }
              }}
              required
              className={`mt-1 ${errors.name ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}`}
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-600">{errors.name}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="start_date" className="block text-sm font-medium text-gray-700">
                Start Date *
              </label>
              <Input
                id="start_date"
                type="date"
                value={formData.start_date}
                onChange={(e) => {
                  setFormData({ ...formData, start_date: e.target.value });
                  if (errors.start_date) {
                    setErrors({ ...errors, start_date: undefined });
                  }
                }}
                required
                className={`mt-1 ${errors.start_date ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}`}
              />
              {errors.start_date && (
                <p className="mt-1 text-sm text-red-600">{errors.start_date}</p>
              )}
            </div>

            <div>
              <label htmlFor="end_date" className="block text-sm font-medium text-gray-700">
                End Date *
              </label>
              <Input
                id="end_date"
                type="date"
                value={formData.end_date}
                onChange={(e) => {
                  setFormData({ ...formData, end_date: e.target.value });
                  if (errors.end_date) {
                    setErrors({ ...errors, end_date: undefined });
                  }
                }}
                required
                className={`mt-1 ${errors.end_date ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}`}
              />
              {errors.end_date && (
                <p className="mt-1 text-sm text-red-600">{errors.end_date}</p>
              )}
            </div>
          </div>

          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700">
              Notes
            </label>
            <textarea
              id="notes"
              value={formData.notes}
              onChange={(e) => {
                setFormData({ ...formData, notes: e.target.value });
                if (errors.notes) {
                  setErrors({ ...errors, notes: undefined });
                }
              }}
              rows={3}
              className={`mt-1 block w-full rounded-md border px-3 py-2 focus:outline-none focus:ring-1 ${
                errors.notes 
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500' 
                  : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
              }`}
            />
            {errors.notes && (
              <p className="mt-1 text-sm text-red-600">{errors.notes}</p>
            )}
          </div>

          <Button type="submit" disabled={loading}>
            {loading ? 'Creating...' : 'Create Campaign'}
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
