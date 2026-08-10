import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import NotificationSettings from '../NotificationSettings'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../utils/auth', () => ({
  getValidPlatformToken: vi.fn(() => 'token'),
}))

vi.mock('../../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

describe('NotificationSettings', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/feature-flags/')) {
          const key = decodeURIComponent(url.split('/feature-flags/')[1])
          return jsonResponse({ key, name: key, enabled: true })
        }
        if (url.includes('/push/vapid-status')) {
          return jsonResponse({
            status: 'not_configured',
            public_key_present: false,
            private_key_present: false,
            library: 'pywebpush',
          })
        }
        return jsonResponse({}, 404)
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('shows the persisted Compliance Schedule flags', async () => {
    render(<NotificationSettings />)

    expect(
      await screen.findByTestId('cs-notify-flag-compliance_schedule_assignment_notify'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('cs-notify-flag-compliance_schedule_due_reminder_notify'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('cs-notify-flag-compliance_schedule_email_enabled'),
    ).toBeInTheDocument()
  })

  it('offers no channel toggle that fails to persist', async () => {
    render(<NotificationSettings />)

    await screen.findByTestId('cs-notify-flag-compliance_schedule_assignment_notify')

    for (const label of [
      'Email Notifications',
      'Push Notifications',
      'In-App Notifications',
      'Webhook Integration',
    ]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument()
    }

    // Every remaining toggle belongs to a Compliance Schedule flag row, so no
    // control on this page can be clicked without a PATCH behind it.
    const rows = screen.getAllByTestId(/^cs-notify-flag-/)
    const toggles = screen.getAllByRole('button')
    expect(toggles).toHaveLength(rows.length)
  })

  it('reports push readiness from the server rather than a static badge', async () => {
    render(<NotificationSettings />)

    const readiness = await screen.findByTestId('push-vapid-readiness')
    expect(readiness).toHaveTextContent('VAPID not configured')
    await waitFor(() => expect(readiness).toHaveTextContent('public_key=false'))
  })
})
