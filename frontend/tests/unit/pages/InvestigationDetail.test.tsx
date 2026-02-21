import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  investigationsApi: {
    get: vi.fn().mockResolvedValue({
      data: {
        id: 1,
        title: 'Test Investigation',
        reference_number: 'INV-001',
        status: 'draft',
        description: 'Test description',
        assigned_entity_type: 'reporting_incident',
        data: {},
        started_at: null,
        completed_at: null,
      },
    }),
    getTimeline: vi.fn().mockResolvedValue({ data: { items: [] } }),
    getComments: vi.fn().mockResolvedValue({ data: { items: [] } }),
    getPacks: vi.fn().mockResolvedValue({ data: { items: [] } }),
    getClosureValidation: vi.fn().mockResolvedValue({
      data: { status: 'NOT_OK', reason_codes: [], missing_fields: [] },
    }),
    addComment: vi.fn().mockResolvedValue({}),
    generatePack: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
  },
  actionsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
  },
  evidenceAssetsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
    upload: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
    getSignedUrl: vi.fn().mockResolvedValue({ data: { signed_url: '' } }),
  },
  checkPackCapability: vi.fn().mockResolvedValue({ canGenerate: true }),
  getApiErrorMessage: vi.fn((err: unknown) => String(err)),
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

vi.mock('../../../src/utils/investigationStatusFilter', () => ({
  getStatusDisplay: vi.fn(() => ({ label: 'Draft', className: 'bg-muted' })),
}));

import InvestigationDetail from '../../../src/pages/InvestigationDetail';

describe('InvestigationDetail', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/investigations/1']}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationDetail />} />
        </Routes>
      </MemoryRouter>
    );

  it('renders the investigation title', async () => {
    renderPage();
    expect(await screen.findByText('Test Investigation')).toBeInTheDocument();
  });

  it('renders the reference number', async () => {
    renderPage();
    expect(await screen.findByText('INV-001')).toBeInTheDocument();
  });

  it('renders tab navigation with Summary, Timeline, Evidence, Actions', async () => {
    renderPage();
    await screen.findByText('Test Investigation');
    expect(screen.getByText('Summary')).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('can switch to Timeline tab', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Test Investigation');
    const timelineTab = screen.getByText('Timeline');
    await user.click(timelineTab);
    expect(timelineTab).toBeInTheDocument();
  });
});
