import { Case, User, Search, Offer, EmailCommunication } from './types';

export const mockCases: Case[] = [
  {
    id: 1,
    user_id: 1,
    status: 'in_progress',
    category: 'Office Equipment',
    details: 'Need 20 ergonomic office chairs for new office space',
    urgency: 'high',
    budget_range: '$5000-$8000',
    created_at: '2025-09-28T10:00:00Z',
    updated_at: '2025-09-28T14:30:00Z',
  },
  {
    id: 2,
    user_id: 1,
    status: 'vendor_search',
    category: 'IT Services',
    details: 'Cloud migration consulting for 50-person company',
    urgency: 'medium',
    budget_range: '$20000-$40000',
    created_at: '2025-09-27T09:15:00Z',
    updated_at: '2025-09-28T11:00:00Z',
  },
  {
    id: 3,
    user_id: 2,
    status: 'negotiation',
    category: 'Marketing',
    details: 'Website redesign and SEO optimization',
    urgency: 'medium',
    budget_range: '$10000-$15000',
    created_at: '2025-09-25T14:20:00Z',
    updated_at: '2025-09-29T16:45:00Z',
  },
  {
    id: 4,
    user_id: 1,
    status: 'completed',
    category: 'Legal Services',
    details: 'Contract review for partnership agreement',
    urgency: 'high',
    budget_range: '$3000-$5000',
    created_at: '2025-09-20T08:00:00Z',
    updated_at: '2025-09-25T17:00:00Z',
  },
  {
    id: 5,
    user_id: 2,
    status: 'new',
    category: 'Facility Management',
    details: 'Monthly office cleaning service',
    urgency: 'low',
    budget_range: '$500-$1000',
    created_at: '2025-09-29T13:30:00Z',
    updated_at: '2025-09-29T13:30:00Z',
  },
];

export const mockUsers: Record<number, User> = {
  1: {
    id: 1,
    name: 'John Smith',
    email: 'john.smith@acmecorp.com',
    company: 'Acme Corporation',
    phone: '+1-555-0123',
  },
  2: {
    id: 2,
    name: 'Jane Doe',
    email: 'jane.doe@techstart.com',
    company: 'TechStart Inc',
    phone: '+1-555-0456',
  },
};

export const mockSearches: Record<number, Search[]> = {
  1: [
    {
      id: 1,
      case_id: 1,
      query: 'ergonomic office chairs bulk purchase',
      timestamp: '2025-09-28T10:15:00Z',
      results_json: JSON.stringify([
        { title: 'Office Furniture Plus', url: 'https://example.com/1' },
        { title: 'Ergo Chairs Direct', url: 'https://example.com/2' },
      ]),
    },
    {
      id: 2,
      case_id: 1,
      query: 'ergonomic chair suppliers corporate discount',
      timestamp: '2025-09-28T11:30:00Z',
      results_json: JSON.stringify([
        { title: 'Corporate Seating Solutions', url: 'https://example.com/3' },
      ]),
    },
  ],
  2: [
    {
      id: 3,
      case_id: 2,
      query: 'cloud migration consulting services',
      timestamp: '2025-09-27T09:30:00Z',
      results_json: JSON.stringify([
        { title: 'Cloud Experts Inc', url: 'https://example.com/4' },
        { title: 'Migration Masters', url: 'https://example.com/5' },
      ]),
    },
  ],
};

export const mockOffers: Record<number, Offer[]> = {
  1: [
    {
      id: 1,
      case_id: 1,
      vendor_email: 'sales@officefurnitureplus.com',
      price_quoted: 6500,
      details: '20 Herman Miller Aeron chairs, delivery included',
      status: 'pending',
      received_at: '2025-09-28T15:00:00Z',
    },
    {
      id: 2,
      case_id: 1,
      vendor_email: 'info@ergochairs.com',
      price_quoted: 5800,
      details: '20 Steelcase Leap chairs, assembly included',
      status: 'pending',
      received_at: '2025-09-28T16:30:00Z',
    },
  ],
  3: [
    {
      id: 3,
      case_id: 3,
      vendor_email: 'hello@webdesignpro.com',
      price_quoted: 12000,
      details: 'Full website redesign + 6 months SEO',
      status: 'accepted',
      received_at: '2025-09-29T10:00:00Z',
    },
    {
      id: 4,
      case_id: 3,
      vendor_email: 'contact@digitalagency.com',
      price_quoted: 15000,
      details: 'Premium package with ongoing support',
      status: 'rejected',
      received_at: '2025-09-29T11:30:00Z',
    },
  ],
};

export const mockCommunications: Record<number, EmailCommunication[]> = {
  1: [
    {
      id: 1,
      case_id: 1,
      vendor_email: 'sales@officefurnitureplus.com',
      subject: 'Inquiry about ergonomic office chairs',
      body: 'Hello, we are interested in purchasing 20 ergonomic office chairs...',
      direction: 'sent',
      timestamp: '2025-09-28T14:00:00Z',
      thread_id: 'thread-1',
    },
    {
      id: 2,
      case_id: 1,
      vendor_email: 'sales@officefurnitureplus.com',
      subject: 'Re: Inquiry about ergonomic office chairs',
      body: 'Thank you for your inquiry. We can offer you Herman Miller Aeron chairs...',
      direction: 'received',
      timestamp: '2025-09-28T15:00:00Z',
      thread_id: 'thread-1',
    },
    {
      id: 3,
      case_id: 1,
      vendor_email: 'info@ergochairs.com',
      subject: 'Request for quote - office chairs',
      body: 'Hi, we need 20 ergonomic chairs for our office...',
      direction: 'sent',
      timestamp: '2025-09-28T15:30:00Z',
      thread_id: 'thread-2',
    },
    {
      id: 4,
      case_id: 1,
      vendor_email: 'info@ergochairs.com',
      subject: 'Re: Request for quote - office chairs',
      body: 'We have Steelcase Leap chairs available. Price: $5,800 for 20 units...',
      direction: 'received',
      timestamp: '2025-09-28T16:30:00Z',
      thread_id: 'thread-2',
    },
  ],
  3: [
    {
      id: 5,
      case_id: 3,
      vendor_email: 'hello@webdesignpro.com',
      subject: 'Website redesign inquiry',
      body: 'Looking for a complete website redesign with SEO...',
      direction: 'sent',
      timestamp: '2025-09-29T09:00:00Z',
      thread_id: 'thread-3',
    },
    {
      id: 6,
      case_id: 3,
      vendor_email: 'hello@webdesignpro.com',
      subject: 'Re: Website redesign inquiry',
      body: 'We would love to help! Our package includes modern design and SEO optimization...',
      direction: 'received',
      timestamp: '2025-09-29T10:00:00Z',
      thread_id: 'thread-3',
    },
  ],
};

// Helper functions
export function getCaseById(id: number): Case | undefined {
  return mockCases.find((c) => c.id === id);
}

export function getUserById(userId: number): User | undefined {
  return mockUsers[userId];
}

export function getSearchesByCaseId(caseId: number): Search[] {
  return mockSearches[caseId] || [];
}

export function getOffersByCaseId(caseId: number): Offer[] {
  return mockOffers[caseId] || [];
}

export function getCommunicationsByCaseId(caseId: number): EmailCommunication[] {
  return mockCommunications[caseId] || [];
}
