import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Shield, Mail, ArrowLeft, AlertCircle, Loader2, CheckCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { ThemeToggle } from '../components/ui/ThemeToggle'
import { API_BASE_URL } from '../config/apiBase'

const API_BASE = API_BASE_URL;

type FormState = 'idle' | 'submitting' | 'success' | 'error';

export default function ForgotPassword() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [formState, setFormState] = useState<FormState>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormState('submitting')
    setErrorMessage(null)

    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/password-reset/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })

      if (!response.ok) {
        throw new Error('Failed to send reset email')
      }

      setFormState('success')
    } catch (err) {
      console.error('Password reset request failed:', err)
      // Still show success message to prevent email enumeration
      setFormState('success')
    }
  }

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
          <h1 className="text-2xl font-bold text-foreground mb-2">{t('forgot_password.title')}</h1>
          <p className="text-muted-foreground">
            {t('forgot_password.subtitle')}
          </p>
        </div>

        <Card className="p-8">
          {formState === 'success' ? (
            <div className="text-center" data-testid="success-message">
              <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-success" />
              </div>
              <h2 className="text-xl font-semibold text-foreground mb-2">{t('forgot_password.success_title')}</h2>
              <p className="text-muted-foreground mb-6">
                {t('forgot_password.success_message', { email })}
              </p>
              <p className="text-sm text-muted-foreground mb-6">
                {t('forgot_password.link_expiry')}
              </p>
              <Link to="/login">
                <Button variant="outline" className="w-full">
                  <ArrowLeft size={18} />
                  {t('forgot_password.back_to_login')}
                </Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              {/* Error display */}
              {formState === 'error' && errorMessage && (
                <div 
                  className="mb-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm"
                  data-testid="error-message"
                >
                  <div className="flex items-center gap-3">
                    <AlertCircle size={18} />
                    <span>{errorMessage}</span>
                  </div>
                </div>
              )}

              <div className="space-y-5">
                <div>
                  <label htmlFor="forgotpassword-field-0" className="block text-sm font-medium text-foreground mb-2">{t('forgot_password.email_label')}</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input id="forgotpassword-field-0"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder={t('forgot_password.email_placeholder')}
                      required
                      disabled={formState === 'submitting'}
                      className="pl-10"
                      data-testid="email-input"
                    />
                  </div>
                </div>
              </div>

              <Button
                type="submit"
                disabled={formState === 'submitting' || !email}
                className="mt-6 w-full"
                size="lg"
                data-testid="submit-button"
              >
                {formState === 'submitting' ? (
                  <Loader2 className="w-5 h-5 animate-spin" data-testid="spinner" />
                ) : (
                  t('forgot_password.submit')
                )}
              </Button>

              <div className="mt-6 text-center">
                <Link 
                  to="/login" 
                  className="text-sm text-primary hover:underline inline-flex items-center gap-1"
                  data-testid="back-to-login"
                >
                  <ArrowLeft size={14} />
                  {t('forgot_password.back_to_login')}
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  )
}
