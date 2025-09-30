import { notFound } from 'next/navigation';
import Link from 'next/link';
import { CaseDetail } from '@/components/CaseDetail';
import {
  getCase,
  getUserByCase,
  getSearches,
  getOffers,
  getCommunications,
} from '@/lib/api-client';

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const caseId = parseInt(id);

  try {
    const caseData = await getCase(caseId);
    const user = await getUserByCase(caseId);
    const searches = await getSearches(caseId);
    const offers = await getOffers(caseId);
    const communications = await getCommunications(caseId);

    return (
      <div>
        <div className="mb-6">
          <Link
            href="/"
            className="text-primary hover:text-blue-600 flex items-center text-sm font-medium"
          >
            <svg
              className="w-4 h-4 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Cases
          </Link>
        </div>
        <CaseDetail
          caseData={caseData}
          user={user}
          searches={searches}
          offers={offers}
          communications={communications}
        />
      </div>
    );
  } catch (error) {
    notFound();
  }
}
