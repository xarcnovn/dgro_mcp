import { Offer } from '@/lib/types';

interface OffersListProps {
  offers: Offer[];
}

const statusColors = {
  pending: 'bg-yellow-100 text-yellow-800',
  accepted: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
};

export function OffersList({ offers }: OffersListProps) {
  if (offers.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No offers yet
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Vendor Email
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Price
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Details
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Received
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {offers.map((offer) => (
            <tr key={offer.id}>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {offer.vendor_email}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {offer.price_quoted ? `$${offer.price_quoted.toLocaleString()}` : 'N/A'}
              </td>
              <td className="px-6 py-4 text-sm text-gray-700">
                {offer.details}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span
                  className={`px-2 py-1 text-xs font-medium rounded-full ${
                    statusColors[offer.status]
                  }`}
                >
                  {offer.status}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {new Date(offer.received_at).toLocaleString()}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                {offer.status === 'pending' && (
                  <div className="flex space-x-2">
                    <button className="text-success hover:text-green-700">
                      Accept
                    </button>
                    <button className="text-danger hover:text-red-700">
                      Reject
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
