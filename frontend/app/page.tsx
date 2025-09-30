import { CasesList } from '@/components/CasesList';
import { getCases } from '@/lib/api-client';

export default async function HomePage() {
  const cases = await getCases();

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Cases</h1>
        <p className="text-gray-600 mt-2">
          Manage and track your vendor search cases
        </p>
      </div>
      <CasesList cases={cases} />
    </div>
  );
}
