import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

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

import PortalReport from '../../../src/pages/PortalReport';

describe('PortalReport', () => {
  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <PortalReport />
      </MemoryRouter>
    );
    expect(screen.getByText('What are you reporting?')).toBeInTheDocument();
    expect(screen.getByText('Select the type that best describes your report')).toBeInTheDocument();
  });

  it('renders the Submit Report header', () => {
    render(
      <MemoryRouter>
        <PortalReport />
      </MemoryRouter>
    );
    expect(screen.getByText('Submit Report')).toBeInTheDocument();
  });

  it('renders all four report type options', () => {
    render(
      <MemoryRouter>
        <PortalReport />
      </MemoryRouter>
    );
    expect(screen.getByText('Incident')).toBeInTheDocument();
    expect(screen.getByText('Near Miss')).toBeInTheDocument();
    expect(screen.getByText('Customer Complaint')).toBeInTheDocument();
    expect(screen.getByText('Road Traffic Collision')).toBeInTheDocument();
  });

  it('renders descriptions for each report type', () => {
    render(
      <MemoryRouter>
        <PortalReport />
      </MemoryRouter>
    );
    expect(screen.getByText('Report a workplace injury or accident')).toBeInTheDocument();
    expect(screen.getByText('Report a close call where no injury occurred')).toBeInTheDocument();
    expect(screen.getByText('Log a complaint or concern from a customer')).toBeInTheDocument();
    expect(screen.getByText('Report an RTC involving a company vehicle')).toBeInTheDocument();
  });

  it('renders the help text at the bottom', () => {
    render(
      <MemoryRouter>
        <PortalReport />
      </MemoryRouter>
    );
    expect(screen.getByText(/Not sure which to choose/)).toBeInTheDocument();
  });

  it('report type cards have test IDs for interaction', () => {
    render(
      <MemoryRouter>
        <PortalReport />
      </MemoryRouter>
    );
    expect(screen.getByTestId('report-incident-card')).toBeInTheDocument();
    expect(screen.getByTestId('report-near-miss-card')).toBeInTheDocument();
    expect(screen.getByTestId('report-complaint-card')).toBeInTheDocument();
    expect(screen.getByTestId('report-rta-card')).toBeInTheDocument();
  });
});
