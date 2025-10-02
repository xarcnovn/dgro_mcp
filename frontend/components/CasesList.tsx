import { Case } from '@/lib/types';
import { CaseCard } from './CaseCard';

interface CasesListProps {
  cases: Case[];
}

export function CasesList({ cases }: CasesListProps) {
  return (
    <div>
      {/* Cases Grid */}
      {cases.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">No cases found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cases.map((caseData) => (
            <CaseCard key={caseData.id} case={caseData} />
          ))}
        </div>
      )}
    </div>
  );
}
