import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Mail, CalendarClock, UserPlus } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { API_BASE_URL } from '../../config/apiBase'
import { getValidPlatformToken } from '../../utils/auth'

type PushReadiness = {
  status: string
  public_key_present?: boolean
  private_key_present?: boolean
  library?: string
  note?: string
}

type InventoryChannel = {
  id: string
  label: string
  implemented: boolean
  transport?: string | null
  readiness: string
  can_send: boolean
  status_detail?: string | null
  note: string
}

type InventoryProducerFlag = {
  key: string
  enabled: boolean
  persisted: boolean
}

type InventoryProducer = {
  id: string
  event: string
  module: string
  symbol: string
  channels: string[]
  trigger: string
  schedule?: string | null
  feature_flags: InventoryProducerFlag[]
  status: string
  note: string
}

type NotificationInventory = {
  generated_at: string
  channels: InventoryChannel[]
  producers: InventoryProducer[]
  summary: {
    channels_implemented: number
    channels_can_send: number
    producers_total: number
    producers_active: number
    producers_without_caller: number
  }
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
  const [inventory, setInventory] = useState<NotificationInventory | null>(null)
  // The failure is stored as a kind rather than as a translated sentence, so this
  // loader does not close over `t`. A loader whose identity changes whenever the
  // translation function is re-created re-runs on every render, which is a fetch
  // loop rather than a fetch.
  const [inventoryError, setInventoryError] = useState<'forbidden' | 'unavailable' | null>(null)
  const [inventoryLoading, setInventoryLoading] = useState(true)

  const loadInventory = useCallback(async () => {
    setInventoryLoading(true)
    setInventoryError(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/notifications/inventory`, {
        credentials: 'include',
        headers: await authHeaders(),
      })
      if (res.status === 403) {
        setInventoryError('forbidden')
        return
      }
      if (!res.ok) throw new Error(`inventory HTTP ${res.status}`)
      setInventory((await res.json()) as NotificationInventory)
    } catch {
      setInventoryError('unavailable')
    } finally {
      setInventoryLoading(false)
    }
  }, [])

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
    void loadInventory()
    return () => {
      cancelled = true
    }
  }, [loadCsFlags, loadInventory])

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

  // Readiness is reported by the server; these only put the server's word into
  // the page's language. Nothing here decides whether a channel is ready.
  const readinessLabel = (readiness: string): string => {
    switch (readiness) {
      case 'ready':
        return t('admin.notifications.inventory.readiness_ready', 'Ready')
      case 'degraded':
        return t('admin.notifications.inventory.readiness_degraded', 'Sends, needs attention')
      case 'disabled':
        return t('admin.notifications.inventory.readiness_disabled', 'Disabled by ops')
      case 'not_implemented':
        return t('admin.notifications.inventory.readiness_not_implemented', 'Does not exist')
      default:
        return t('admin.notifications.inventory.readiness_not_configured', 'Not configured')
    }
  }

  const readinessVariant = (readiness: string): 'success' | 'warning' | 'secondary' | 'outline' => {
    if (readiness === 'ready') return 'success'
    if (readiness === 'degraded') return 'warning'
    if (readiness === 'not_implemented') return 'outline'
    return 'secondary'
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
          <h3 className="font-semibold">
            {t('admin.notifications.inventory.title', 'What this deployment can actually notify')}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t(
              'admin.notifications.inventory.subtitle',
              'Read-only. Channels and readiness come from server state; producers are the events that create notifications. Nothing on this panel can be switched.',
            )}
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {inventoryError && (
            <p
              className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
              role="alert"
              data-testid="notification-inventory-error"
            >
              {inventoryError === 'forbidden'
                ? t(
                    'admin.notifications.inventory.forbidden',
                    'The admin:manage permission is required to read the notification inventory.',
                  )
                : t(
                    'admin.notifications.inventory.error',
                    'Could not read the notification inventory from the server.',
                  )}
            </p>
          )}
          {inventoryLoading && !inventory && (
            <p className="text-sm text-muted-foreground">
              {t('admin.notifications.inventory.loading', 'Reading inventory…')}
            </p>
          )}

          {inventory && (
            <div className="space-y-6" data-testid="notification-inventory">
              <p className="text-sm text-muted-foreground" data-testid="notification-inventory-summary">
                {t('admin.notifications.inventory.channels_can_send', 'Channels able to send')}:{' '}
                <span className="font-medium text-foreground">
                  {inventory.summary.channels_can_send}/{inventory.summary.channels_implemented}
                </span>
                {' · '}
                {t('admin.notifications.inventory.producers_active', 'Events that notify someone')}:{' '}
                <span className="font-medium text-foreground">
                  {inventory.summary.producers_active}/{inventory.summary.producers_total}
                </span>
                {' · '}
                {t('admin.notifications.inventory.producers_without_caller', 'Written but never triggered')}:{' '}
                <span className="font-medium text-foreground">{inventory.summary.producers_without_caller}</span>
              </p>

              <div className="space-y-3">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t('admin.notifications.inventory.channels_heading', 'Delivery channels')}
                </h4>
                {inventory.channels.map((channel) => (
                  <div
                    key={channel.id}
                    className="py-2 border-b last:border-0"
                    data-testid={`inventory-channel-${channel.id}`}
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`font-medium ${channel.implemented ? '' : 'text-muted-foreground'}`}>
                        {channel.label}
                      </span>
                      <Badge variant={readinessVariant(channel.readiness)}>{readinessLabel(channel.readiness)}</Badge>
                      <span className="text-xs text-muted-foreground font-mono">{channel.id}</span>
                    </div>
                    {channel.transport && (
                      <p className="text-xs text-muted-foreground mt-1">{channel.transport}</p>
                    )}
                    <p className="text-sm text-muted-foreground mt-1">{channel.status_detail || channel.note}</p>
                  </div>
                ))}
              </div>

              <div className="space-y-3">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t('admin.notifications.inventory.producers_heading', 'Events that produce notifications')}
                </h4>
                {inventory.producers.map((producer) => {
                  const dead = producer.status === 'no_production_caller'
                  return (
                    <div
                      key={producer.id}
                      className={`py-2 border-b last:border-0 ${dead ? 'bg-amber-50/60 -mx-2 px-2 rounded' : ''}`}
                      data-testid={`inventory-producer-${producer.id}`}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium">{producer.event}</span>
                        <Badge variant={dead ? 'warning' : 'success'}>
                          {dead
                            ? t('admin.notifications.inventory.status_no_caller', 'Notifies nobody')
                            : t('admin.notifications.inventory.status_active', 'Active')}
                        </Badge>
                        {producer.channels.map((channel) => (
                          <Badge key={channel} variant="outline">
                            {channel}
                          </Badge>
                        ))}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">{producer.note}</p>
                      <p className="text-xs text-muted-foreground mt-1 font-mono">
                        {producer.module}#{producer.symbol}
                        {producer.schedule ? ` · ${producer.schedule}` : ''}
                      </p>
                      {producer.feature_flags.length > 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {producer.feature_flags
                            .map(
                              (flag) =>
                                `${flag.key}=${flag.enabled ? 'on' : 'off'}${flag.persisted ? '' : ' (default)'}`,
                            )
                            .join(' · ')}
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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
    </div>
  )
}
