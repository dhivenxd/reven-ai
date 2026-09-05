// REVEN API Types

export type InterventionType =
  | 'payment_retry'
  | 'payment_reminder'
  | 'renewal_reminder'
  | 'personalized_offer'
  | 'discount'
  | 'plan_change'
  | 'cancellation_save'
  | 'no_action';

export type ExecutionStatus =
  | 'pending'
  | 'executed'
  | 'captured'
  | 'failed';

export interface Alternative {
  intervention_type: InterventionType;
  success_probability: number;
  baseline_probability: number;
  gross_revenue_if_success: number;
  baseline_expected_revenue: number;
  expected_revenue: number;
  incremental_lift: number;
  incremental_revenue: number;
  intervention_cost: number;
  offer_cost: number;
  expected_net_revenue: number;
}

export interface Decision {
  decision_id: string;
  customer_id: string;
  intervention_type: InterventionType;
  expected_net_revenue: number;
  confidence: number;
  reason: string;
  alternatives: Alternative[];
  execution_status: ExecutionStatus;
  razorpay_payment_link_id?: string;
  razorpay_result_id?: string;
  captured_amount?: number;
  recovered_at?: string;
  executed_at?: string;
  execution_error?: string;
  created_at: string;
}

export interface DecisionsResponse {
  decisions: Decision[];
  total: number;
  limit: number;
  offset: number;
  count: number;
  timestamp: string;
}

export interface InterventionBreakdown {
  decisions: number;
  successes: number;
  failures: number;
  success_rate: number;
  revenue: number;
  cost: number;
  incremental_revenue: number;
}

export interface PolicyOverview {
  intervention_distribution: Record<string, number>;
  no_action_percentage: number;
  no_action_count: number;
  intervention_rate: number;
  total_decisions: number;
  captured_decisions: number;
  revenue_preserved: number;
  revenue_recovered: number;
  timestamp: string;
}

export interface BenchmarkResult {
  total_customers: number;
  total_decisions: number;
  interventions: number;
  no_action: number;
  intervention_rate: number;
  no_action_rate: number;
  baseline: {
    renewals: number;
    revenue: number;
    renewal_rate: number;
  };
  reven: {
    renewals: number;
    revenue: number;
    renewal_rate: number;
    net_revenue: number;
    intervention_cost: number;
    incremental_net_revenue: number;
    roi: number;
  };
  incremental_lift: {
    renewals: number;
    renewal_rate_delta: number;
    net_revenue: number;
  };
  intervention_breakdown: Record<string, InterventionBreakdown>;
  timestamp: string;
}

export interface Summary {
  total_decisions: number;
  total_customers: number;
  intervention_count: number;
  intervention_rate: number;
  no_action_count: number;
  no_action_percentage: number;
  executed_decisions: number;
  captured_decisions: number;
  pending_decisions: number;
  failed_executions: number;
  revenue_preserved: number;
  revenue_recovered: number;
  intervention_breakdown: Record<string, number>;
  include_pending: boolean;
  timestamp: string;
}
