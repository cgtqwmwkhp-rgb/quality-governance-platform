import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AuditTrail from '../../../src/pages/AuditTrail';

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
  standardsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  workflowApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  usersApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  nearMissApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  analyticsApi: { getDashboard: vi.fn().mockResolvedValue({ data: {} }), getTrend: vi.fn().mockResolvedValue({ data: {} }) },
  auditTrailApi: { list: vi.fn().mockResolvedValue({ data: { items: [] } }), exportLog: vi.fn().mockResolvedValue({ data: {} }) },
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

describe('AuditTrail', () => {
  it('renders without crashing', async () => {
    render(
      <MemoryRouter>
        <AuditTrail />
      </MemoryRouter>
    );

    const heading = await screen.findByText('Audit Trail');
    expect(heading).toBeTruthy();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <AuditTrail />
      </MemoryRouter>
    );

    const subtitle = await screen.findByText('Complete history of system activities');
    expect(subtitle).toBeTruthy();
  });

  it('renders the Export Log button', async () => {
    render(
      <MemoryRouter>
        <AuditTrail />
      </MemoryRouter>
    );

    const btn = await screen.findByText('Export Log');
    expect(btn).toBeTruthy();
  });
});
