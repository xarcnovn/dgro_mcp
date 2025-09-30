const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export async function getCases(status?: string) {
  const url = status ? `${API_BASE_URL}/api/cases?status=${status}` : `${API_BASE_URL}/api/cases`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch cases');
  return res.json();
}

export async function getCase(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}`);
  if (!res.ok) throw new Error('Failed to fetch case');
  return res.json();
}

export async function getSearches(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/searches`);
  if (!res.ok) throw new Error('Failed to fetch searches');
  return res.json();
}

export async function getOffers(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/offers`);
  if (!res.ok) throw new Error('Failed to fetch offers');
  return res.json();
}

export async function getCommunications(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/communications`);
  if (!res.ok) throw new Error('Failed to fetch communications');
  return res.json();
}

export async function getUserByCase(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/users/${caseId}`);
  if (!res.ok) throw new Error('Failed to fetch user');
  return res.json();
}
