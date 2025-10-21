import { AdvertiserForm } from './AdvertiserForm';
import { CampaignForm } from './CampaignForm';
import { InsertionForm } from './InsertionForm';
import { VectorUpload } from './VectorUpload';

export function AdminPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Admin</h1>
        <p className="mt-2 text-gray-600">
          Manage advertisers, campaigns, and insertions
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <AdvertiserForm />
        <CampaignForm />
        <InsertionForm />
        <VectorUpload />
      </div>
    </div>
  );
}
