import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, Mail, Smartphone, Globe, CalendarClock, UserPlus } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { API_BASE_URL } from '../../config/apiBase'
import { getValidPlatformToken } from '../../utils/auth'

interface NotificationChannel {
  key: string
  label: string
  icon: React.ReactNode
  enabled: boolean
  description: string
}

type PushReadiness = {
  status: string
  public_key_present?: boolean
  private_key_present?: boolean
  library?: string
  note?: string
}

type FeatureFlagRow = {
  key: string
  name: string
  description?: string | null
  enabled: boolean
}

const CS_NOTIFY_FLAGS = [
  {
    key: 'compliance_schedule_assignment_notify',
    label: 'Compliance Schedule — owner assignment',
    description: 'Notify when someone is allocated as schedule owner (in-app; email when email channel is on).',
    icon: <UserPlus className="w-5 h-5" />,
  },
  {
    key: 'compliance_schedule_due_reminder_notify',
    label: 'Compliance Schedule — due reminders',
    description:
      'Daily 08:15 UTC sweep reminders for due/overdue obligations. Completing a cycle rolls next_due_date and stops that occurrence’s reminders.',
    icon: <CalendarClock className="w-5 h-5" />,
  },
  {
    key: 'compliance_schedule_email_enabled',
    label: 'Compliance Schedule — email channel',
    description: 'Master email channel for CS assignment and due-reminder mail (also requires SMTP and user email preference).',
    icon: <Mail className="w-5 h-5" />,
  },
] as const

