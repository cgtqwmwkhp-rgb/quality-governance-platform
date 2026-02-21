import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Audits from '../../../src/pages/Audits';

vi.mock('../../../src/api/client', () => ({
  incidentsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  rtasApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  complaintsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  actionsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  auditsApi: {
    listRuns: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }),
    listFindings: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }),
    listTemplates: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }),
    createRun: vi.fn().mockResolvedValue({ data: { reference_number: 'AUD-001' } }),
  },
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
  analyticsApi: { getDashboard: vi.fn().mockResolvedValue({ data: {} }) },
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

describe('Audits', () => {
  it('renders the Audit Management heading', async () => {
    render(
      <MemoryRouter>
        <Audits />
      </MemoryRouter>
    );
    expect(await screen.findByText('Audit Management')).toBeInTheDocument();
  });

  it('renders the New Audit button', async () => {
    render(
      <MemoryRouter>
        <Audits />
      </MemoryRouter>
    );
    await screen.findByText('Audit Management');
    expect(screen.getByText('New Audit')).toBeInTheDocument();
  });

  it('renders search input', async () => {
    render(
      <MemoryRouter>
        <Audits />
      </MemoryRouter>
    );
    await screen.findByText('Audit Management');
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('opens modal when New Audit is clicked', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Audits />
      </MemoryRouter>
    );
    await screen.findByText('Audit Management');
    await user.click(screen.getByText('New Audit'));
    expect(screen.getByText('Schedule New Audit')).toBeInTheDocument();
  });
});
