import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import type { BenchmarkResult } from '../types';
import './InterventionMixChart.css';

interface InterventionMixChartProps {
  data: BenchmarkResult | null;
  loading: boolean;
}

// Color palette - muted but distinct
const COLORS = {
  no_action: '#5856d6',      // Purple - distinguished
  payment_retry: '#0071e3',    // Blue
  payment_reminder: '#34c759', // Green
  renewal_reminder: '#ff9500', // Orange
  personalized_offer: '#af52de', // Purple light
  discount: '#ff3b30',         // Red
  default: '#86868b',          // Gray
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

interface ChartData {
  name: string;
  label: string;
  value: number;
  percentage: number;
  color: string;
}

export function InterventionMixChart({ data, loading }: InterventionMixChartProps) {
  if (loading || !data) {
    return (
      <div className="chart-container chart-loading">
        <div className="chart-skeleton-circle" />
      </div>
    );
  }

  const breakdown = data.intervention_breakdown;
  const total = data.total_decisions;

  const chartData: ChartData[] = Object.entries(breakdown)
    .map(([type, stats]) => ({
      name: type,
      label: INTERVENTION_LABELS[type] || type,
      value: stats.decisions,
      percentage: stats.decisions / total,
      color: COLORS[type as keyof typeof COLORS] || COLORS.default,
    }))
    .sort((a, b) => b.value - a.value); // Sort by value descending

  return (
    <div className="chart-container animate-slide-up stagger-2">
      <div className="chart-header">
        <h3 className="chart-title">Intervention Mix</h3>
        <p className="chart-description">REVEN's decision distribution</p>
      </div>

      <div className="chart-body">
        <div className="pie-container">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.color}
                    opacity={0.9}
                  />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.[0]) return null;
                  const item = payload[0].payload as ChartData;
                  return (
                    <div className="chart-tooltip">
                      <div className="tooltip-label">{item.label}</div>
                      <div className="tooltip-value">
                        {item.value.toLocaleString()} decisions
                      </div>
                      <div className="tooltip-percentage">
                        {(item.percentage * 100).toFixed(1)}%
                      </div>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Center label */}
          <div className="pie-center">
            <span className="pie-center-value">{total.toLocaleString()}</span>
            <span className="pie-center-label">Decisions</span>
          </div>
        </div>

        <div className="legend">
          {chartData.map((item) => (
            <div
              key={item.name}
              className={`legend-item ${item.name === 'no_action' ? 'legend-item--no-action' : ''}`}
            >
              <span
                className="legend-dot"
                style={{ background: item.color }}
              />
              <span className="legend-label">{item.label}</span>
              <span className="legend-value">
                {item.value.toLocaleString()}
              </span>
              <span className="legend-percentage">
                {(item.percentage * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
