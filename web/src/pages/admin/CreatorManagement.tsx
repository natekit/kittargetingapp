import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { api } from '../../api';
import { SyncResult } from '../../types';
import { parseCSVFile, validateCSVStructure, getCSVPreview, formatCSVErrors, debugCSVStructure } from '../../lib/csvParser';
import toast from 'react-hot-toast';

export function CreatorManagement() {
  const [file, setFile] = useState<File | null>(null);
  const [csvPreview, setCsvPreview] = useState<string[][]>([]);
  const [csvErrors, setCsvErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setCsvErrors([]);
      
      try {
        // Parse CSV with proper handling
        const parseResult = await parseCSVFile(selectedFile);
        
        // Debug CSV structure first
        const debugInfo = debugCSVStructure(parseResult.data);
        console.log('CSV Debug Info:', debugInfo);
        
        // Validate structure
        const validation = validateCSVStructure(parseResult.data, [
          'name', 'acct_id', 'owner_email', 'topic'
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
          toast.error(`CSV parsing warnings: ${formattedErrors.length} issues found`);
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

  const handleSync = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setResult(null);

    try {
      const data = await api.seedCreators(file);
      setResult(data);
      toast.success(`Creator database synced! ${data.upserted} creators updated, ${data.skipped} skipped.`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      toast.error(`Sync failed: ${errorMessage}`);
      setResult({ upserted: 0, skipped: 0, total_processed: 0, errors: [errorMessage] });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Creator Management</h1>
        <p className="mt-2 text-gray-600">
          Sync your creator database from Notion exports. This will update creator profiles while preserving all performance data.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle>Sync from Notion</CardTitle>
            <CardDescription>
              Upload a CSV export from your Notion creator database
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSync} className="space-y-4">
              <div>
                <label htmlFor="file" className="block text-sm font-medium text-gray-700">
                  Notion CSV Export *
                </label>
                <Input
                  id="file"
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  required
                  className="mt-1"
                />
                <p className="mt-1 text-sm text-gray-500">
                  Expected columns: Name, Acct Id, Owner Email, Topic
                </p>
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

              <Button type="submit" disabled={loading || !file || csvErrors.length > 0}>
                {loading ? 'Syncing...' : 'Sync Creator Database'}
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
            </form>
          </CardContent>
        </Card>

        {/* Instructions */}
        <Card>
          <CardHeader>
            <CardTitle>How to Export from Notion</CardTitle>
            <CardDescription>
              Step-by-step guide to export your creator database
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex items-start">
                <div className="flex-shrink-0 w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-medium text-blue-600">1</span>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-gray-700">
                    In your Notion creator database, click the <strong>three dots</strong> menu
                  </p>
                </div>
              </div>
              
              <div className="flex items-start">
                <div className="flex-shrink-0 w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-medium text-blue-600">2</span>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-gray-700">
                    Select <strong>"Export"</strong> → <strong>"CSV"</strong>
                  </p>
                </div>
              </div>
              
              <div className="flex items-start">
                <div className="flex-shrink-0 w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-medium text-blue-600">3</span>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-gray-700">
                    Upload the downloaded CSV file here
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-yellow-800">Data Safety</h3>
                  <p className="mt-1 text-sm text-yellow-700">
                    This sync will only update creator profiles. All your click and conversion data will be preserved.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Results */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Sync Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-green-50 border border-green-200 rounded-md p-4">
                <div className="text-2xl font-bold text-green-600">{result.upserted}</div>
                <div className="text-sm text-green-700">Creators Updated</div>
              </div>
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                <div className="text-2xl font-bold text-yellow-600">{result.skipped}</div>
                <div className="text-sm text-yellow-700">Rows Skipped</div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                <div className="text-2xl font-bold text-blue-600">{result.total_processed}</div>
                <div className="text-sm text-blue-700">Total Processed</div>
              </div>
            </div>
            
            {result.errors && result.errors.length > 0 && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
                <h4 className="text-sm font-medium text-red-800 mb-2">Errors:</h4>
                <ul className="text-sm text-red-700 list-disc list-inside">
                  {result.errors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