async function authHeaders(): Promise<HeadersInit> {
  const token = getValidPlatformToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

export default function NotificationSettings() {
  const { t } = useTranslation()
  const [pushReadiness, setPushReadiness] = useState<PushReadiness | null>(null)
  const [csFlags, setCsFlags] = useState<Record<string, boolean>>({})
  const [csFlagsError, setCsFlagsError] = useState<string | null>(null)
  const [csFlagsLoading, setCsFlagsLoading] = useState(true)
  const [csSavingKey, setCsSavingKey] = useState<string | null>(null)
  const [channels, setChannels] = useState<NotificationChannel[]>([
    {
      key: 'email',
      label: 'Email Notifications',
      icon: <Mail className="w-5 h-5" />,
      enabled: true,
      description: 'Send notifications via email for critical events',
    },
    {
      key: 'push',
      label: 'Push Notifications',
      icon: <Smartphone className="w-5 h-5" />,
      enabled: false,
      description: 'Browser push notifications for real-time alerts',
    },
    {
      key: 'in_app',
      label: 'In-App Notifications',
      icon: <Bell className="w-5 h-5" />,
      enabled: true,
      description: 'Show notifications within the application',
    },
    {
      key: 'webhook',
      label: 'Webhook Integration',
      icon: <Globe className="w-5 h-5" />,
      enabled: false,
      description: 'Send events to external webhook endpoints',
    },
  ])

  const loadCsFlags = useCallback(async () => {
    setCsFlagsLoading(true)
    setCsFlagsError(null)
    try {
      const headers = await authHeaders()
      const next: Record<string, boolean> = {}
      // Fetch each CS key directly. A paginated list + "missing => enabled"
      // misreads flags that exist but sit past the first page.
      await Promise.all(
        CS_NOTIFY_FLAGS.map(async (def) => {
          const res = await fetch(`${API_BASE_URL}/api/v1/feature-flags/${encodeURIComponent(def.key)}`, {
            credentials: 'include',
            headers,
          })
          if (res.ok) {
            const flag = (await res.json()) as FeatureFlagRow
            next[def.key] = Boolean(flag.enabled)
            return
          }
          if (res.status === 404) {
            // Seed default is enabled when the row is not yet materialised.
            next[def.key] = true
            return
          }
          throw new Error(`flag ${def.key} HTTP ${res.status}`)
        }),
      )
      setCsFlags(next)
    } catch {
      setCsFlagsError('Could not load Compliance Schedule notification flags.')
    } finally {
      setCsFlagsLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/notifications/push/vapid-status`, {
          credentials: 'include',
        })
        if (!res.ok) return
        const data = (await res.json()) as PushReadiness
        if (!cancelled) setPushReadiness(data)
      } catch {
        // Optional readiness — leave null on failure
      }
    }
    void load()
    void loadCsFlags()
    return () => {
      cancelled = true
    }
  }, [loadCsFlags])

  const toggleChannel = (key: string) => {
    // Cosmetic channel cards below are not persisted — CS toggles above are the real controls.
    setChannels((prev) => prev.map((ch) => (ch.key === key ? { ...ch, enabled: !ch.enabled } : ch)))
  }

  const toggleCsFlag = async (key: string) => {
    const current = csFlags[key] ?? true
    const next = !current
    setCsSavingKey(key)
    setCsFlagsError(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/feature-flags/${encodeURIComponent(key)}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: await authHeaders(),
        body: JSON.stringify({ enabled: next }),
      })
      if (!res.ok) {
        const detail = res.status === 403 ? 'Superuser required to change feature flags.' : `Save failed (${res.status}).`
        setCsFlagsError(detail)
        return
      }
      const updated = (await res.json()) as FeatureFlagRow
      setCsFlags((prev) => ({ ...prev, [key]: Boolean(updated.enabled) }))
    } catch {
      setCsFlagsError('Failed to update feature flag.')
    } finally {
      setCsSavingKey(null)
    }
  }

  const pushStatusLabel =
    pushReadiness?.status === 'configured'
      ? 'VAPID ready'
      : pushReadiness?.status === 'partial'
        ? 'VAPID partial'
        : pushReadiness
          ? 'VAPID not configured'
          : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {t('admin.notifications.title', 'Notification Settings')}
        </h1>
        <p className="text-muted-foreground mt-1">
          {t('admin.notifications.subtitle', 'Configure how and when notifications are sent')}
        </p>
      </div>

      <Card>
        <CardHeader>
          <h3 className="font-semibold">Compliance Schedule notifications</h3>
          <p className="text-sm text-muted-foreground">
            Persisted feature flags (superuser). Module opener and kill switch still close the whole
            Compliance Schedule surface.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {csFlagsError && (
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" role="alert">
              {csFlagsError}
            </p>
          )}
          {csFlagsLoading ? (
            <p className="text-sm text-muted-foreground">Loading flags…</p>
          ) : (
            CS_NOTIFY_FLAGS.map((def) => {
              const enabled = csFlags[def.key] ?? true
              return (
                <div
                  key={def.key}
                  className="flex items-center justify-between gap-4 py-2 border-b last:border-0"
                  data-testid={`cs-notify-flag-${def.key}`}
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                        enabled ? 'bg-primary/10 text-primary' : 'bg-gray-100 text-gray-400'
                      }`}
                    >
                      {def.icon}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium">{def.label}</p>
                      <p className="text-sm text-muted-foreground">{def.description}</p>
                      <p className="text-xs text-muted-foreground mt-1 font-mono">{def.key}</p>
                    </div>
                  </div>
                  <Button
                    variant={enabled ? 'default' : 'outline'}
                    size="sm"
                    disabled={csSavingKey === def.key}
                    onClick={() => void toggleCsFlag(def.key)}
                  >
                    {csSavingKey === def.key ? 'Saving…' : enabled ? 'Enabled' : 'Disabled'}
                  </Button>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      {pushReadiness && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            pushReadiness.status === 'configured'
              ? 'border-green-200 bg-green-50 text-green-800'
              : 'border-amber-200 bg-amber-50 text-amber-900'
          }`}
          data-testid="push-vapid-readiness"
        >
          <p className="font-medium">Push / VAPID readiness: {pushStatusLabel}</p>
          <p className="mt-1 text-muted-foreground">
            {pushReadiness.note ||
              (pushReadiness.status === 'configured'
                ? 'Web Push keys are present; outbound push can be sent.'
                : 'Push sends are skipped until VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are set.')}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            public_key={String(!!pushReadiness.public_key_present)} · private_key=
            {String(!!pushReadiness.private_key_present)} · library={pushReadiness.library || 'unknown'}
          </p>
        </div>
      )}

      <div className="grid gap-4">
        <p className="text-sm text-muted-foreground">
          Channel cards below are illustrative only and do not persist. Use Compliance Schedule
          toggles above, or user Notification Preferences for personal email/push prefs.
        </p>
        {channels.map((ch) => (
          <Card key={ch.key}>
            <CardContent className="flex items-center justify-between p-4">
              <div className="flex items-center gap-4">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    ch.enabled ? 'bg-primary/10 text-primary' : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {ch.icon}
                </div>
                <div>
                  <p className="font-medium">{ch.label}</p>
                  <p className="text-sm text-muted-foreground">{ch.description}</p>
                  {ch.key === 'push' && pushStatusLabel && (
                    <p className="text-xs mt-1 text-muted-foreground">{pushStatusLabel}</p>
                  )}
                </div>
              </div>
              <Button
                variant={ch.enabled ? 'default' : 'outline'}
                size="sm"
                onClick={() => toggleChannel(ch.key)}
              >
                {ch.enabled ? 'Enabled' : 'Disabled'}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
