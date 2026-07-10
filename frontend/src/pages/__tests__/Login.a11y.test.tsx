/**
 * Real axe coverage for the Login CUJ page (/login), not a route stub.
 * Complements Playwright a11y-audit and unit Login.test.tsx.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import Login from '../Login'
import { LiveAnnouncerProvider } from '../../components/ui/LiveAnnouncer'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'login.title': 'Sign In',
        'login.subtitle': 'Welcome back',
        'login.email': 'Email',
        'login.submit': 'Sign In',
        'login.forgot_password': 'Forgot password?',
      }
      return translations[key] || key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  authApi: {
    login: vi.fn().mockRejectedValue(new Error('Network error')),
  },
  classifyLoginError: () => 'NETWORK' as const,
  LOGIN_ERROR_I18N_KEYS: {
    TIMEOUT: 'login.error.TIMEOUT',
    UNAUTHORIZED: 'login.error.UNAUTHORIZED',
    UNAVAILABLE: 'login.error.UNAVAILABLE',
    SERVER_ERROR: 'login.error.SERVER_ERROR',
    NETWORK_ERROR: 'login.error.NETWORK_ERROR',
    UNKNOWN: 'login.error.UNKNOWN',
  },
  LOGIN_ERROR_MESSAGES: {
    TIMEOUT: 'Request timed out',
    UNAUTHORIZED: 'Invalid credentials',
    UNAVAILABLE: 'Service unavailable',
    SERVER: 'Server error',
    NETWORK: 'Network error',
    UNKNOWN: 'Unknown error',
  },
  getDurationBucket: () => 'fast',
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

vi.mock('../../services/telemetry', () => ({
  trackLoginCompleted: vi.fn(),
  trackLoginErrorShown: vi.fn(),
  trackLoginRecoveryAction: vi.fn(),
  trackLoginSlowWarning: vi.fn(),
}))

vi.mock('../../utils/auth', () => ({
  clearTokens: vi.fn(),
}))

vi.mock('../../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <LiveAnnouncerProvider>{children}</LiveAnnouncerProvider>
}

describe('Login page accessibility (real page /login)', () => {
  const onLogin = vi.fn()

  beforeEach(() => {
    onLogin.mockClear()
  })

  it('renders the real Login form without critical axe violations', async () => {
    const { container } = render(<Login onLogin={onLogin} />, { wrapper: Wrapper })

    expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    expect(screen.getByTestId('email-input')).toBeInTheDocument()
    expect(screen.getByTestId('password-input')).toBeInTheDocument()

    await expectNoA11yViolations(container)
  })
})
