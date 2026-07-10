import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, Mail, Smartphone, Globe } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { API_BASE_URL } from '../../config/apiBase'

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

export default function NotificationSettings() {
  const { t } = useTranslation()
  const [pushReadiness, setPushReadiness] = useState<PushReadiness | null>(null)
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
    return () => {
      cancelled = true
    }
  }, [])

  const toggleChannel = (key: string) => {
    setChannels((prev) => prev.map((ch) => (ch.key === key ? { ...ch, enabled: !ch.enabled } : ch)))
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

      <Card>
        <CardHeader>
          <h3 className="font-semibold">Event Triggers</h3>
          <p className="text-sm text-muted-foreground">
            Configure which events trigger notifications
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            'Incident reported',
            'Audit completed',
            'CAPA overdue',
            'Risk score changed',
            'Policy due for review',
            'Complaint received',
          ].map((event) => (
            <div
              key={event}
              className="flex items-center justify-between py-2 border-b last:border-0"
            >
              <span className="text-sm">{event}</span>
              <input
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
