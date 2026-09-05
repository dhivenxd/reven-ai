import { useEffect, useState } from 'react';
import type { BenchmarkResult } from '../types';
import './HeroMetric.css';

interface HeroMetricProps {
  data: BenchmarkResult | null;
  loading: boolean;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatRoi(value: number): string {
  return `${value.toFixed(2)}x`;
}

// Animated counter hook
function useAnimatedValue(value: number, duration = 1000): number {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const startValue = 0;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      const current = startValue + (value - startValue) * eased;

      setDisplayValue(current);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [value, duration]);

  return displayValue;
}

export function HeroMetric({ data, loading }: HeroMetricProps) {
  const animatedRevenue = useAnimatedValue(
    data?.reven.incremental_net_revenue || 0,
    1200
  );

  if (loading || !data) {
    return (
      <section className="hero-metric">
        <div className="hero-content">
          <div className="hero-main">
            <div className="hero-skeleton" />
            <div className="hero-subtitle-skeleton" />
          </div>
          <div className="hero-secondary">
            <div className="secondary-metric-skeleton" />
            <div className="secondary-metric-skeleton" />
            <div className="secondary-metric-skeleton" />
          </div>
        </div>
      </section>
    );
  }

  const roi = data.reven.roi;
  const interventionRate = data.intervention_rate;
  const noActionRate = data.no_action_rate;

  return (
    <section className="hero-metric animate-slide-up">
      <div className="hero-content">
        <div className="hero-main">
          <div className="hero-value">
            <span className="hero-currency">₹</span>
            <span className="hero-amount">
              {Math.round(animatedRevenue).toLocaleString('en-IN')}
            </span>
          </div>
          <p className="hero-subtitle">
            Incremental net revenue vs. legacy recovery policy
          </p>
        </div>

        <div className="hero-secondary">
          <div className="secondary-metric">
            <span className="secondary-value">{formatRoi(roi)}</span>
            <span className="secondary-label">ROI</span>
          </div>
          <div className="secondary-divider" />
          <div className="secondary-metric">
            <span className="secondary-value">{formatPercent(interventionRate)}</span>
            <span className="secondary-label">Intervention Rate</span>
          </div>
          <div className="secondary-divider" />
          <div className="secondary-metric secondary-metric--no-action">
            <span className="secondary-value">{formatPercent(noActionRate)}</span>
            <span className="secondary-label">No Action</span>
          </div>
        </div>
      </div>
    </section>
  );
}
