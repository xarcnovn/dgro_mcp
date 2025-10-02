import Link from 'next/link';
import { Case } from '@/lib/types';

interface CaseCardProps {
  case: Case;
}

export function CaseCard({ case: caseData }: CaseCardProps) {
  return (
    <Link href={`/cases/${caseData.id}`}>
      <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow cursor-pointer">
        <div className="flex justify-between items-start mb-4">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">
              {caseData.subject}
            </h3>
            <p className="text-sm text-gray-600">Case #{caseData.id}</p>
          </div>
          <div className="ml-4">
            <span className="px-3 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
              {caseData.location}
            </span>
          </div>
        </div>
        <p className="text-sm text-gray-700 mb-4 line-clamp-2">
          {caseData.features}
        </p>
        <div className="flex justify-between items-center text-xs text-gray-500">
          <span className="flex items-center">
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {caseData.timeline}
          </span>
          <span className="text-primary font-medium">
            ${caseData.budget.toLocaleString()}
          </span>
        </div>
      </div>
    </Link>
  );
}
