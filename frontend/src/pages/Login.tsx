import { useState, useEffect, useRef } from 'react'
import { Shield, Mail, Lock, ArrowRight, AlertCircle, Loader2, RefreshCw, Trash2, Clock } from 'lucide-react'
import { 
  authApi, 
  classifyLoginError, 
  LOGIN_ERROR_MESSAGES, 
  getDurationBucket,
  type LoginErrorCode,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { ThemeToggle } from '../components/ui/ThemeToggle'
import { clearTokens } from '../utils/auth'
import { 
  trackLoginCompleted, 
  trackLoginErrorShown, 
  trackLoginRecoveryAction,
  trackLoginSlowWarning 
} from '../services/telemetry'

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
  | 'success';

// Timing constants (from contract)
const SPINNER_DELAY_MS = 250;      // Don't show spinner for fast requests
const SLOW_WARNING_MS = 3000;      // Show "Still working..." after 3s
const REQUEST_TIMEOUT_MS = 15000;  // Hard timeout

interface LoginProps {
  onLogin: (token: string) => void
}

// Telemetry wrappers (uses centralized service)
function emitLoginTelemetry(
  result: 'success' | 'error',
  durationMs: number,
  errorCode?: LoginErrorCode
): void {
  const durationBucket = getDurationBucket(durationMs);
  trackLoginCompleted(result, durationBucket, errorCode);
  
  // Also track error shown if applicable
  if (result === 'error' && errorCode) {
    trackLoginErrorShown(errorCode);
  }
}

export default function Login({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginState, setLoginState] = useState<LoginState>('idle')
  const [errorCode, setErrorCode] = useState<LoginErrorCode | null>(null)
  
  // Refs for timing
  const requestStartRef = useRef<number>(0)
  const spinnerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const slowWarningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
      setLoginState(current => 
        current === 'submitting' ? 'spinner_visible' : current
      )
    }, SPINNER_DELAY_MS)
    
    // Set up slow warning
    slowWarningTimerRef.current = setTimeout(() => {
      setLoginState(current => {
        if (current === 'submitting' || current === 'spinner_visible') {
          trackLoginSlowWarning()
          return 'slow_warning'
        }
        return current
      })
    }, SLOW_WARNING_MS)

    try {
      // Demo login bypass - allows access without backend
      const DEMO_CREDENTIALS = [
        { email: 'admin@plantexpand.com', password: 'TestUser123!' },
        { email: 'demo@plantexpand.com', password: 'demo123' },
        { email: 'jamie.uncle@plantexpand.com', password: 'Plantexpand2026!' },
      ]
      
      const isDemoLogin = DEMO_CREDENTIALS.some(
        cred => cred.email.toLowerCase() === email.toLowerCase() && cred.password === password
      )
      
      if (isDemoLogin) {
        // Generate a demo token (JWT-like structure for demo purposes)
        const getUserName = (userEmail: string) => {
          const names: Record<string, string> = {
            'admin@plantexpand.com': 'Admin User',
            'demo@plantexpand.com': 'Demo User',
            'jamie.uncle@plantexpand.com': 'Jamie Uncle',
          }
          return names[userEmail.toLowerCase()] || 'User'
        }
        const demoPayload = {
          sub: email,
          email: email,
          name: getUserName(email),
          role: 'admin',
          exp: Math.floor(Date.now() / 1000) + 86400, // 24 hours
        }
        const demoToken = `demo.${btoa(JSON.stringify(demoPayload))}.signature`
        
        const durationMs = Date.now() - requestStartRef.current
        emitLoginTelemetry('success', durationMs)
        
        setLoginState('success')
        onLogin(demoToken)
        return
      }
      
      // Try real API login
      const response = await authApi.login({ email, password })
      
      const durationMs = Date.now() - requestStartRef.current
      emitLoginTelemetry('success', durationMs)
      
      setLoginState('success')
      onLogin(response.data.access_token)
      
    } catch (err: unknown) {
      // Classify error into bounded code
      const code = classifyLoginError(err)
      const durationMs = Date.now() - requestStartRef.current
      
      emitLoginTelemetry('error', durationMs, code)
      
      setErrorCode(code)
      setLoginState(`error_${code.toLowerCase()}` as LoginState)
      
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
    <div className="min-h-screen flex items-center justify-center p-4 bg-background relative">
      {/* Theme Toggle */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative animate-fade-in">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl gradient-brand mb-4 shadow-glow">
            <Shield className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Quality Governance Platform</h1>
          <p className="text-muted-foreground">Sign in to manage your governance</p>
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
                <label className="block text-sm font-medium text-foreground mb-2">Email</label>
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
                <label className="block text-sm font-medium text-foreground mb-2">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
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
              disabled={isLoading}
              className="mt-6 w-full"
              size="lg"
              data-testid="submit-button"
              data-loading={isLoading}
            >
              {showSpinner ? (
                <Loader2 className="w-5 h-5 animate-spin" data-testid="spinner" />
              ) : (
                <>
                  Sign In
                  <ArrowRight size={18} />
                </>
              )}
            </Button>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Demo: admin@plantexpand.com / TestUser123!
            </p>
          </form>
        </Card>
      </div>
    </div>
  )
}
