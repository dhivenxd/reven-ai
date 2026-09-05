import type { Decision } from '../types';
import './RecentDecisions.css';

interface RecentDecisionsProps {
  decisions: Decision[];
  loading: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#ff9500',
  executed: '#0071e3',
  captured: '#34c759',
  failed: '#ff3b30',
};

const INTERVENTION_LABELS: Record<string, string> = {
  no_action: 'No Action',
  payment_retry: 'Payment Retry',
  payment_reminder: 'Payment Reminder',
  renewal_reminder: 'Renewal Reminder',
  personalized_offer: 'Personalized Offer',
  discount: 'Discount',
  plan_change: 'Plan Change',
  cancellation_save: 'Cancellation Save',
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-IN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function RecentDecisions({ decisions, loading }: RecentDecisionsProps) {
  if (loading) {
    return (
      <section className="recent-decisions">
        <div className="section-header">
          <h3 className="section-title">Recent Decisions</h3>
        </div>
        <div className="decisions-loading">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="decision-skeleton" />
          ))}
        </div>
      </section>
    );
  }

  if (decisions.length === 0) {
    return (
      <section className="recent-decisions">
        <div className="section-header">
          <h3 className="section-title">Recent Decisions</h3>
        </div>
        <div className="decisions-empty">
          <p>No decisions yet. Run the benchmark to generate sample data.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="recent-decisions animate-slide-up stagger-4">
      <div className="section-header">
        <h3 className="section-title">Recent Decisions</h3>
        <span className="section-count">{decisions.length} decisions</span>
      </div>

      <div className="decisions-list">
        {decisions.slice(0, 8).map((decision, index) => (
          <div
            key={decision.decision_id}
            className={`decision-row ${decision.intervention_type === 'no_action' ? 'decision-row--no-action' : ''}`}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="decision-main">
              <div className="decision-customer">
                <span className="customer-id">{decision.customer_id}</span>
              </div>
              <div className="decision-meta">
                <span
                  className="intervention-badge"
                  data-type={decision.intervention_type}
                >
                  {INTERVENTION_LABELS[decision.intervention_type] || decision.intervention_type}
                </span>
                <span className="decision-confidence">
                  {(decision.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>
            </div>

            <div className="decision-value">
              <span className="value-amount">
                {formatCurrency(decision.expected_net_revenue)}
              </span>
              <span className="value-label">Expected</span>
            </div>

            <div className="decision-status">
              <span
                className="status-badge"
                style={{ '--status-color': STATUS_COLORS[decision.execution_status] } as React.CSSProperties}
              >
                {decision.execution_status}
              </span>
            </div>

            <div className="decision-time">
              {formatDate(decision.created_at)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
