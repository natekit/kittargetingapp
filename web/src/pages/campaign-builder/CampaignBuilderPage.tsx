import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { ChatInterface } from '../../components/ChatInterface';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { api } from '../../api';
import toast from 'react-hot-toast';
import type { PlanResponse } from '../../types';

export function CampaignBuilderPage() {
  const { user, signOut } = useAuth();
  const [showPlan, setShowPlan] = useState(false);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [collectedData, setCollectedData] = useState<Record<string, any> | null>(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [planId, setPlanId] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);

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
      setPlan(planResponse);
      
      // Save plan to database
      try {
        const savedPlan = await api.savePlan(planRequest, planResponse);
        setPlanId(savedPlan.plan_id);
        toast.success('Campaign plan generated and saved successfully!');
      } catch (error) {
        console.error('Error saving plan:', error);
        toast.error('Plan generated but failed to save. You can still review it.');
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

            {/* Plan Results */}
            {plan && (
              <Card>
                <CardHeader>
                  <CardTitle>Your Campaign Plan</CardTitle>
                  <CardDescription>
                    We've picked {plan.picked_creators.length} creators for your campaign
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-4 gap-4 mb-6">
                    <div className="bg-gray-50 p-4 rounded-md">
                      <div className="text-sm text-gray-500">Total Spend</div>
                      <div className="text-2xl font-bold">${plan.total_spend.toLocaleString()}</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-md">
                      <div className="text-sm text-gray-500">Total Conversions</div>
                      <div className="text-2xl font-bold">{plan.total_conversions.toFixed(0)}</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-md">
                      <div className="text-sm text-gray-500">Blended CPA</div>
                      <div className="text-2xl font-bold">${plan.blended_cpa.toFixed(2)}</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-md">
                      <div className="text-sm text-gray-500">Budget Utilization</div>
                      <div className="text-2xl font-bold">{(plan.budget_utilization * 100).toFixed(1)}%</div>
                    </div>
                  </div>

                  <div className="mt-6">
                    <h3 className="text-lg font-semibold mb-4">Selected Creators</h3>
                    <div className="space-y-2">
                      {plan.picked_creators.slice(0, 10).map((creator) => (
                        <div key={creator.creator_id} className="border rounded-lg p-4">
                          <div className="flex justify-between items-start">
                            <div>
                              <p className="font-medium">{creator.name}</p>
                              <p className="text-sm text-gray-500">Account ID: {creator.acct_id}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-medium">${creator.expected_spend.toFixed(2)}</p>
                              <p className="text-xs text-gray-500">{creator.expected_clicks.toFixed(0)} clicks</p>
                            </div>
                          </div>
                        </div>
                      ))}
                      {plan.picked_creators.length > 10 && (
                        <p className="text-sm text-gray-500 text-center">
                          ... and {plan.picked_creators.length - 10} more creators
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="mt-6">
                    <Button
                      onClick={async () => {
                        if (!planId) {
                          toast.error('Plan ID not found. Please regenerate the plan.');
                          return;
                        }
                        
                        setConfirming(true);
                        try {
                          const result = await api.confirmPlan(planId);
                          toast.success(result.message);
                          // Optionally redirect or show success state
                        } catch (error) {
                          toast.error(error instanceof Error ? error.message : 'Failed to confirm campaign');
                        } finally {
                          setConfirming(false);
                        }
                      }}
                      className="w-full"
                      disabled={confirming || !planId}
                    >
                      {confirming ? 'Confirming...' : 'Confirm Campaign'}
                    </Button>
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

