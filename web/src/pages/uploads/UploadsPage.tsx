import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import PerformanceUploadForm from './PerformanceUploadForm';
import ConversionsUploadForm from './ConversionsUploadForm';
import ManualConversionForm from './ManualConversionForm';

const UploadsPage: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Data Uploads</h1>
      
      <Tabs defaultValue="performance" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="performance">Performance Data</TabsTrigger>
          <TabsTrigger value="conversions">Conversions Data</TabsTrigger>
          <TabsTrigger value="manual">Manual Entry</TabsTrigger>
        </TabsList>
        
        <TabsContent value="performance">
          <PerformanceUploadForm />
        </TabsContent>
        
        <TabsContent value="conversions">
          <ConversionsUploadForm />
        </TabsContent>
        
        <TabsContent value="manual">
          <ManualConversionForm />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default UploadsPage;
