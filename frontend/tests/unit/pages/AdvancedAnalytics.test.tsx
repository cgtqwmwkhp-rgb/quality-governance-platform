import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getKPIs: vi.fn().mockResolvedValue({
      data: {
        incidents: { total: 10, open: 3, closed: 7, trend: -5, avg_resolution_days: 4 },
        actions: { total: 20, open: 5, overdue: 2, completed_on_time_rate: 85, trend: 3 },
        audits: { total: 8, completed: 6, in_progress: 2, avg_score: 92, trend: 1 },
        risks: { total: 15, high: 2, medium: 5, low: 8, mitigated: 10 },
        compliance: { overall_score: 87, iso_9001: 90, iso_14001: 85, iso_45001: 88 },
        training: { completion_rate: 78, expiring_soon: 3, overdue: 1 },
      },
    }),
    getBenchmarks: vi.fn().mockResolvedValue({
      data: { comparisons: {}, overall_percentile: 0, above_average_count: 0, total_metrics: 0, performance_rating: '' },
    }),
    getNonComplianceCosts: vi.fn().mockResolvedValue({
      data: {
        total_cost: 0,
        breakdown: {
          incident_costs: { amount: 0, count: 0 },
          regulatory_fines: { amount: 0, count: 0 },
          legal_costs: { amount: 0, count: 0 },
          remediation: { amount: 0, count: 0 },
          productivity_loss: { amount: 0 },
        },
        trend: { vs_previous_period: 0, direction: 'stable' },
      },
    }),
    getROI: vi.fn().mockResolvedValue({
      data: {
        investments: [],
        summary: { total_investment: 0, total_annual_savings: 0, total_incidents_prevented: 0, overall_roi: 0 },
      },
    }),
    getTrends: vi.fn().mockResolvedValue({ data: { labels: [], datasets: [], summary: {} } }),
    forecast: vi.fn().mockResolvedValue({ data: {} }),
    getDrillDown: vi.fn().mockResolvedValue({ data: { records: [] } }),
  },
}));

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/stores/useAppStore', () => ({
  useAppStore: {
    getState: () => ({
      setLoading: vi.fn(),
      setConnectionStatus: vi.fn(),
    }),
  },
}));

vi.mock('../../../src/utils/auth', () => ({
  getPlatformToken: vi.fn(() => null),
  isTokenExpired: vi.fn(() => false),
  clearTokens: vi.fn(),
}));

import AdvancedAnalytics from '../../../src/pages/AdvancedAnalytics';

describe('AdvancedAnalytics', () => {
  it('renders the Advanced Analytics heading', async () => {
    render(
      <MemoryRouter>
        <AdvancedAnalytics />
      </MemoryRouter>
    );
    expect(await screen.findByText('Advanced Analytics')).toBeInTheDocument();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <AdvancedAnalytics />
      </MemoryRouter>
    );
    expect(await screen.findByText('Interactive insights with forecasting and benchmarks')).toBeInTheDocument();
  });

  it('renders tab navigation', async () => {
    render(
      <MemoryRouter>
        <AdvancedAnalytics />
      </MemoryRouter>
    );
    await screen.findByText('Advanced Analytics');
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Trends & Forecast')).toBeInTheDocument();
    expect(screen.getByText('Benchmarks')).toBeInTheDocument();
  });

  it('can switch to Benchmarks tab', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AdvancedAnalytics />
      </MemoryRouter>
    );
    await screen.findByText('Advanced Analytics');
    await user.click(screen.getByText('Benchmarks'));
    expect(screen.getByText('Benchmarks')).toBeInTheDocument();
  });
});
