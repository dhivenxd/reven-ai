# REVEN Frontend

Revenue Recovery Intelligence Dashboard

## Quick Start

### 1. Start Backend

```bash
cd /c/Users/dhiven_xd/revenaiii/reven-ai
python -m backend.llm.api.server
```

Backend runs on: http://localhost:8080

### 2. Start Frontend

```bash
cd /c/Users/dhiven_xd/revenaiii/reven-ai/frontend
npm run dev
```

Frontend runs on: http://localhost:3000

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /agent/benchmark` | Run benchmark comparison (Legacy vs REVEN) |
| `GET /agent/summary` | Executive dashboard summary |
| `GET /agent/decisions` | Recent decisions list |
| `GET /agent/decisions/{id}` | Decision detail |
| `GET /agent/policy/overview` | Policy intelligence overview |
| `POST /agent/demo/seed` | Seed demo data |

## Design System

### Colors

- **Background Primary**: `#fafafa`
- **Background Secondary**: `#f5f5f7`
- **Text Primary**: `#1d1d1f`
- **Text Secondary**: `#86868b`
- **Accent**: `#0071e3`
- **No Action (distinguished)**: `#5856d6`
- **Success**: `#34c759`
- **Warning**: `#ff9500`
- **Error**: `#ff3b30`

### Typography

- **Font**: Inter (Google Fonts)
- **Mono Font**: JetBrains Mono
- **Hierarchy**: 56px hero → 40px → 32px → 24px → 20px → 17px → 15px → 13px → 11px

### Spacing

Base unit: 4px. Common values: 8, 12, 16, 20, 24, 32, 40, 48, 64, 80px

### Border Radius

- Small: 6px
- Medium: 10px
- Large: 14px
- Extra Large: 20px

## Components

- `Header` - Minimal Apple-like header with branding
- `HeroMetric` - Animated incremental revenue display
- `RevenueChart` - Bar chart comparing Legacy vs REVEN
- `InterventionMixChart` - Pie chart showing decision distribution
- `DecisionPath` - Visual flow showing REVEN decision logic
- `RecentDecisions` - Clean list of recent decisions

## Architecture

```
src/
├── api/
│   └── client.ts       # API client
├── components/
│   ├── Header.tsx      # Header component
│   ├── HeroMetric.tsx   # Hero metric with animation
│   ├── RevenueChart.tsx # Revenue comparison chart
│   ├── InterventionMixChart.tsx  # Intervention distribution
│   ├── DecisionPath.tsx # Decision flow visualization
│   └── RecentDecisions.tsx      # Recent decisions list
├── pages/
│   └── Overview.tsx     # Main dashboard page
├── styles/
│   └── globals.css      # Global styles & CSS variables
└── types/
    └── index.ts         # TypeScript types
```

## Key Design Principles

1. **Quiet interface. Loud intelligence.** - Subtle UI, impressive data visualization
2. **No Action is first-class** - Distinguished visually to show it's an intelligent outcome
3. **Apple-inspired** - Clean, premium, generous whitespace
4. **Dribbble-inspired charts** - Rich, analytical, sophisticated

## TODO

- [ ] Decision Explorer page
- [ ] Policy Intelligence page
- [ ] Ask REVEN chat experience
- [ ] Customer detail view
- [ ] Advanced audit views
- [ ] Loading states for individual components
- [ ] Error boundaries
- [ ] Responsive refinements
