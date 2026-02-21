import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({
    isAuthenticated: false,
    user: null,
    login: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
    platformToken: null,
  }),
}));

vi.mock('../../../src/components/ReportChat', () => ({
  default: () => <div>ReportChat</div>,
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

import PortalTrack from '../../../src/pages/PortalTrack';

describe('PortalTrack', () => {
  it('renders the page heading and subtitle', () => {
    render(
      <MemoryRouter>
        <PortalTrack />
      </MemoryRouter>
    );
    expect(screen.getByText('Your Reports')).toBeInTheDocument();
    expect(screen.getByText('Track Reports')).toBeInTheDocument();
  });

  it('shows sign-in prompt when not authenticated', () => {
    render(
      <MemoryRouter>
        <PortalTrack />
      </MemoryRouter>
    );
    expect(screen.getByText('Sign in for easier access')).toBeInTheDocument();
    expect(screen.getByText('Sign In')).toBeInTheDocument();
  });

  it('renders the reference number search input', () => {
    render(
      <MemoryRouter>
        <PortalTrack />
      </MemoryRouter>
    );
    expect(
      screen.getByPlaceholderText('Enter reference number (e.g., INC-2026-0001)')
    ).toBeInTheDocument();
  });

  it('shows example reference formats', () => {
    render(
      <MemoryRouter>
        <PortalTrack />
      </MemoryRouter>
    );
    expect(screen.getByText('INC-2026-0001')).toBeInTheDocument();
    expect(screen.getByText('COMP-2026-0001')).toBeInTheDocument();
  });

  it('allows typing in the search field', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PortalTrack />
      </MemoryRouter>
    );
    const input = screen.getByPlaceholderText('Enter reference number (e.g., INC-2026-0001)');
    await user.type(input, 'inc-2026');
    expect(input).toHaveValue('INC-2026');
  });
});
