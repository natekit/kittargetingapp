import { useState } from 'react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { api } from '../../api';

interface VectorUploadResult {
  status: string;
  message: string;
  uploaded: number;
  updated: number;
  skipped: number;
  total_processed: number;
  errors: string[];
  total_errors: number;
}

export function VectorUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<VectorUploadResult | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    try {
      const response = await api.uploadVectors(file);
      setResult(response);
    } catch (error) {
      console.error('Vector upload failed:', error);
      setResult({
        status: 'error',
        message: 'Upload failed',
        uploaded: 0,
        updated: 0,
        skipped: 0,
        total_processed: 0,
        errors: [error instanceof Error ? error.message : 'Unknown error'],
        total_errors: 1
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Upload Creator Vectors</h3>
          <p className="text-sm text-gray-600">
            Upload vector embeddings for creator similarity matching. CSV format: account_id, vector_component_1, vector_component_2, ...
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label htmlFor="vector-file" className="block text-sm font-medium text-gray-700">
              Select CSV File
            </label>
            <input
              id="vector-file"
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>

          {file && (
            <div className="text-sm text-gray-600">
              Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </div>
          )}

          <Button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="w-full"
          >
            {uploading ? 'Uploading...' : 'Upload Vectors'}
          </Button>
        </div>

        {result && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-2">Upload Results</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Status:</span>
                <span className={result.status === 'success' ? 'text-green-600' : 'text-red-600'}>
                  {result.status}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Uploaded:</span>
                <span className="text-green-600">{result.uploaded}</span>
              </div>
              <div className="flex justify-between">
                <span>Updated:</span>
                <span className="text-blue-600">{result.updated}</span>
              </div>
              <div className="flex justify-between">
                <span>Skipped:</span>
                <span className="text-yellow-600">{result.skipped}</span>
              </div>
              <div className="flex justify-between">
                <span>Total Processed:</span>
                <span>{result.total_processed}</span>
              </div>
              {result.total_errors > 0 && (
                <div className="flex justify-between">
                  <span>Errors:</span>
                  <span className="text-red-600">{result.total_errors}</span>
                </div>
              )}
            </div>

            {result.errors.length > 0 && (
              <div className="mt-3">
                <h5 className="font-medium text-red-600 mb-1">Errors:</h5>
                <div className="text-xs text-red-600 space-y-1 max-h-32 overflow-y-auto">
                  {result.errors.map((error, index) => (
                    <div key={index}>{error}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
