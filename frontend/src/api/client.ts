// REVEN API Client
// Uses relative URLs that go through Vite dev server proxy to avoid CORS issues

import type { BenchmarkResult, DecisionsResponse, PolicyOverview, Summary, Decision } from '../types';

async function fetchJSON<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(endpoint, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export interface ChatResponse {
  message: string;
  session_id: string;
  tool_calls?: Array<{
    name?: string;
    description?: string;
    result?: unknown;
  }>;
  status: string;
  timestamp: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export const api = {
  // Get benchmark comparison data
  getBenchmark: (customerCount = 1000, seed = 42): Promise<BenchmarkResult> =>
    fetchJSON<BenchmarkResult>(`/agent/benchmark?customer_count=${customerCount}&seed=${seed}`),

  // Get recent decisions
  getDecisions: (limit = 50, offset = 0): Promise<DecisionsResponse> =>
    fetchJSON<DecisionsResponse>(`/agent/decisions?limit=${limit}&offset=${offset}`),

  // Get single decision by ID
  getDecision: (decisionId: string): Promise<Decision> =>
    fetchJSON<Decision>(`/agent/decisions/${decisionId}`),

  // Get customer decisions
  getCustomerDecisions: (customerId: string): Promise<DecisionsResponse> =>
    fetchJSON<DecisionsResponse>(`/agent/customer/${customerId}/decisions`),

  // Get policy overview
  getPolicyOverview: (): Promise<PolicyOverview> =>
    fetchJSON<PolicyOverview>('/agent/policy/overview'),

  // Get summary
  getSummary: (includePending = false): Promise<Summary> =>
    fetchJSON<Summary>(`/agent/summary?include_pending=${includePending}`),

  // Seed demo data
  seedDemo: (): Promise<{ status: string; decision_ids: string[] }> =>
    fetchJSON('/agent/demo/seed', { method: 'POST' }),

  // Simulate a failed payment (Trigger Recovery Flow)
  simulatePaymentFailed: (): Promise<{ status: string; message: string }> =>
    fetchJSON('/agent/demo/simulate/payment-failed', { method: 'POST' }),

  // Simulate a payment capture (Mark Recovery as Success)
  simulatePaymentCaptured: (decisionId: string): Promise<{ status: string; message: string }> =>
    fetchJSON(`/agent/demo/simulate/payment-captured?decision_id=${decisionId}`, { method: 'POST' }),

  // Chat with REVEN agent
  chat: (message: string, sessionId?: string): Promise<ChatResponse> =>

    fetchJSON<ChatResponse>('/agent/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
};

export default api;
