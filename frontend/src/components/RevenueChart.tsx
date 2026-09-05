import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { BenchmarkResult } from '../types';
import './RevenueChart.css';

interface RevenueChartProps {
  data: BenchmarkResult | null;
  loading: boolean;
}

function formatCurrency(value: number): string {
  if (value >= 100000) {
    return `₹${(value / 100000).toFixed(1)}L`;
  }
  if (value >= 1000) {
    return `₹${(value / 1000).toFixed(0)}K`;
  }
  return `₹${value.toFixed(0)}`;
}

interface ChartData {
  name: string;
  baseline: number;
  reven: number;
  incremental: number;
  fill: string;
}

export function RevenueChart({ data, loading }: RevenueChartProps) {
  if (loading || !data) {
    return (
      <div className="chart-container chart-loading">
        <div className="chart-skeleton" />
      </div>
    );
  }

  const chartData: ChartData[] = [
    {
      name: 'Baseline',
      baseline: data.baseline.revenue,
      reven: data.baseline.revenue,
      incremental: 0,
      fill: '#e5e5ea',
    },
    {
      name: 'REVEN',
      baseline: data.baseline.revenue,
      reven: data.reven.net_revenue,
      incremental: data.reven.net_revenue - data.baseline.revenue,
      fill: '#0071e3',
    },
  ];

  return (
    <div className="chart-container animate-slide-up stagger-1">
      <div className="chart-header">
        <h3 className="chart-title">Revenue Impact</h3>
        <p className="chart-description">Legacy vs REVEN net revenue comparison</p>
      </div>

      <div className="chart-body">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={chartData}
            margin={{ top: 20, right: 20, left: 20, bottom: 20 }}
            barCategoryGap="30%"
          >
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#86868b', fontSize: 13, fontWeight: 500 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#86868b', fontSize: 12 }}
              tickFormatter={formatCurrency}
              width={60}
            />
            <Tooltip
              cursor={{ fill: 'rgba(0, 0, 0, 0.04)' }}
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const item = payload[0].payload as ChartData;
                return (
                  <div className="chart-tooltip">
                    <div className="tooltip-label">{item.name}</div>
                    <div className="tooltip-value">
                      <span className="tooltip-currency">₹</span>
                      {Math.round(item.reven).toLocaleString('en-IN')}
                    </div>
                    {item.incremental > 0 && (
                      <div className="tooltip-incremental">
                        +₹{Math.round(item.incremental).toLocaleString('en-IN')} incremental
                      </div>
                    )}
                  </div>
                );
              }}
            />
            <Bar dataKey="reven" radius={[6, 6, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-footer">
        <div className="chart-stat">
          <span className="stat-value">
            ₹{Math.round(data.reven.intervention_cost).toLocaleString('en-IN')}
          </span>
          <span className="stat-label">Intervention Cost</span>
        </div>
        <div className="chart-stat chart-stat--highlight">
          <span className="stat-value">
            ₹{Math.round(data.incremental_lift.net_revenue).toLocaleString('en-IN')}
          </span>
          <span className="stat-label">Net Lift</span>
        </div>
      </div>
    </div>
  );
}
