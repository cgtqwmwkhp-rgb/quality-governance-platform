import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  complianceApi: {
    listEvidenceLinks: vi.fn().mockResolvedValue({ data: [] }),
    getCoverage: vi.fn().mockResolvedValue({ data: {} }),
    autoTag: vi.fn().mockResolvedValue([]),
    linkEvidence: vi.fn().mockResolvedValue({}),
    deleteEvidenceLink: vi.fn().mockResolvedValue({}),
    getReport: vi.fn().mockResolvedValue({ data: {} }),
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

import ComplianceEvidence from '../../../src/pages/ComplianceEvidence';

describe('ComplianceEvidence', () => {
  it('renders the page heading', async () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(await screen.findByText('ISO Compliance Evidence Center')).toBeInTheDocument();
  });

  it('renders the subtitle', async () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(
      await screen.findByText('Central repository for all compliance evidence mapped to ISO standards')
    ).toBeInTheDocument();
  });

  it('renders action buttons', async () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(await screen.findByText('AI Auto-Tagger')).toBeInTheDocument();
    expect(screen.getByText('Export Report')).toBeInTheDocument();
  });

  it('renders view mode tabs', async () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(await screen.findByText('Clause View')).toBeInTheDocument();
    expect(screen.getByText('Evidence List')).toBeInTheDocument();
    expect(screen.getByText('Gap Analysis')).toBeInTheDocument();
  });

  it('renders the Clause Structure heading in default view', async () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(await screen.findByText('Clause Structure')).toBeInTheDocument();
  });

  it('shows the clause detail placeholder when no clause is selected', async () => {
    render(
      <MemoryRouter>
        <ComplianceEvidence />
      </MemoryRouter>
    );
    expect(await screen.findByText('Select a Clause')).toBeInTheDocument();
    expect(
      screen.getByText('Click on any clause in the tree view to see details and linked evidence')
    ).toBeInTheDocument();
  });
});
