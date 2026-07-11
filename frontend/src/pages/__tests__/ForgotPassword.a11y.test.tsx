/**
 * Real axe coverage for the Forgot Password CUJ page (/forgot-password), not a route stub.
 * Complements Login.a11y.test.tsx and Playwright a11y-audit.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import ForgotPassword from '../ForgotPassword'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { email?: string }) => {
      const translations: Record<string, string> = {
        'forgot_password.title': 'Forgot password',
        'forgot_password.subtitle': 'Enter your email to reset your password',
        'forgot_password.email_label': 'Email',
        'forgot_password.email_placeholder': 'you@example.com',
        'forgot_password.submit': 'Send reset link',
        'forgot_password.back_to_login': 'Back to login',
      }
      if (key === 'forgot_password.success_message' && opts?.email) {
        return `Reset link sent to ${opts.email}`
      }
      return translations[key] || key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

vi.mock('../../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('Forgot Password page accessibility (real page /forgot-password)', () => {
  it('renders the real Forgot Password form without critical axe violations', async () => {
    const { container } = render(<ForgotPassword />, { wrapper: Wrapper })

    expect(screen.getByRole('heading', { name: 'Forgot password' })).toBeInTheDocument()
    expect(screen.getByTestId('email-input')).toBeInTheDocument()
    expect(screen.getByTestId('submit-button')).toBeInTheDocument()

    await expectNoA11yViolations(container)
  })
})
