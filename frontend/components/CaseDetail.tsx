import { Case, User, Search, Offer, EmailCommunication } from '@/lib/types';
import { OffersList } from './OffersList';
import { EmailThreads } from './EmailThreads';

interface CaseDetailProps {
  caseData: Case;
  user: User;
  searches: Search[];
  offers: Offer[];
  communications: EmailCommunication[];
}

export function CaseDetail({ caseData, user, searches, offers, communications }: CaseDetailProps) {
  return (
    <div className="space-y-6">
      {/* Case Info Card */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex justify-between items-start mb-4">
          <h1 className="text-2xl font-bold text-gray-900">
            {caseData.subject}
          </h1>
          <span className="px-3 py-1 text-sm font-medium rounded-full bg-blue-100 text-blue-800">
            {caseData.location}
          </span>
        </div>

        <div className="mb-4">
          <span className="text-sm text-gray-500">Case ID</span>
          <p className="text-base font-medium">#{caseData.id}</p>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <span className="text-sm text-gray-500">Budget</span>
            <p className="text-base font-medium text-primary">
              ${caseData.budget.toLocaleString()}
            </p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Timeline</span>
            <p className="text-base font-medium">{caseData.timeline}</p>
          </div>
        </div>

        <div className="mb-4">
          <span className="text-sm text-gray-500">Features & Requirements</span>
          <p className="text-base mt-1">{caseData.features}</p>
        </div>

        {caseData.additional_features && (
          <div>
            <span className="text-sm text-gray-500">Additional Features</span>
            <p className="text-base mt-1">{caseData.additional_features}</p>
          </div>
        )}
      </div>

      {/* User Info Card */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Client Information</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-sm text-gray-500">Name</span>
            <p className="text-base font-medium">{user.name}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Email</span>
            <p className="text-base font-medium">{user.email}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Phone</span>
            <p className="text-base font-medium">{user.phone || 'Not provided'}</p>
          </div>
        </div>
      </div>

      {/* Search History */}
      {searches.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Search History</h2>
          <div className="space-y-3">
            {searches.map((search) => (
              <div key={search.id} className="border-l-4 border-primary pl-4">
                <p className="text-xs text-gray-500 mb-1">{search.search_goal}</p>
                <p className="text-sm font-medium text-gray-900">{search.search_query}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Offers */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Offers</h2>
        <OffersList offers={offers} />
      </div>

      {/* Email Communications */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Email Communications</h2>
        <EmailThreads communications={communications} />
      </div>
    </div>
  );
}
