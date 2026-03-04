import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Login from '../Login';
import { LiveAnnouncerProvider } from '../../components/ui/LiveAnnouncer';
import type { ReactNode } from 'react';

// Mock i18next - returns the key as the translation
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'login.title': 'Sign In',
        'login.subtitle': 'Welcome back',
        'login.email': 'Email',
        'login.submit': 'Sign In',
        'login.forgot_password': 'Forgot password?',
      };
      return translations[key] || key;
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

vi.mock('../../api/client', () => ({
  authApi: {
    login: vi.fn().mockRejectedValue(new Error('Network error')),
  },
  classifyLoginError: () => 'NETWORK' as const,
  LOGIN_ERROR_MESSAGES: {
    TIMEOUT: 'Request timed out',
    UNAUTHORIZED: 'Invalid credentials',
    UNAVAILABLE: 'Service unavailable',
    SERVER: 'Server error',
    NETWORK: 'Network error',
    UNKNOWN: 'Unknown error',
  },
  getDurationBucket: () => 'fast',
}));

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}));

vi.mock('../../services/telemetry', () => ({
  trackLoginCompleted: vi.fn(),
  trackLoginErrorShown: vi.fn(),
  trackLoginRecoveryAction: vi.fn(),
  trackLoginSlowWarning: vi.fn(),
}));

vi.mock('../../utils/auth', () => ({
  clearTokens: vi.fn(),
}));

vi.mock('../../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}));

function Wrapper({ children }: { children: ReactNode }) {
  return <LiveAnnouncerProvider>{children}</LiveAnnouncerProvider>;
}

describe('Login', () => {
  const onLogin = vi.fn();

  beforeEach(() => {
    onLogin.mockClear();
  });

  it('renders the login form with email and password fields', () => {
    render(<Login onLogin={onLogin} />, { wrapper: Wrapper });

    expect(screen.getByTestId('email-input')).toBeInTheDocument();
    expect(screen.getByTestId('password-input')).toBeInTheDocument();
    expect(screen.getByTestId('submit-button')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument();
  });

  it('allows typing into email and password fields', async () => {
    const user = userEvent.setup();
    render(<Login onLogin={onLogin} />, { wrapper: Wrapper });

    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    await user.type(emailInput, 'user@example.com');
    await user.type(passwordInput, 'secret123');

    expect(emailInput).toHaveValue('user@example.com');
    expect(passwordInput).toHaveValue('secret123');
  });

  it('calls authApi.login and invokes onLogin on success', async () => {
    const { authApi } = await import('../../api/client');
    vi.mocked(authApi.login).mockResolvedValueOnce({ data: { access_token: 'real-jwt-token' } });

    const user = userEvent.setup();
    render(<Login onLogin={onLogin} />, { wrapper: Wrapper });

    fireEvent.change(screen.getByTestId('email-input'), {
      target: { value: 'admin@plantexpand.com' },
    });
    fireEvent.change(screen.getByTestId('password-input'), {
      target: { value: 'TestUser123!' },
    });
    await user.click(screen.getByTestId('submit-button'));

    await vi.waitFor(() => {
      expect(onLogin).toHaveBeenCalledOnce();
    });

    expect(onLogin).toHaveBeenCalledWith('real-jwt-token');
  });
});
