import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Standards from '../../../src/pages/Standards';

vi.mock('../../../src/api/client', () => ({
  incidentsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  rtasApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  complaintsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  actionsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  auditsApi: { listRuns: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  risksApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  policiesApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  documentsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  investigationsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  notificationsApi: { getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }), list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  executiveDashboardApi: { getDashboard: vi.fn().mockResolvedValue({ data: { risks: { total_active: 0, high_critical: 0 }, near_misses: { trend_percent: 0 }, compliance: { completion_rate: 0 }, kris: { at_risk: 0 } } }) },
  standardsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }), getComplianceScore: vi.fn().mockResolvedValue({ data: { compliance_percentage: 0 } }), get: vi.fn().mockResolvedValue({ data: { clauses: [] } }), getControls: vi.fn().mockResolvedValue({ data: [] }) },
  complianceApi: { linkEvidence: vi.fn().mockResolvedValue({ data: {} }) },
  workflowApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  usersApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  nearMissApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  analyticsApi: { getDashboard: vi.fn().mockResolvedValue({ data: {} }) },
  getApiErrorMessage: vi.fn((err: unknown) => String(err)),
  default: { get: vi.fn().mockResolvedValue({ data: {} }), post: vi.fn().mockResolvedValue({ data: {} }) },
}));

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/stores/useAppStore', () => ({
  useAppStore: { getState: () => ({ setLoading: vi.fn(), setConnectionStatus: vi.fn() }) },
}));

vi.mock('../../../src/utils/auth', () => ({
  getPlatformToken: vi.fn(() => null),
  isTokenExpired: vi.fn(() => false),
  clearTokens: vi.fn(),
}));

describe('Standards', () => {
  it('renders without crashing', async () => {
    render(
      <MemoryRouter>
        <Standards />
      </MemoryRouter>
    );

    const heading = await screen.findByText('Standards & Compliance');
    expect(heading).toBeTruthy();
  });
});
