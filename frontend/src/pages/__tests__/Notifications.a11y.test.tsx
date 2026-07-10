/**
 * Real axe coverage for the Notifications CUJ page, not a route stub.
 * Complements Notifications.test.tsx and Playwright a11y-audit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Notifications from '../Notifications'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../components/ui/Switch', () => ({
  Switch: ({
    checked,
    onCheckedChange,
  }: {
    checked?: boolean
    onCheckedChange?: (v: boolean) => void
  }) => (
    <button
      type="button"
      data-testid="switch"
      aria-pressed={checked}
      onClick={() => onCheckedChange?.(!checked)}
    >
      switch
    </button>
  ),
}))

const mockList = vi.fn()
const mockGetPreferences = vi.fn()

vi.mock('../../api/client', () => ({
  notificationsApi: {
    list: (...args: unknown[]) => mockList(...args),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
    delete: vi.fn(),
    clearAll: vi.fn(),
    getPreferences: (...args: unknown[]) => mockGetPreferences(...args),
    updatePreferences: vi.fn(),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Something went wrong',
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

describe('Notifications page accessibility (real page)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 11,
            type: 'incident_new',
            priority: 'high',
            title: 'High Priority Incident Reported',
            message: 'Requires attention.',
            entity_type: 'incident',
            action_url: '/incidents/1',
            is_read: false,
            created_at: '2026-07-09T12:00:00.000Z',
          },
        ],
        total: 1,
        unread_count: 1,
      },
    })
    mockGetPreferences.mockResolvedValue({
      data: {
        email_enabled: true,
        sms_enabled: false,
        push_enabled: true,
        category_preferences: {},
      },
    })
  })

  it('renders the real Notifications page without critical axe violations', async () => {
    const { container } = render(<Notifications />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText('High Priority Incident Reported')).toBeInTheDocument()
    })
    await expectNoA11yViolations(container)
  })
})
