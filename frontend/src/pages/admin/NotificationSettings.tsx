import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, Mail, Smartphone, Globe } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'

interface NotificationChannel {
  key: string
  label: string
  icon: React.ReactNode
  enabled: boolean
  description: string
}

export default function NotificationSettings() {
  const { t } = useTranslation()
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

  const toggleChannel = (key: string) => {
    setChannels((prev) =>
      prev.map((ch) => (ch.key === key ? { ...ch, enabled: !ch.enabled } : ch)),
    )
  }

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
            <div key={event} className="flex items-center justify-between py-2 border-b last:border-0">
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
