import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  rtasApi: {
    get: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        title: 'Test RTA on M1',
        reference_number: 'RTA-2026-0001',
        status: 'reported',
        severity: 'minor_injury',
        description: 'Vehicle collision at junction 12',
        location: 'M1 Junction 12',
        driver_name: 'John Smith',
        company_vehicle_registration: 'AB12 CDE',
        police_attended: true,
        driver_injured: false,
        insurance_notified: false,
        collision_date: '2026-02-20T14:30:00Z',
        reported_date: '2026-02-20T15:00:00Z',
        created_at: '2026-02-20T15:05:00Z',
      },
    }),
    update: vi.fn(),
  },
  investigationsApi: { create: vi.fn(), createFromRecord: vi.fn() },
  actionsApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }), create: vi.fn() },
  getApiErrorMessage: vi.fn(() => 'Error'),
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

vi.mock('../../../src/components/UserEmailSearch', () => ({
  UserEmailSearch: ({ label }: { label: string }) => <div data-testid="user-email-search">{label}</div>,
}));

import RTADetail from '../../../src/pages/RTADetail';

const renderWithRoute = () =>
  render(
    <MemoryRouter initialEntries={['/rtas/1']}>
      <Routes>
        <Route path="/rtas/:id" element={<RTADetail />} />
      </Routes>
    </MemoryRouter>
  );

describe('RTADetail', () => {
  it('renders the RTA title and reference number', async () => {
    renderWithRoute();
    expect(await screen.findByText('Test RTA on M1')).toBeInTheDocument();
    expect(screen.getByText('RTA-2026-0001')).toBeInTheDocument();
  });

  it('renders severity and status badges', async () => {
    renderWithRoute();
    const severityElements = await screen.findAllByText('minor injury');
    expect(severityElements.length).toBeGreaterThanOrEqual(1);
    const statusElements = screen.getAllByText('reported');
    expect(statusElements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Collision Details card with description', async () => {
    renderWithRoute();
    expect(await screen.findByText('Collision Details')).toBeInTheDocument();
    expect(screen.getByText('Vehicle collision at junction 12')).toBeInTheDocument();
  });

  it('renders Vehicle & Driver Information card', async () => {
    renderWithRoute();
    expect(await screen.findByText('Vehicle & Driver Information')).toBeInTheDocument();
    expect(screen.getByText('AB12 CDE')).toBeInTheDocument();
    expect(screen.getByText('John Smith')).toBeInTheDocument();
  });

  it('renders action buttons (Edit, Add Action, Start Investigation)', async () => {
    renderWithRoute();
    expect(await screen.findByText('Edit')).toBeInTheDocument();
    expect(screen.getByText('Add Action')).toBeInTheDocument();
    expect(screen.getByText('Start Investigation')).toBeInTheDocument();
  });

  it('renders Quick Info sidebar and Activity Timeline', async () => {
    renderWithRoute();
    expect(await screen.findByText('Quick Info')).toBeInTheDocument();
    expect(screen.getByText('Activity Timeline')).toBeInTheDocument();
    expect(screen.getByText('RTA Reported')).toBeInTheDocument();
    expect(screen.getByText('Record Created')).toBeInTheDocument();
  });

  it('shows empty actions state', async () => {
    renderWithRoute();
    expect(await screen.findByText('No actions yet')).toBeInTheDocument();
    expect(screen.getByText('Create actions to track follow-up tasks')).toBeInTheDocument();
  });
});
