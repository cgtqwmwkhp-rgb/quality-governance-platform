import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getKPIs: vi.fn().mockResolvedValue({ data: {} }),
    getExecutiveSummary: vi.fn().mockResolvedValue({ data: {} }),
    getExportJobs: vi.fn().mockResolvedValue({ data: [] }),
    createExportJob: vi.fn(),
    deleteExportJob: vi.fn(),
    downloadExport: vi.fn(),
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

import ExportCenter from '../../../src/pages/ExportCenter';

describe('ExportCenter', () => {
  it('renders the Export Center heading and subtitle', async () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('Export Center')).toBeInTheDocument();
    expect(screen.getByText('Generate reports and export data')).toBeInTheDocument();
  });

  it('renders the tab navigation buttons', async () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('New Export')).toBeInTheDocument();
    expect(screen.getByText('Export History')).toBeInTheDocument();
    expect(screen.getByText('Templates')).toBeInTheDocument();
  });

  it('renders the module selection area with all modules', async () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('Select Modules')).toBeInTheDocument();
    expect(screen.getByText('Incidents')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
    expect(screen.getByText('Audits')).toBeInTheDocument();
    expect(screen.getByText('Risks')).toBeInTheDocument();
    expect(screen.getByText('Complaints')).toBeInTheDocument();
  });

  it('renders export format options', async () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('Export Format')).toBeInTheDocument();
    expect(screen.getByText('Formatted report')).toBeInTheDocument();
    expect(screen.getByText('Spreadsheet with charts')).toBeInTheDocument();
    expect(screen.getByText('Raw data export')).toBeInTheDocument();
    expect(screen.getByText('API-ready format')).toBeInTheDocument();
  });

  it('renders the summary section and Start Export button', async () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>
    );
    expect(await screen.findByText('Summary')).toBeInTheDocument();
    expect(screen.getByText('0 selected')).toBeInTheDocument();
    expect(screen.getByText('Start Export')).toBeInTheDocument();
  });
});
