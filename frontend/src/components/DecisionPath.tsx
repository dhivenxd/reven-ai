import type { Decision } from '../types';
import './DecisionPath.css';

interface DecisionPathProps {
  decision: Decision | null;
  loading: boolean;
}

const INTERVENTION_LABELS: Record<string, string> = {
  no_action: 'NO ACTION',
  payment_retry: 'PAYMENT RETRY',
  payment_reminder: 'PAYMENT REMINDER',
  renewal_reminder: 'RENEWAL REMINDER',
  personalized_offer: 'PERSONALIZED OFFER',
  discount: 'DISCOUNT',
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value);
}

export function DecisionPath({ decision, loading }: DecisionPathProps) {
  if (loading) {
    return (
      <section className="decision-path">
        <div className="decision-path-header">
          <h3 className="decision-path-title">REVEN Decision Flow</h3>
        </div>
        <div className="decision-path-loading">
          <div className="path-skeleton" />
        </div>
      </section>
    );
  }

  if (!decision) return null;

  const isNoAction = decision.intervention_type === 'no_action';
  const bestAlternative = decision.alternatives?.[0];

  return (
    <section className="decision-path animate-slide-up stagger-3">
      <div className="decision-path-header">
        <h3 className="decision-path-title">Decision Story</h3>
        <p className="decision-path-description">
          Reasoning path for customer {decision.customer_id}
        </p>
      </div>

      <div className="decision-flow">
        <div className="flow-step">
          <div className="step-number">1</div>
          <div className="step-content">
            <span className="step-label">Situation</span>
            <span className="step-value">Payment failure detected for {decision.customer_id}</span>
          </div>
        </div>

        <div className="flow-arrow">
          <svg width="12" height="24" viewBox="0 0 12 24" fill="none">
            <path d="M6 0L6 18M6 18L2 14M6 18L10 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        <div className="flow-step">
          <div className="step-number">2</div>
          <div className="step-content">
            <span className="step-label">Risk Evaluation</span>
            <span className="step-value">{decision.reason.split('.')[0]}</span>
          </div>
        </div>

        <div className="flow-arrow">
          <svg width="12" height="24" viewBox="0 0 12 24" fill="none">
            <path d="M6 0L6 18M6 18L2 14M6 18L10 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        <div className="flow-step">
          <div className="step-number">3</div>
          <div className="step-content">
            <span className="step-label">Economic Evaluation</span>
            <span className="step-value">
              Expected Value: {formatCurrency(decision.expected_net_revenue)}
            </span>
          </div>
        </div>

        <div className="flow-arrow">
          <svg width="12" height="24" viewBox="0 0 12 24" fill="none">
            <path d="M6 0L6 18M6 18L2 14M6 18L10 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        <div className="flow-step">
          <div className="step-number">4</div>
          <div className="step-content">
            <span className="step-label">Policy Gate</span>
            <span className={`step-value ${isNoAction ? 'status-blocked' : 'status-approved'}`}>
              {isNoAction ? 'THRESHOLD NOT MET' : 'THRESHOLD PASSED'}
            </span>
          </div>
        </div>

        <div className="flow-arrow">
          <svg width="12" height="24" viewBox="0 0 12 24" fill="none">
            <path d="M6 0L6 18M6 18L2 14M6 18L10 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        <div className={`flow-decision ${isNoAction ? 'flow-decision--no-action' : ''}`}>
          <div className="decision-badge">
            {INTERVENTION_LABELS[decision.intervention_type] || decision.intervention_type.toUpperCase()}
          </div>

          <div className="decision-reasoning">
            <div className="reasoning-item">
              <span className="reasoning-label">Engine Decision</span>
              <span className="reasoning-value">{decision.reason}</span>
            </div>
            {bestAlternative && (
              <div className="reasoning-item">
                <span className="reasoning-label">Best Alternative</span>
                <span className="reasoning-value">
                  {INTERVENTION_LABELS[bestAlternative.intervention_type] || bestAlternative.intervention_type} ({formatCurrency(bestAlternative.expected_net_revenue)})
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="flow-arrow">
          <svg width="12" height="24" viewBox="0 0 12 24" fill="none">
            <path d="M6 0L6 18M6 18L2 14M6 18L10 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        <div className="flow-step">
          <div className="step-number">5</div>
          <div className="step-content">
            <span className="step-label">Execution Status</span>
            <span className={`step-value state ${decision.execution_status}`}>
              {decision.execution_status.toUpperCase()}
            </span>
          </div>
        </div>

        {decision.execution_status === 'captured' && (
          <>
            <div className="flow-arrow">
              <svg width="12" height="24" viewBox="0 0 12 24" fill="none">
                <path d="M6 0L6 18M6 18L2 14M6 18L10 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="flow-step">
              <div className="step-number">6</div>
              <div className="step-content">
                <span className="step-label">Final Outcome</span>
                <span className="step-value status-approved">
                  REVENUE RECOVERED
                </span>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="decision-insight">
        <div className="insight-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <p className="insight-text">
          {isNoAction
            ? "REVEN identified that the cost of intervention exceeds the expected recovery value. This is a deliberate economic choice to preserve margin."
            : "REVEN identified a high-probability recovery path that exceeds the economic threshold for action."}
        </p>
      </div>
    </section>
  );
}
