import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlanetMark from '../../../src/pages/PlanetMark';

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
  planetMarkApi: {
    getDashboard: vi.fn().mockResolvedValue({ data: { years: [] } }),
    listActions: vi.fn().mockResolvedValue({ data: [] }),
    getScope3: vi.fn().mockResolvedValue({ data: [] }),
    addEmissionSource: vi.fn().mockResolvedValue({ data: {} }),
    createAction: vi.fn().mockResolvedValue({ data: {} }),
  },
  ErrorClass: { NETWORK_ERROR: 'NETWORK_ERROR', SERVER_ERROR: 'SERVER_ERROR', AUTH_ERROR: 'AUTH_ERROR', NOT_FOUND: 'NOT_FOUND', UNKNOWN: 'UNKNOWN' },
  createApiError: vi.fn(() => ({ error_class: 'UNKNOWN', message: 'Error' })),
  isSetupRequired: vi.fn(() => false),
  getApiErrorMessage: vi.fn(() => 'Error'),
  default: { get: vi.fn().mockResolvedValue({ data: {} }), post: vi.fn().mockResolvedValue({ data: {} }) },
}));

vi.mock('../../../src/components/ui/SetupRequiredPanel', () => ({
  SetupRequiredPanel: () => <div>Setup Required</div>,
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

describe('PlanetMark', () => {
  it('renders without crashing', async () => {
    render(
      <MemoryRouter>
        <PlanetMark />
      </MemoryRouter>
    );

    const heading = await screen.findByText('Planet Mark Carbon');
    expect(heading).toBeTruthy();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <PlanetMark />
      </MemoryRouter>
    );

    const subtitle = await screen.findByText(/Net-Zero Journey/);
    expect(subtitle).toBeTruthy();
  });

  it('renders the Add Emission button', async () => {
    render(
      <MemoryRouter>
        <PlanetMark />
      </MemoryRouter>
    );

    const btn = await screen.findByText('Add Emission');
    expect(btn).toBeTruthy();
  });
});
