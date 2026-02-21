import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ComplaintDetail from '../../../src/pages/ComplaintDetail';

vi.mock('../../../src/api/client', () => ({
  incidentsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  rtasApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  complaintsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }),
    get: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        reference_number: 'CMP-001',
        title: 'Test Complaint',
        description: 'Test description',
        complaint_type: 'service',
        priority: 'medium',
        status: 'received',
        complainant_name: 'John Doe',
        complainant_email: 'john@test.com',
        complainant_phone: '+44123',
        received_date: '2025-01-01T00:00:00Z',
        created_at: '2025-01-01T00:00:00Z',
        resolution_summary: '',
      },
    }),
    update: vi.fn().mockResolvedValue({ data: {} }),
  },
  actionsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }), create: vi.fn().mockResolvedValue({ data: {} }) },
  auditsApi: { listRuns: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  risksApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  policiesApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  documentsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  investigationsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }), createFromRecord: vi.fn().mockResolvedValue({ data: {} }) },
  notificationsApi: { getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }), list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  executiveDashboardApi: { getDashboard: vi.fn().mockResolvedValue({ data: { risks: { total_active: 0, high_critical: 0 }, near_misses: { trend_percent: 0 }, compliance: { completion_rate: 0 }, kris: { at_risk: 0 } } }) },
  standardsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  workflowApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  usersApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }), search: vi.fn().mockResolvedValue({ data: [] }) },
  nearMissApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 10, pages: 0 } }) },
  analyticsApi: { getDashboard: vi.fn().mockResolvedValue({ data: {} }), getTrend: vi.fn().mockResolvedValue({ data: {} }) },
  getApiErrorMessage: vi.fn(() => 'Error'),
  Complaint: {},
  ComplaintUpdate: {},
  Action: {},
  UserSearchResult: {},
  CreateFromRecordError: {},
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

describe('ComplaintDetail', () => {
  it('renders without crashing', async () => {
    render(
      <MemoryRouter initialEntries={['/complaints/1']}>
        <Routes>
          <Route path="/complaints/:id" element={<ComplaintDetail />} />
        </Routes>
      </MemoryRouter>
    );

    const heading = await screen.findByText('Complaint Details');
    expect(heading).toBeTruthy();
  });

  it('renders the complaint title', async () => {
    render(
      <MemoryRouter initialEntries={['/complaints/1']}>
        <Routes>
          <Route path="/complaints/:id" element={<ComplaintDetail />} />
        </Routes>
      </MemoryRouter>
    );

    const title = await screen.findByText('Test Complaint');
    expect(title).toBeTruthy();
  });

  it('renders complainant information section', async () => {
    render(
      <MemoryRouter initialEntries={['/complaints/1']}>
        <Routes>
          <Route path="/complaints/:id" element={<ComplaintDetail />} />
        </Routes>
      </MemoryRouter>
    );

    const section = await screen.findByText('Complainant Information');
    expect(section).toBeTruthy();
  });
});
