import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  incidentsApi: {
    get: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        title: 'Test Incident',
        reference_number: 'INC-001',
        status: 'open',
        severity: 'low',
        description: 'A test incident description',
        incident_type: 'near_miss',
        location: 'Building A',
        reported_date: '2026-01-15T10:00:00Z',
        reported_by: 'John Doe',
        date_occurred: '2026-01-15T09:00:00Z',
      },
    }),
    update: vi.fn(),
  },
  investigationsApi: { create: vi.fn() },
  actionsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    create: vi.fn(),
    update: vi.fn(),
  },
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

import IncidentDetail from '../../../src/pages/IncidentDetail';

describe('IncidentDetail', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/incidents/1']}>
        <Routes>
          <Route path="/incidents/:id" element={<IncidentDetail />} />
        </Routes>
      </MemoryRouter>
    );

  it('renders the incident title', async () => {
    renderPage();
    expect(await screen.findByText('Test Incident')).toBeInTheDocument();
  });

  it('renders the reference number', async () => {
    renderPage();
    await screen.findByText('Test Incident');
    expect(screen.getByText('INC-001')).toBeInTheDocument();
  });

  it('renders the back button with aria label', async () => {
    renderPage();
    await screen.findByText('Test Incident');
    expect(screen.getByLabelText('Back to incidents')).toBeInTheDocument();
  });
});
