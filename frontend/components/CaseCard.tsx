import Link from 'next/link';
import { Case } from '@/lib/types';

interface CaseCardProps {
  case: Case;
}

const statusColors = {
  new: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
  vendor_search: 'bg-purple-100 text-purple-800',
  negotiation: 'bg-orange-100 text-orange-800',
  completed: 'bg-green-100 text-green-800',
};

const urgencyIndicators = {
  low: 'bg-gray-400',
  medium: 'bg-warning',
  high: 'bg-danger',
};

export function CaseCard({ case: caseData }: CaseCardProps) {
  return (
    <Link href={`/cases/${caseData.id}`}>
      <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow cursor-pointer">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-1">
              Case #{caseData.id}
            </h3>
            <p className="text-sm text-gray-600">{caseData.category}</p>
          </div>
          <div className="flex items-center space-x-2">
            <div
              className={`w-3 h-3 rounded-full ${urgencyIndicators[caseData.urgency]}`}
              title={`${caseData.urgency} urgency`}
            />
            <span
              className={`px-2 py-1 text-xs font-medium rounded-full ${
                statusColors[caseData.status]
              }`}
            >
              {caseData.status.replace('_', ' ')}
            </span>
          </div>
        </div>
        <p className="text-sm text-gray-700 mb-4 line-clamp-2">
          {caseData.details}
        </p>
        <div className="flex justify-between items-center text-xs text-gray-500">
          <span>
            Created: {new Date(caseData.created_at).toLocaleDateString()}
          </span>
          {caseData.budget_range && (
            <span className="text-primary font-medium">
              {caseData.budget_range}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
