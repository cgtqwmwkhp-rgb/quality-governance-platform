import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/config/apiBase', () => ({
  API_BASE_URL: 'https://test-api.example.com',
}));

vi.mock('../../../src/contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({
    isAuthenticated: true,
    user: { id: '1', name: 'Test User', email: 'test@example.com' },
    login: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
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

import Portal from '../../../src/pages/Portal';

describe('Portal', () => {
  it('renders the Plantexpand header', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>
    );
    expect(await screen.findByText('Plantexpand')).toBeInTheDocument();
    expect(screen.getByText('Employee Portal')).toBeInTheDocument();
  });

  it('displays the user name and email', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>
    );
    expect(await screen.findByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
  });

  it('renders the welcome question heading', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>
    );
    expect(await screen.findByText('What would you like to do?')).toBeInTheDocument();
    expect(screen.getByText('Select an option below')).toBeInTheDocument();
  });

  it('renders the main action cards', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>
    );
    expect(await screen.findByText('Submit a Report')).toBeInTheDocument();
    expect(screen.getByText('Incident, Near Miss, Complaint, or RTA')).toBeInTheDocument();
    expect(screen.getByText('Track My Report')).toBeInTheDocument();
    expect(screen.getByText('Check status with reference number')).toBeInTheDocument();
    expect(screen.getByText('Help & Support')).toBeInTheDocument();
    expect(screen.getByText('FAQs and contact information')).toBeInTheDocument();
  });

  it('renders the Admin Login footer link', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>
    );
    const adminLink = await screen.findByText('Admin Login →');
    expect(adminLink).toBeInTheDocument();
    expect(adminLink.closest('button')).not.toBeNull();
  });

  it('renders the mobile optimized badge', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>
    );
    expect(await screen.findByText('Optimized for mobile devices')).toBeInTheDocument();
  });
});
