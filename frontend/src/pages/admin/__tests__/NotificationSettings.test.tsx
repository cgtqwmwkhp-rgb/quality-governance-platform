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

// Shaped like GET /api/v1/notifications/inventory. Deliberately an unconfigured
// deployment: the readiness the page must not overstate is the default one.
const INVENTORY_FIXTURE = {
  generated_at: '2026-08-10T18:00:00+00:00',
  channels: [
    {
      id: 'in_app',
      label: 'In-app',
      implemented: true,
      transport: 'notifications table row, pushed over the /realtime websocket',
      readiness: 'ready',
      can_send: true,
      status_detail: null,
      note: 'Always attempted, and needs no configuration.',
    },
    {
      id: 'email',
      label: 'Email',
      implemented: true,
      transport: 'Celery send_email task, then aiosmtplib via EmailService',
      readiness: 'not_configured',
      can_send: false,
      status_detail: 'Outbound email is not configured.',
      note: 'Enqueued to the Celery notifications path.',
    },
    {
      id: 'webhook',
      label: 'Webhook',
      implemented: false,
      transport: null,
      readiness: 'not_implemented',
      can_send: false,
      status_detail: null,
      note: 'NotificationChannel has no webhook member, so no notification has ever been deliverable this way.',
    },
  ],
  producers: [
    {
      id: 'action_owner_assigned',
      event: 'An action is assigned to an owner, or its owner changes',
      module: 'src/domain/services/action_assignment_service.py',
      symbol: 'notify_action_assignment',
      channels: ['preferences'],
      trigger: 'request',
      schedule: null,
      feature_flags: [],
      status: 'active',
      note: 'Reached from action create and action update.',
    },
    {
      id: 'sos_alert',
      event: 'A lone worker raises an SOS',
      module: 'src/domain/services/notification_service.py',
      symbol: 'send_sos_alert',
      channels: ['in_app', 'email', 'sms', 'push'],
      trigger: 'request',
      schedule: null,
      feature_flags: [],
      status: 'no_production_caller',
      note: 'No production caller, so raising an SOS in this product notifies nobody.',
    },
    {
      id: 'compliance_schedule_due_reminder',
      event: 'A Compliance Schedule obligation falls due or goes overdue',
      module: 'src/infrastructure/tasks/compliance_schedule_notification_tasks.py',
      symbol: 'sweep_compliance_schedule_due',
      channels: ['in_app', 'email'],
      trigger: 'schedule',
      schedule: 'daily 08:15 UTC',
      feature_flags: [
        { key: 'compliance_schedule_due_reminder_notify', enabled: true, persisted: true },
        { key: 'compliance_schedule_email_enabled', enabled: false, persisted: false },
      ],
      status: 'active',
      note: 'Deduplicates per obligation occurrence.',
    },
  ],
  summary: {
    channels_implemented: 2,
    channels_can_send: 1,
    producers_total: 3,
    producers_active: 2,
    producers_without_caller: 1,
  },
}

/** Stub fetch, optionally overriding the inventory response. */
function stubFetch(inventory: () => Response = () => jsonResponse(INVENTORY_FIXTURE)) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/notifications/inventory')) {
        return inventory()
      }
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
}

