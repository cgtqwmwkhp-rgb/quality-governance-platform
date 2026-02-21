import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../src/api/client', () => ({
  authApi: {
    login: vi.fn(),
    microsoftLogin: vi.fn(),
  },
  classifyLoginError: vi.fn(() => 'UNKNOWN'),
  LOGIN_ERROR_MESSAGES: {},
  getDurationBucket: vi.fn(() => 'fast'),
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

vi.mock('../../../src/services/telemetry', () => ({
  trackLoginCompleted: vi.fn(),
  trackLoginErrorShown: vi.fn(),
  trackLoginRecoveryAction: vi.fn(),
  trackLoginSlowWarning: vi.fn(),
}));

vi.mock('../../../src/components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div>ThemeToggle</div>,
}));

import Login from '../../../src/pages/Login';

describe('Login', () => {
  const mockOnLogin = vi.fn();

  it('renders the platform heading and subtitle', async () => {
    render(
      <MemoryRouter>
        <Login onLogin={mockOnLogin} />
      </MemoryRouter>
    );
    expect(await screen.findByText('Quality Governance Platform')).toBeInTheDocument();
    expect(screen.getByText('Sign in to manage your governance')).toBeInTheDocument();
  });

  it('renders email and password input fields with labels', async () => {
    render(
      <MemoryRouter>
        <Login onLogin={mockOnLogin} />
      </MemoryRouter>
    );
    expect(await screen.findByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.getByTestId('email-input')).toBeInTheDocument();
    expect(screen.getByTestId('password-input')).toBeInTheDocument();
  });

  it('renders the Sign In button and forgot password link', async () => {
    render(
      <MemoryRouter>
        <Login onLogin={mockOnLogin} />
      </MemoryRouter>
    );
    expect(await screen.findByText('Sign In')).toBeInTheDocument();
    expect(screen.getByTestId('submit-button')).toBeInTheDocument();
    expect(screen.getByText('Forgot password?')).toBeInTheDocument();
  });

  it('renders the Microsoft SSO button', async () => {
    render(
      <MemoryRouter>
        <Login onLogin={mockOnLogin} />
      </MemoryRouter>
    );
    expect(await screen.findByText('Sign in with Microsoft')).toBeInTheDocument();
    expect(screen.getByTestId('microsoft-sso-button')).toBeInTheDocument();
  });

  it('allows typing in email and password fields', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Login onLogin={mockOnLogin} />
      </MemoryRouter>
    );
    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    await user.type(emailInput, 'admin@example.com');
    expect(emailInput).toHaveValue('admin@example.com');

    await user.type(passwordInput, 'secret123');
    expect(passwordInput).toHaveValue('secret123');
  });
});
