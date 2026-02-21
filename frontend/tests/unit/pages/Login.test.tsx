import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
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
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );
    expect(document.body).toBeTruthy();
  });
});
