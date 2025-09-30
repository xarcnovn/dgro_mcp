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

const statusColors = {
  new: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
  vendor_search: 'bg-purple-100 text-purple-800',
  negotiation: 'bg-orange-100 text-orange-800',
  completed: 'bg-green-100 text-green-800',
};

const urgencyColors = {
  low: 'text-gray-600',
  medium: 'text-warning',
  high: 'text-danger',
};

export function CaseDetail({ caseData, user, searches, offers, communications }: CaseDetailProps) {
  return (
    <div className="space-y-6">
      {/* Case Info Card */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex justify-between items-start mb-4">
          <h1 className="text-2xl font-bold text-gray-900">
            Case #{caseData.id}
          </h1>
          <span
            className={`px-3 py-1 text-sm font-medium rounded-full ${
              statusColors[caseData.status]
            }`}
          >
            {caseData.status.replace('_', ' ')}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <span className="text-sm text-gray-500">Category</span>
            <p className="text-base font-medium">{caseData.category}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Urgency</span>
            <p className={`text-base font-medium ${urgencyColors[caseData.urgency]}`}>
              {caseData.urgency.toUpperCase()}
            </p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Budget Range</span>
            <p className="text-base font-medium">{caseData.budget_range || 'Not specified'}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Created</span>
            <p className="text-base font-medium">
              {new Date(caseData.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div>
          <span className="text-sm text-gray-500">Details</span>
          <p className="text-base mt-1">{caseData.details}</p>
        </div>
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
            <span className="text-sm text-gray-500">Company</span>
            <p className="text-base font-medium">{user.company}</p>
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
                <p className="text-sm font-medium text-gray-900">{search.query}</p>
                <p className="text-xs text-gray-500">
                  {new Date(search.timestamp).toLocaleString()}
                </p>
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
