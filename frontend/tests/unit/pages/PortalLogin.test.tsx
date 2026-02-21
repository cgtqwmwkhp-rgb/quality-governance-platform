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
    loginWithDemo: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
    error: null,
    isAzureADAvailable: false,
  }),
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

vi.mock('../../../src/components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div>ThemeToggle</div>,
}));

import PortalLogin from '../../../src/pages/PortalLogin';

describe('PortalLogin', () => {
  it('renders the Employee Portal heading', async () => {
    render(
      <MemoryRouter>
        <PortalLogin />
      </MemoryRouter>
    );
    expect(await screen.findByText('Employee Portal')).toBeInTheDocument();
  });

  it('renders the sign-in subtitle', async () => {
    render(
      <MemoryRouter>
        <PortalLogin />
      </MemoryRouter>
    );
    expect(await screen.findByText('Sign in with your Plantexpand account')).toBeInTheDocument();
  });

  it('renders the Microsoft sign-in button', async () => {
    render(
      <MemoryRouter>
        <PortalLogin />
      </MemoryRouter>
    );
    expect(await screen.findByText('Sign in with Microsoft')).toBeInTheDocument();
  });

  it('renders the demo login button', async () => {
    render(
      <MemoryRouter>
        <PortalLogin />
      </MemoryRouter>
    );
    expect(await screen.findByText('Continue as Demo User')).toBeInTheDocument();
  });

  it('renders the Admin Login link', async () => {
    render(
      <MemoryRouter>
        <PortalLogin />
      </MemoryRouter>
    );
    const adminLink = await screen.findByText('Admin Login →');
    expect(adminLink).toBeInTheDocument();
    expect(adminLink.closest('button')).not.toBeNull();
  });

  it('renders secure sign-in info items', async () => {
    render(
      <MemoryRouter>
        <PortalLogin />
      </MemoryRouter>
    );
    expect(await screen.findByText(/Your identity will be recorded/)).toBeInTheDocument();
    expect(screen.getByText(/Your name and details will be auto-filled/)).toBeInTheDocument();
    expect(screen.getByText(/Track all your submitted reports/)).toBeInTheDocument();
  });
});
