import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from '../../../src/pages/Dashboard';

vi.mock('../../../src/api/client', () => {
  const emptyPaginated = { data: { items: [], total: 0, page: 1, size: 10, pages: 0 } };
  return {
    incidentsApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    rtasApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    complaintsApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    actionsApi: { list: vi.fn().mockResolvedValue(emptyPaginated) },
    auditsApi: { listRuns: vi.fn().mockResolvedValue(emptyPaginated) },
    notificationsApi: {
      getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
    },
    executiveDashboardApi: {
      getDashboard: vi.fn().mockResolvedValue({
        data: {
          risks: { total_active: 0, high_critical: 0 },
          near_misses: { trend_percent: 0 },
          compliance: { completion_rate: 0 },
          kris: { at_risk: 0 },
        },
      }),
    },
  };
});

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

describe('Dashboard', () => {
  it('renders without crashing', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const heading = await screen.findByText('Dashboard');
    expect(heading).toBeTruthy();
  });

  it('shows the subtitle text', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const subtitle = await screen.findByText('Quality Governance Platform Overview');
    expect(subtitle).toBeTruthy();
  });

  it('renders the Refresh button', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const refreshBtn = await screen.findByText('Refresh');
    expect(refreshBtn).toBeTruthy();
  });

  it('renders stat cards after loading', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const openIncidents = await screen.findByText('Open Incidents');
    expect(openIncidents).toBeTruthy();

    expect(screen.getByText('Open RTAs')).toBeTruthy();
    expect(screen.getByText('Open Complaints')).toBeTruthy();
    expect(screen.getByText('Overdue Actions')).toBeTruthy();
  });

  it('renders IMS Compliance section', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const compliance = await screen.findByText('IMS Compliance');
    expect(compliance).toBeTruthy();
  });

  it('renders quick action links', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    const newIncident = await screen.findByText('New Incident');
    expect(newIncident).toBeTruthy();
    expect(screen.getByText('Start Audit')).toBeTruthy();
    expect(screen.getByText('View Analytics')).toBeTruthy();
    expect(screen.getByText('Compliance')).toBeTruthy();
  });
});
