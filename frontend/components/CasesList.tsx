'use client';

import { useState } from 'react';
import { Case } from '@/lib/types';
import { CaseCard } from './CaseCard';

interface CasesListProps {
  cases: Case[];
}

type StatusFilter = 'all' | Case['status'];

export function CasesList({ cases }: CasesListProps) {
  const [filter, setFilter] = useState<StatusFilter>('all');

  const filteredCases = filter === 'all'
    ? cases
    : cases.filter((c) => c.status === filter);

  const tabs: { label: string; value: StatusFilter }[] = [
    { label: 'All', value: 'all' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Vendor Search', value: 'vendor_search' },
    { label: 'Negotiation', value: 'negotiation' },
    { label: 'Completed', value: 'completed' },
  ];

  return (
    <div>
      {/* Filter Tabs */}
      <div className="mb-6 border-b border-gray-200">
        <div className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
              className={`pb-4 px-1 text-sm font-medium border-b-2 transition-colors ${
                filter === tab.value
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Cases Grid */}
      {filteredCases.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">No cases found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCases.map((caseData) => (
            <CaseCard key={caseData.id} case={caseData} />
          ))}
        </div>
      )}
    </div>
  );
}
