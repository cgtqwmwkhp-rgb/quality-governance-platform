import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Shield,
  Mail,
  Lock,
  ArrowRight,
  AlertCircle,
  Loader2,
  RefreshCw,
  Trash2,
  Clock,
} from 'lucide-react'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import {
  authApi,
  classifyLoginError,
  LOGIN_ERROR_MESSAGES,
  getDurationBucket,
  type LoginErrorCode,
} from '../api/client'
import { API_BASE_URL } from '../config/apiBase'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { ThemeToggle } from '../components/ui/ThemeToggle'
import { clearTokens } from '../utils/auth'
import {
  trackLoginCompleted,
  trackLoginErrorShown,
  trackLoginRecoveryAction,
  trackLoginSlowWarning,
} from '../services/telemetry'

// ============ Microsoft Entra ID (Azure AD) Configuration ============
const AZURE_CONFIG = {
  clientId: import.meta.env.VITE_AZURE_CLIENT_ID || '',
  authority: import.meta.env.VITE_AZURE_AUTHORITY || '',
  redirectUri: window.location.origin + '/login',
}

const API_BASE = API_BASE_URL

const isAzureConfigured = () => {
  return (
    AZURE_CONFIG.clientId &&
    AZURE_CONFIG.clientId !== 'your-client-id' &&
    AZURE_CONFIG.authority &&
    AZURE_CONFIG.authority !== 'https://login.microsoftonline.com/your-tenant-id'
  )
}

// ============ Login State Machine (LOGIN_UX_CONTRACT.md) ============
type LoginState =
  | 'idle'
  | 'submitting'
  | 'spinner_visible'
  | 'slow_warning'
  | 'error_timeout'
  | 'error_unauthorized'
  | 'error_unavailable'
  | 'error_server'
  | 'error_network'
  | 'error_unknown'
  | 'success'

// Timing constants (from contract)
const SPINNER_DELAY_MS = 250 // Don't show spinner for fast requests
const SLOW_WARNING_MS = 3000 // Show "Still working..." after 3s
// Note: REQUEST_TIMEOUT_MS (15000) is handled by the API client's AbortController

interface LoginProps {
  onLogin: (token: string, refreshToken?: string) => void
}

// Telemetry wrappers (uses centralized service)
function emitLoginTelemetry(
  result: 'success' | 'error',
  durationMs: number,
  errorCode?: LoginErrorCode,
): void {
  const durationBucket = getDurationBucket(durationMs)
  trackLoginCompleted(result, durationBucket, errorCode)

  // Also track error shown if applicable
  if (result === 'error' && errorCode) {
    trackLoginErrorShown(errorCode)
  }
}

