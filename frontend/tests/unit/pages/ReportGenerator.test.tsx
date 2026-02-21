import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  analyticsApi: {
    getReports: vi.fn().mockResolvedValue({ data: [] }),
    generateReport: vi.fn(),
    getExecutiveSummary: vi.fn().mockResolvedValue({ data: {} }),
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

import ReportGenerator from '../../../src/pages/ReportGenerator';

describe('ReportGenerator', () => {
  it('renders the Report Generator heading', () => {
    render(
      <MemoryRouter>
        <ReportGenerator />
      </MemoryRouter>
    );
    expect(screen.getByText('Report Generator')).toBeInTheDocument();
    expect(screen.getByText('Create and schedule automated reports')).toBeInTheDocument();
  });

  it('renders report template cards', () => {
    render(
      <MemoryRouter>
        <ReportGenerator />
      </MemoryRouter>
    );
    expect(screen.getByText('Executive Summary')).toBeInTheDocument();
    expect(screen.getByText('Safety Performance')).toBeInTheDocument();
    expect(screen.getByText('Compliance Report')).toBeInTheDocument();
  });

  it('renders tab navigation', () => {
    render(
      <MemoryRouter>
        <ReportGenerator />
      </MemoryRouter>
    );
    expect(screen.getAllByText(/Generate Report/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Scheduled Reports/i).length).toBeGreaterThanOrEqual(1);
  });

  it('can switch to Scheduled Reports tab', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ReportGenerator />
      </MemoryRouter>
    );

    const scheduledTab = screen.getByText('Scheduled Reports');
    await user.click(scheduledTab);
    expect(screen.getByText('Monthly Executive Summary')).toBeInTheDocument();
  });
});