describe('NotificationSettings', () => {
  beforeEach(() => {
    stubFetch()
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

  it('shows the Incident assignment notify flag', async () => {
    render(<NotificationSettings />)

    expect(
      await screen.findByTestId('incident-notify-flag-incident_owner_assignment_notify'),
    ).toBeInTheDocument()
  })

  it('offers no channel toggle that fails to persist', async () => {
    render(<NotificationSettings />)

    await screen.findByTestId('cs-notify-flag-compliance_schedule_assignment_notify')
    await screen.findByTestId('incident-notify-flag-incident_owner_assignment_notify')

    for (const label of [
      'Email Notifications',
      'Push Notifications',
      'In-App Notifications',
      'Webhook Integration',
    ]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument()
    }

    // Every remaining toggle belongs to a persisted notify flag row, so no
    // control on this page can be clicked without a PATCH behind it.
    const rows = [
      ...screen.getAllByTestId(/^cs-notify-flag-/),
      ...screen.getAllByTestId(/^incident-notify-flag-/),
    ]
    const toggles = screen.getAllByRole('button')
    expect(toggles).toHaveLength(rows.length)
  })

  it('reports push readiness from the server rather than a static badge', async () => {
    render(<NotificationSettings />)

    const readiness = await screen.findByTestId('push-vapid-readiness')
    expect(readiness).toHaveTextContent('VAPID not configured')
    await waitFor(() => expect(readiness).toHaveTextContent('public_key=false'))
  })

  describe('notification inventory', () => {
    it('reports each channel with the readiness the server gave it', async () => {
      render(<NotificationSettings />)

      const inApp = await screen.findByTestId('inventory-channel-in_app')
      expect(inApp).toHaveTextContent('In-app')
      expect(inApp).toHaveTextContent('Ready')

      const email = screen.getByTestId('inventory-channel-email')
      expect(email).toHaveTextContent('Email')
      expect(email).toHaveTextContent('Not configured')
      // The server's own explanation, not a label invented in the page.
      expect(email).toHaveTextContent('Outbound email is not configured.')
    })

    it('says outright that a channel does not exist rather than omitting it', async () => {
      render(<NotificationSettings />)

      const webhook = await screen.findByTestId('inventory-channel-webhook')
      expect(webhook).toHaveTextContent('Webhook')
      expect(webhook).toHaveTextContent('Does not exist')
      expect(webhook).toHaveTextContent('no webhook member')
    })

    it('names the events that are written and notify nobody', async () => {
      render(<NotificationSettings />)

      const sos = await screen.findByTestId('inventory-producer-sos_alert')
      expect(sos).toHaveTextContent('A lone worker raises an SOS')
      expect(sos).toHaveTextContent('Notifies nobody')
      expect(sos).toHaveTextContent('notifies nobody')

      const active = screen.getByTestId('inventory-producer-action_owner_assigned')
      expect(active).toHaveTextContent('Active')
    })

    it('shows where a producer lives and when it runs', async () => {
      render(<NotificationSettings />)

      const sweep = await screen.findByTestId('inventory-producer-compliance_schedule_due_reminder')
      expect(sweep).toHaveTextContent(
        'src/infrastructure/tasks/compliance_schedule_notification_tasks.py#sweep_compliance_schedule_due',
      )
      expect(sweep).toHaveTextContent('daily 08:15 UTC')
      // A flag with no row is marked as running on its default, not shown as off.
      expect(sweep).toHaveTextContent('compliance_schedule_email_enabled=off (default)')
    })

    it('counts what can send without rounding it up', async () => {
      render(<NotificationSettings />)

      const summary = await screen.findByTestId('notification-inventory-summary')
      expect(summary).toHaveTextContent('1/2')
      expect(summary).toHaveTextContent('2/3')
    })

    it('adds no control to the page', async () => {
      render(<NotificationSettings />)

      await screen.findByTestId('notification-inventory')
      await screen.findByTestId('cs-notify-flag-compliance_schedule_assignment_notify')
      await screen.findByTestId('incident-notify-flag-incident_owner_assignment_notify')

      // The inventory is a report. If it ever grows a button, that button is a
      // notification setting nothing persists — the thing FR-HONESTY-SWEEP-01
      // deleted from this page.
      const rows = [
        ...screen.getAllByTestId(/^cs-notify-flag-/),
        ...screen.getAllByTestId(/^incident-notify-flag-/),
      ]
      expect(screen.getAllByRole('button')).toHaveLength(rows.length)
      expect(screen.queryAllByRole('switch')).toHaveLength(0)
      expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
    })

    it('reads the inventory once per mount', async () => {
      render(<NotificationSettings />)

      await screen.findByTestId('notification-inventory')
      await screen.findByTestId('cs-notify-flag-compliance_schedule_assignment_notify')

      // The loader must not close over anything that changes identity per render.
      // When it did, the effect re-ran on every state update and the page sat in a
      // fetch loop that also starved the feature-flag load.
      const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
      const inventoryCalls = calls.filter(([input]) => String(input).includes('/notifications/inventory'))
      expect(inventoryCalls).toHaveLength(1)
    })

    it('says the permission is missing rather than showing an empty inventory', async () => {
      vi.unstubAllGlobals()
      stubFetch(() => jsonResponse({ detail: "Permission 'admin:manage' required" }, 403))
      render(<NotificationSettings />)

      const error = await screen.findByTestId('notification-inventory-error')
      expect(error).toHaveTextContent('admin:manage')
      expect(screen.queryByTestId('notification-inventory')).not.toBeInTheDocument()
    })

    it('claims no readiness at all when the inventory cannot be read', async () => {
      vi.unstubAllGlobals()
      stubFetch(() => jsonResponse({}, 500))
      render(<NotificationSettings />)

      expect(await screen.findByTestId('notification-inventory-error')).toBeInTheDocument()
      expect(screen.queryByTestId('inventory-channel-email')).not.toBeInTheDocument()
      // A failed read must not cost the flags, which come from a different call.
      expect(
        screen.getByTestId('cs-notify-flag-compliance_schedule_assignment_notify'),
      ).toBeInTheDocument()
    })
  })
})