export default function Login({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginState, setLoginState] = useState<LoginState>('idle')
  const [errorCode, setErrorCode] = useState<LoginErrorCode | null>(null)
  const [ssoLoading, setSsoLoading] = useState(false)
  const [ssoError, setSsoError] = useState<string | null>(null)
  const { t } = useTranslation()
  const { announce } = useLiveAnnouncer()

  // Refs for timing
  const requestStartRef = useRef<number>(0)
  const spinnerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const slowWarningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Exchange Azure AD id_token for platform JWT (with retry for cold-start resilience)
  const exchangeToken = async (
    idToken: string,
  ): Promise<{ accessToken: string; refreshToken?: string } | null> => {
    const MAX_ATTEMPTS = 3
    const TIMEOUT_MS = 30_000

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS)
      try {
        const response = await fetch(`${API_BASE}/api/v1/auth/token-exchange`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: idToken }),
          signal: controller.signal,
        })

        if (response.ok) {
          const data = await response.json()
          return {
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
          }
        }

        // 4xx errors (except 408/429) are not retryable
        if (response.status >= 400 && response.status < 500 && response.status !== 408 && response.status !== 429) {
          if (import.meta.env.DEV) {
            console.error(`[AdminAuth] Token exchange rejected (${response.status}), not retrying`)
          }
          return null
        }

        if (import.meta.env.DEV) {
          console.warn(`[AdminAuth] Token exchange attempt ${attempt}/${MAX_ATTEMPTS} failed: ${response.status}`)
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn(`[AdminAuth] Token exchange attempt ${attempt}/${MAX_ATTEMPTS} error:`, err)
        }
      } finally {
        clearTimeout(timeout)
      }

      // Backoff before retry (1s, 2s)
      if (attempt < MAX_ATTEMPTS) {
        await new Promise((r) => setTimeout(r, attempt * 1000))
      }
    }

    return null
  }

  // Handle OAuth callback (check URL for tokens)
  const handleOAuthCallback = useCallback(async (): Promise<boolean> => {
    const hash = window.location.hash
    if (hash && hash.includes('id_token')) {
      setSsoLoading(true)
      const params = new URLSearchParams(hash.substring(1))
      const idToken = params.get('id_token')
      const state = params.get('state')
      const errorParam = params.get('error')
      const errorDesc = params.get('error_description')

      // Clear the hash from URL
      window.history.replaceState(null, '', window.location.pathname)

      if (errorParam) {
        setSsoError(errorDesc || 'Microsoft authentication failed')
        setSsoLoading(false)
        return false
      }

      const expectedState = sessionStorage.getItem('oauth_state')
      sessionStorage.removeItem('oauth_state')
      sessionStorage.removeItem('oauth_nonce')
      if (!state || !expectedState || state !== expectedState) {
        setSsoError('Microsoft authentication state could not be verified. Please try again.')
        setSsoLoading(false)
        return false
      }

      if (idToken) {
        const tokens = await exchangeToken(idToken)

        if (tokens) {
          const durationMs = Date.now() - (requestStartRef.current || Date.now())
          emitLoginTelemetry('success', durationMs)
          setLoginState('success')
          onLogin(tokens.accessToken, tokens.refreshToken)
          setSsoLoading(false)
          return true
        } else {
          setSsoError('Failed to authenticate with platform. Please try again.')
          setSsoLoading(false)
          return false
        }
      }
    }
    return false
  }, [onLogin])

  // Pre-warm the backend on mount so cold-start latency is absorbed before
  // the user actually submits credentials or returns from SSO redirect.
  // Retries silently to handle Azure App Service cold-start (503 until ready).
  useEffect(() => {
    let cancelled = false
    const warmUp = async () => {
      for (let attempt = 0; attempt < 3; attempt++) {
        if (cancelled) return
        try {
          // CORS mode (default): no-cors + CORP same-origin on the API causes
          // Chrome ERR_BLOCKED_BY_RESPONSE.NotSameOrigin on cross-origin warmup.
          await fetch(`${API_BASE}/healthz`, {
            method: 'GET',
            credentials: 'omit',
          })
          return
        } catch {
          if (attempt < 2) await new Promise((r) => setTimeout(r, 2000 * 2 ** attempt))
        }
      }
    }
    warmUp()
    return () => { cancelled = true }
  }, [])

  // Check for OAuth callback on mount
  useEffect(() => {
    handleOAuthCallback()
  }, [handleOAuthCallback])

  // Auto-recover from stuck SSO loading state (e.g. backend timeout).
  // Budget: 3 attempts x 30s timeout + backoff ≈ 95s; allow 100s.
  useEffect(() => {
    if (!ssoLoading) return
    const recovery = setTimeout(() => {
      setSsoLoading(false)
      setSsoError('Microsoft sign-in timed out. Please try again.')
    }, 100_000)
    return () => clearTimeout(recovery)
  }, [ssoLoading])

  // Microsoft SSO login
  const handleMicrosoftLogin = () => {
    setSsoError(null)
    setSsoLoading(true)

    if (!isAzureConfigured()) {
      setSsoError(
        'Microsoft login is not configured. Please use email/password or contact your administrator.',
      )
      setSsoLoading(false)
      return
    }

    // Generate state and nonce for security
    const state = crypto.randomUUID()
    const nonce = crypto.randomUUID()

    // Store state for validation
    sessionStorage.setItem('oauth_state', state)
    sessionStorage.setItem('oauth_nonce', nonce)

    // Build authorization URL
    const authUrl = new URL(`${AZURE_CONFIG.authority}/oauth2/v2.0/authorize`)
    authUrl.searchParams.set('client_id', AZURE_CONFIG.clientId)
    authUrl.searchParams.set('response_type', 'id_token')
    authUrl.searchParams.set('redirect_uri', AZURE_CONFIG.redirectUri)
    authUrl.searchParams.set('scope', 'openid profile email')
    authUrl.searchParams.set('response_mode', 'fragment')
    authUrl.searchParams.set('state', state)
    authUrl.searchParams.set('nonce', nonce)
    authUrl.searchParams.set('prompt', 'select_account')

    // Redirect to Microsoft login
    window.location.href = authUrl.toString()
  }

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (spinnerTimerRef.current) clearTimeout(spinnerTimerRef.current)
      if (slowWarningTimerRef.current) clearTimeout(slowWarningTimerRef.current)
    }
  }, [])

  // Clear session data (for stuck states)
  const handleClearSession = () => {
    trackLoginRecoveryAction('clear_session')
    clearTokens()
    localStorage.removeItem('user')
    sessionStorage.clear()
    // Reload to reset all state
    window.location.reload()
  }

  const handleRetry = () => {
    trackLoginRecoveryAction('retry')
    setLoginState('idle')
    setErrorCode(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Clear any previous errors
    setErrorCode(null)
    setLoginState('submitting')
    requestStartRef.current = Date.now()

    // Set up spinner delay (don't show spinner for fast requests)
    spinnerTimerRef.current = setTimeout(() => {
      setLoginState((current) => (current === 'submitting' ? 'spinner_visible' : current))
    }, SPINNER_DELAY_MS)

    // Set up slow warning
    slowWarningTimerRef.current = setTimeout(() => {
      setLoginState((current) => {
        if (current === 'submitting' || current === 'spinner_visible') {
          trackLoginSlowWarning()
          return 'slow_warning'
        }
        return current
      })
    }, SLOW_WARNING_MS)

    try {
      const response = await authApi.login({ email, password })

      const durationMs = Date.now() - requestStartRef.current
      emitLoginTelemetry('success', durationMs)

      setLoginState('success')
      announce('Signed in successfully')
      onLogin(response.data.access_token, response.data.refresh_token)
    } catch (err: unknown) {
      const code = classifyLoginError(err)
      const durationMs = Date.now() - requestStartRef.current

      emitLoginTelemetry('error', durationMs, code)

      setErrorCode(code)
      setLoginState(`error_${code.toLowerCase()}` as LoginState)
      announce(LOGIN_ERROR_MESSAGES[code] || 'Login failed', 'assertive')
    } finally {
      // CRITICAL: Always clear timers to prevent state leaks
      if (spinnerTimerRef.current) {
        clearTimeout(spinnerTimerRef.current)
        spinnerTimerRef.current = null
      }
      if (slowWarningTimerRef.current) {
        clearTimeout(slowWarningTimerRef.current)
        slowWarningTimerRef.current = null
      }
    }
  }

  // Derived state
  const isLoading = ['submitting', 'spinner_visible', 'slow_warning'].includes(loginState)
  const showSpinner = ['spinner_visible', 'slow_warning'].includes(loginState)
  const showSlowWarning = loginState === 'slow_warning'
  const isError = loginState.startsWith('error_')
  const showRecoveryActions = errorCode && errorCode !== 'UNAUTHORIZED'

  // Get error message from bounded list
  const errorMessage = errorCode ? LOGIN_ERROR_MESSAGES[errorCode] : null

  return (
    <div data-testid="login-page" className="min-h-screen flex items-center justify-center p-4 bg-background relative">
      {/* Theme Toggle */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-md relative">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl gradient-brand mb-4 shadow-glow">
            <Shield className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">{t('login.title')}</h1>
          <p className="text-muted-foreground">{t('login.subtitle')}</p>
        </div>

        {/* Login form */}
        <Card className="p-8">
          <form onSubmit={handleSubmit}>
            {/* Error display (bounded) */}
            {isError && errorMessage && (
              <div
                className="mb-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm"
                data-testid="login-error"
                data-error-code={errorCode}
              >
                <div className="flex items-center gap-3 mb-2">
                  <AlertCircle size={18} />
                  <span data-testid="error-message">{errorMessage}</span>
                </div>
                {showRecoveryActions && (
                  <div className="flex gap-2 mt-3" data-testid="recovery-actions">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRetry}
                      className="text-xs"
                      data-testid="retry-button"
                    >
                      <RefreshCw size={14} className="mr-1" />
                      Try Again
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleClearSession}
                      className="text-xs"
                      data-testid="clear-session-button"
                    >
                      <Trash2 size={14} className="mr-1" />
                      Clear Session
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Slow warning */}
            {showSlowWarning && (
              <div
                className="mb-6 p-4 rounded-xl bg-warning/10 border border-warning/20 text-warning-foreground text-sm flex items-center gap-3"
                data-testid="slow-warning"
              >
                <Clock size={18} className="text-warning" />
                <span>Still working... This is taking longer than usual.</span>
              </div>
            )}

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  {t('login.email')}
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    disabled={isLoading}
                    className="pl-10"
                    data-testid="email-input"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="password-input"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    id="password-input"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    disabled={isLoading}
                    className="pl-10"
                    data-testid="password-input"
                  />
                </div>
              </div>
            </div>

            <Button
              type="submit"
              disabled={isLoading || !email.trim() || !password}
              className="mt-6 w-full"
              size="lg"
              data-testid="login-submit-btn"
              data-loading={isLoading}
            >
              {showSpinner ? (
                <Loader2 className="w-5 h-5 animate-spin" data-testid="spinner" />
              ) : (
                <>
                  {t('login.submit')}
                  <ArrowRight size={18} />
                </>
              )}
            </Button>

            {/* Forgot Password Link */}
            <div className="mt-4 text-center">
              <a
                href="/forgot-password"
                className="text-sm text-primary hover:underline"
                data-testid="forgot-password-link"
              >
                {t('login.forgot_password')}
              </a>
            </div>

            {/* Divider */}
            <div className="my-6 flex items-center gap-4">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground">OR</span>
              <div className="flex-1 h-px bg-border" />
            </div>

            {/* SSO Error */}
            {ssoError && (
              <div
                className="mb-4 p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm"
                data-testid="sso-error"
              >
                <div className="flex items-center gap-3">
                  <AlertCircle size={18} />
                  <span>{ssoError}</span>
                </div>
              </div>
            )}

            {/* Microsoft SSO Button */}
            <Button
              type="button"
              onClick={handleMicrosoftLogin}
              disabled={isLoading || ssoLoading}
              variant="outline"
              size="lg"
              className="w-full"
              data-testid="microsoft-sso-button"
            >
              {ssoLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  {/* Microsoft Logo */}
                  <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none">
                    <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                    <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                    <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                    <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
                  </svg>
                  Sign in with Microsoft
                </>
              )}
            </Button>

            {isAzureConfigured() && (
              <p className="mt-3 text-center text-xs text-muted-foreground">
                Use your <span className="text-primary font-medium">@plantexpand.com</span> email
              </p>
            )}

            <p className="mt-6 text-center text-sm text-muted-foreground">{t('login.subtitle')}</p>
          </form>
        </Card>
      </div>
    </div>
  )
}
