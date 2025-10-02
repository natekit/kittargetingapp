import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';

interface FormErrors {
  name?: string;
  category?: string;
}

export function AdvertiserForm() {
  const [formData, setFormData] = useState({
    name: '',
    category: '',
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    
    // Name validation
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    } else if (formData.name.trim().length < 2) {
      newErrors.name = 'Name must be at least 2 characters';
    } else if (formData.name.trim().length > 255) {
      newErrors.name = 'Name must be less than 255 characters';
    }
    
    // Category validation
    if (!formData.category.trim()) {
      newErrors.category = 'Category is required';
    } else if (formData.category.trim().length < 2) {
      newErrors.category = 'Category must be at least 2 characters';
    } else if (formData.category.trim().length > 100) {
      newErrors.category = 'Category must be less than 100 characters';
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
      await api.createAdvertiser(formData);
      setMessage('Advertiser created successfully!');
      setFormData({ name: '', category: '' });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setMessage(`Error: ${errorMessage}`);
      
      // Handle specific validation errors from the API
      if (errorMessage.includes('already exists') || errorMessage.includes('duplicate')) {
        setErrors({ name: 'An advertiser with this name already exists' });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create Advertiser</CardTitle>
        <CardDescription>
          Add a new advertiser to the system
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700">
              Name *
            </label>
            <Input
              id="name"
              type="text"
              value={formData.name}
              onChange={(e) => {
                setFormData({ ...formData, name: e.target.value });
                // Clear error when user starts typing
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

          <div>
            <label htmlFor="category" className="block text-sm font-medium text-gray-700">
              Category *
            </label>
            <Input
              id="category"
              type="text"
              value={formData.category}
              onChange={(e) => {
                setFormData({ ...formData, category: e.target.value });
                // Clear error when user starts typing
                if (errors.category) {
                  setErrors({ ...errors, category: undefined });
                }
              }}
              required
              className={`mt-1 ${errors.category ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}`}
            />
            {errors.category && (
              <p className="mt-1 text-sm text-red-600">{errors.category}</p>
            )}
          </div>

          <Button type="submit" disabled={loading}>
            {loading ? 'Creating...' : 'Create Advertiser'}
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
