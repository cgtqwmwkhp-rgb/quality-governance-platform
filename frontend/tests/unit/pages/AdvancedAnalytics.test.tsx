import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getKPIs: vi.fn().mockResolvedValue({
      data: {
        incidents: { total: 0, open: 0, closed: 0, trend: 0, avg_resolution_days: 0 },
        actions: { total: 0, open: 0, overdue: 0, completed_on_time_rate: 0, trend: 0 },
        audits: { total: 0, completed: 0, in_progress: 0, avg_score: 0, trend: 0 },
        risks: { total: 0, high: 0, medium: 0, low: 0, mitigated: 0 },
        compliance: { overall_score: 0, iso_9001: 0, iso_14001: 0, iso_45001: 0 },
        training: { completion_rate: 0, expiring_soon: 0, overdue: 0 },
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
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <AdvancedAnalytics />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
