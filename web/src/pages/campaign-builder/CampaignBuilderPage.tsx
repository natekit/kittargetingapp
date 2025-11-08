import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { ChatInterface } from '../../components/ChatInterface';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { api } from '../../api';
import toast from 'react-hot-toast';

export function CampaignBuilderPage() {
  const { user, signOut } = useAuth();
  const [showPlan, setShowPlan] = useState(false);
  const [collectedData, setCollectedData] = useState<Record<string, any> | null>(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [planGenerated, setPlanGenerated] = useState(false);

  const handleReadyForPlan = (data: Record<string, any>) => {
    setCollectedData(data);
    setShowPlan(true);
  };

  const handleGeneratePlan = async () => {
    if (!collectedData) return;

    setGeneratingPlan(true);
    try {
      // Convert collected data to plan request format
      const planRequest: any = {
        budget: parseFloat(collectedData.budget),
        horizon_days: collectedData.horizon_days || 30,
        use_smart_matching: true,
      };

      // Add required fields
      if (collectedData.category) {
        planRequest.category = collectedData.category;
      } else if (collectedData.advertiser_id) {
        planRequest.advertiser_id = collectedData.advertiser_id;
      }

      if (collectedData.cpc) {
        planRequest.cpc = parseFloat(collectedData.cpc);
      } else if (collectedData.insertion_id) {
        planRequest.insertion_id = collectedData.insertion_id;
      }

      // Add optional fields
      if (collectedData.target_cpa) {
        planRequest.target_cpa = parseFloat(collectedData.target_cpa);
      }
      if (collectedData.advertiser_avg_cvr) {
        planRequest.advertiser_avg_cvr = parseFloat(collectedData.advertiser_avg_cvr);
      }
      if (collectedData.target_age_range) {
        planRequest.target_age_range = collectedData.target_age_range;
      }
      if (collectedData.target_gender_skew) {
        planRequest.target_gender_skew = collectedData.target_gender_skew;
      }
      if (collectedData.target_location) {
        planRequest.target_location = collectedData.target_location;
      }
      if (collectedData.target_interests) {
        planRequest.target_interests = collectedData.target_interests;
      }

      const planResponse = await api.createSmartPlan(planRequest);
      
      // Save plan to database and send email
      try {
        const savedPlan = await api.savePlan(planRequest, planResponse);
        
        // Automatically confirm and send email
        try {
          await api.confirmPlan(savedPlan.plan_id);
          setPlanGenerated(true);
          toast.success('Campaign plan submitted successfully!');
        } catch (confirmError) {
          console.error('Error confirming plan:', confirmError);
          // Plan is still saved, just email might not have sent
          setPlanGenerated(true);
          toast.success('Campaign plan saved! Our team will reach out shortly.');
        }
      } catch (error) {
        console.error('Error saving plan:', error);
        toast.error('Failed to save plan. Please try again.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate plan');
    } finally {
      setGeneratingPlan(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Campaign Builder</h1>
            <p className="text-sm text-gray-600">Create your campaign plan with AI assistance</p>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">{user?.email}</span>
            <Button variant="outline" onClick={signOut}>
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!showPlan ? (
          /* Chat Interface */
          <Card className="h-[calc(100vh-200px)]">
            <CardHeader>
              <CardTitle>Let's Build Your Campaign</CardTitle>
              <CardDescription>
                I'll ask you a few questions to understand your campaign goals and create a personalized plan.
              </CardDescription>
            </CardHeader>
            <CardContent className="h-[calc(100%-120px)]">
              <ChatInterface onReadyForPlan={handleReadyForPlan} />
            </CardContent>
          </Card>
        ) : (
          /* Plan Summary and Generation */
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Campaign Summary</CardTitle>
                <CardDescription>Review your campaign details before generating the plan</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-500">Budget</p>
                    <p className="text-lg font-semibold">${collectedData?.budget || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">CPC</p>
                    <p className="text-lg font-semibold">${collectedData?.cpc || 'N/A'}</p>
                  </div>
                  {collectedData?.category && (
                    <div>
                      <p className="text-sm font-medium text-gray-500">Category</p>
                      <p className="text-lg font-semibold">{collectedData.category}</p>
                    </div>
                  )}
                  {collectedData?.target_cpa && (
                    <div>
                      <p className="text-sm font-medium text-gray-500">Target CPA</p>
                      <p className="text-lg font-semibold">${collectedData.target_cpa}</p>
                    </div>
                  )}
                </div>
                <div className="mt-4 flex space-x-4">
                  <Button onClick={handleGeneratePlan} disabled={generatingPlan}>
                    {generatingPlan ? 'Generating Plan...' : 'Generate Campaign Plan'}
                  </Button>
                  <Button variant="outline" onClick={() => setShowPlan(false)}>
                    Go Back
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Thank You Message */}
            {planGenerated && (
              <Card>
                <CardContent className="pt-6">
                  <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
                    <div className="text-green-600 text-4xl mb-4">✓</div>
                    <h3 className="text-2xl font-semibold text-green-900 mb-3">Thank You!</h3>
                    <p className="text-lg text-green-700 mb-2">
                      Someone from the Kit Ads team will be reaching out shortly with next steps for your campaign.
                    </p>
                    <p className="text-sm text-green-600 mt-4">
                      Your campaign plan has been submitted and our team has been notified.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

