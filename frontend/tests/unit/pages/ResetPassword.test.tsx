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

import ResetPassword from '../../../src/pages/ResetPassword';

describe('ResetPassword', () => {
  it('renders the page heading', () => {
    render(
      <MemoryRouter initialEntries={['/reset-password?token=test']}>
        <ResetPassword />
      </MemoryRouter>
    );
    expect(screen.getByText('Create New Password')).toBeInTheDocument();
    expect(screen.getByText('Enter your new password below')).toBeInTheDocument();
  });

  it('renders password input fields with labels', () => {
    render(
      <MemoryRouter initialEntries={['/reset-password?token=test']}>
        <ResetPassword />
      </MemoryRouter>
    );
    expect(screen.getByText('New Password')).toBeInTheDocument();
    expect(screen.getByText('Confirm Password')).toBeInTheDocument();
  });

  it('shows invalid token message when no token is provided', () => {
    render(
      <MemoryRouter initialEntries={['/reset-password']}>
        <ResetPassword />
      </MemoryRouter>
    );
    expect(screen.getByTestId('invalid-token-message')).toBeInTheDocument();
  });

  it('renders password inputs that accept text', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/reset-password?token=test']}>
        <ResetPassword />
      </MemoryRouter>
    );

    const inputs = screen.getAllByPlaceholderText('••••••••');
    expect(inputs.length).toBe(2);
    await user.type(inputs[0], 'Str0ngP@ss!');
    expect(inputs[0]).toHaveValue('Str0ngP@ss!');
  });
});
