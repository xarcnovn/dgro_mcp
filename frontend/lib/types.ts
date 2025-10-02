// TypeScript interfaces matching DB schema (aligned with MCP server)

export interface Case {
  id: number;
  subject: string;
  features: string;
  location: string;
  budget: number;
  timeline: string;
  additional_features?: string;
}

export interface User {
  id: number;
  case_id: number;
  name: string;
  email: string;
  phone?: string;
}

export interface Search {
  id: number;
  case_id: number;
  search_goal: string;
  search_query: string;
  search_results: string;
}

export interface Offer {
  offer_id: number;
  case_id: number;
  status: 'pending' | 'active' | 'accepted' | 'rejected' | 'expired';
  price?: number;
  timeline: string;
  accuracy: number;
  additional_details?: string;
  communication_thread_id?: string;
  vendor_email: string;
  created_at: string;
  updated_at: string;
}

export interface EmailCommunication {
  id: number;
  case_id: number;
  vendor_email: string;
  vendor_name?: string;
  vendor_website?: string;
  subject: string;
  message_id?: string;
  thread_id?: string;
  email_type: string;
  email_content: string;
  sent_at: string;
  status?: string;
}
