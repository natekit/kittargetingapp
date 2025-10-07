import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { PerformanceUpload } from './PerformanceUpload';
import { ConversionsUpload } from './ConversionsUpload';

type UploadType = 'performance' | 'conversions';

export function UploadsPage() {
  const [activeTab, setActiveTab] = useState<UploadType>('performance');

  const tabs = [
    { id: 'performance' as const, label: 'Performance Data', description: 'Upload click and performance metrics' },
    { id: 'conversions' as const, label: 'Conversions Data', description: 'Upload conversion tracking data' },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Data Uploads</h1>
        <p className="mt-2 text-gray-600">
          Upload performance and conversion data to populate your database
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload Data</CardTitle>
          <CardDescription>
            Choose the type of data you want to upload
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Tab Navigation */}
          <div className="border-b border-gray-200 mb-6">
            <nav className="-mb-px flex space-x-8">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="mt-6">
            {activeTab === 'performance' && (
              <div>
                <div className="mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Performance Data Upload</h3>
                  <p className="text-sm text-gray-600">
                    Upload CSV files with click and performance metrics. Expected columns: Creator, Clicks, Unique, Flagged, Execution Date, Status
                  </p>
                </div>
                <PerformanceUpload />
              </div>
            )}

            {activeTab === 'conversions' && (
              <div>
                <div className="mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Conversions Data Upload</h3>
                  <p className="text-sm text-gray-600">
                    Upload CSV files with conversion tracking data. Expected columns: Acct Id, Conversions
                  </p>
                </div>
                <ConversionsUpload />
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
