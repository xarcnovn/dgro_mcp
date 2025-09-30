// TypeScript interfaces matching DB schema

export interface Case {
  id: number;
  user_id: number;
  status: 'new' | 'in_progress' | 'vendor_search' | 'negotiation' | 'completed';
  category: string;
  details: string;
  urgency: 'low' | 'medium' | 'high';
  budget_range?: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: number;
  name: string;
  email: string;
  company: string;
  phone?: string;
}

export interface Search {
  id: number;
  case_id: number;
  query: string;
  timestamp: string;
  results_json: string;
}

export interface Offer {
  id: number;
  case_id: number;
  vendor_email: string;
  price_quoted?: number;
  details: string;
  status: 'pending' | 'accepted' | 'rejected';
  received_at: string;
}

export interface EmailCommunication {
  id: number;
  case_id: number;
  vendor_email: string;
  subject: string;
  body: string;
  direction: 'sent' | 'received';
  timestamp: string;
  thread_id?: string;
}
