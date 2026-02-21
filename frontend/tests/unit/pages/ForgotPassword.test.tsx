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

vi.mock('../../../src/components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div>ThemeToggle</div>,
}));

import ForgotPassword from '../../../src/pages/ForgotPassword';

describe('ForgotPassword', () => {
  it('renders the Reset Password heading and subtitle', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );
    expect(await screen.findByText('Reset Password')).toBeInTheDocument();
    expect(
      screen.getByText("Enter your email and we'll send you a reset link")
    ).toBeInTheDocument();
  });

  it('renders the email input with label', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );
    expect(await screen.findByText('Email Address')).toBeInTheDocument();
    expect(screen.getByTestId('email-input')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('you@company.com')).toBeInTheDocument();
  });

  it('renders the Send Reset Link button', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );
    expect(await screen.findByText('Send Reset Link')).toBeInTheDocument();
    expect(screen.getByTestId('submit-button')).toBeInTheDocument();
  });

  it('renders the Back to Login link', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );
    expect(await screen.findByText('Back to Login')).toBeInTheDocument();
    expect(screen.getByTestId('back-to-login')).toBeInTheDocument();
  });

  it('allows typing in the email field', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    );
    const emailInput = screen.getByTestId('email-input');
    await user.type(emailInput, 'user@example.com');
    expect(emailInput).toHaveValue('user@example.com');
  });
});
