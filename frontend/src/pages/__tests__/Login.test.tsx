import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Login from '../Login'
import { LiveAnnouncerProvider } from '../../components/ui/LiveAnnouncer'
import type { ReactNode } from 'react'

// Mock i18next - returns the key as the translation
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'brand.product_name': 'Quality Governance Platform',
        'brand.company_line': 'Plantexpand Limited',
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

describe('Login', () => {
  const onLogin = vi.fn()

  beforeEach(() => {
    onLogin.mockClear()
  })

  it('renders the login form with email and password fields', () => {
    render(<Login onLogin={onLogin} />, { wrapper: Wrapper })

    expect(screen.getByTestId('email-input')).toBeInTheDocument()
    expect(screen.getByTestId('password-input')).toBeInTheDocument()
    expect(screen.getByTestId('login-submit-btn')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Quality Governance Platform' })).toBeInTheDocument()
    expect(screen.getByText('Plantexpand Limited')).toBeInTheDocument()
  })

  it('allows typing into email and password fields', async () => {
    const user = userEvent.setup()
    render(<Login onLogin={onLogin} />, { wrapper: Wrapper })

    const emailInput = screen.getByTestId('email-input')
    const passwordInput = screen.getByTestId('password-input')

    await user.type(emailInput, 'user@example.com')
    await user.type(passwordInput, 'secret123')

    expect(emailInput).toHaveValue('user@example.com')
    expect(passwordInput).toHaveValue('secret123')
  })

  it('calls authApi.login and invokes onLogin on success', async () => {
    const { authApi } = await import('../../api/client')
    vi.mocked(authApi.login).mockResolvedValueOnce({
      data: { access_token: 'real-jwt-token', refresh_token: 'refresh-token' },
    })

    const user = userEvent.setup()
    render(<Login onLogin={onLogin} />, { wrapper: Wrapper })

    fireEvent.change(screen.getByTestId('email-input'), {
      target: { value: 'admin@plantexpand.com' },
    })
    fireEvent.change(screen.getByTestId('password-input'), {
      target: { value: 'TestUser123!' },
    })
    await user.click(screen.getByTestId('login-submit-btn'))

    await vi.waitFor(() => {
      expect(onLogin).toHaveBeenCalledOnce()
    })

    expect(onLogin).toHaveBeenCalledWith('real-jwt-token', 'refresh-token')
  })

  // The warm-up effect had no test at all, which is why a leaked response stream on the
  // most important route in the product went unnoticed. The assertion is deliberately on
  // `bodyUsed` rather than on which method was called: what matters is that the body is
  // no longer undisturbed, and reading it or cancelling it both satisfy that. Asserting
  // `text()` was called would pin the fix to one implementation and fail the next person
  // who switches to `body.cancel()` for the same correct reason.
  describe('backend warm-up', () => {
    it('consumes the warm-up response body, so the request cannot stay in flight', async () => {
      const warmUpResponse = new Response('{"status":"healthy","version":"df6cd70e"}', {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
      expect(warmUpResponse.bodyUsed).toBe(false)

      const fetchSpy = vi.fn().mockResolvedValue(warmUpResponse)
      vi.stubGlobal('fetch', fetchSpy)

      try {
        render(<Login onLogin={onLogin} />, { wrapper: Wrapper })

        await vi.waitFor(() => {
          expect(fetchSpy).toHaveBeenCalledWith(
            'http://localhost:3000/api/v1/health',
            expect.objectContaining({ method: 'GET', credentials: 'omit' }),
          )
        })

        await vi.waitFor(() => {
          expect(warmUpResponse.bodyUsed).toBe(true)
        })
      } finally {
        vi.unstubAllGlobals()
      }
    })

    it('does not retry when the warm-up succeeds', async () => {
      const fetchSpy = vi
        .fn()
        .mockImplementation(() => Promise.resolve(new Response('{}', { status: 200 })))
      vi.stubGlobal('fetch', fetchSpy)

      try {
        render(<Login onLogin={onLogin} />, { wrapper: Wrapper })

        await vi.waitFor(() => {
          expect(fetchSpy).toHaveBeenCalled()
        })

        const healthCalls = () =>
          fetchSpy.mock.calls.filter(([url]) => String(url).endsWith('/api/v1/health')).length
        expect(healthCalls()).toBe(1)
      } finally {
        vi.unstubAllGlobals()
      }
    })
  })
})
