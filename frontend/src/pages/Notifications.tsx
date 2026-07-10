import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Trash2,
  Settings,
  AlertTriangle,
  Info,
  CheckCircle2,
  Clock,
  Mail,
  MessageSquare,
  Smartphone,
  Volume2,
  Loader2,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Switch } from '../components/ui/Switch'
import { EmptyState } from '../components/ui/EmptyState'
import { cn } from '../helpers/utils'
import {
  notificationsApi,
  getApiErrorMessage,
  type NotificationEntry,
  type NotificationPreferences,
  type NotificationCategoryChannels,
} from '../api/client'

type UiNotificationType = 'alert' | 'info' | 'success' | 'warning' | 'reminder'

interface Notification {
  id: number
  type: UiNotificationType
  title: string
  message: string
  timestamp: string
  read: boolean
  module?: string
  actionUrl?: string
  actionLabel?: string
}

interface NotificationPreferenceRow {
  id: string
  label: string
  description: string
  email: boolean
  push: boolean
  inApp: boolean
}

const CATEGORY_IDS = [
  'high_priority_alerts',
  'action_reminders',
  'audit_notifications',
  'document_updates',
  'weekly_summaries',
  'assignment_notifications',
] as const

type CategoryId = (typeof CATEGORY_IDS)[number]

const DEFAULT_CATEGORY_CHANNELS: Record<CategoryId, NotificationCategoryChannels> = {
  high_priority_alerts: { email: true, push: true, in_app: true },
  action_reminders: { email: true, push: true, in_app: true },
  audit_notifications: { email: true, push: false, in_app: true },
  document_updates: { email: false, push: false, in_app: true },
  weekly_summaries: { email: true, push: false, in_app: false },
  assignment_notifications: { email: true, push: true, in_app: true },
}

function formatRelativeTime(iso: string): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const sec = Math.round((Date.now() - t) / 1000)
  if (sec < 45) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const h = Math.round(min / 60)
  if (h < 48) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 14) return `${d}d ago`
  return new Date(iso).toLocaleDateString()
}

function mapApiType(entry: NotificationEntry): UiNotificationType {
  const type = (entry.type || '').toLowerCase()
  const priority = (entry.priority || '').toLowerCase()
  if (priority === 'critical' || priority === 'high') return 'alert'
  if (type.includes('overdue') || type.includes('escalat') || type.includes('expir')) return 'warning'
  if (type.includes('due_soon') || type.includes('scheduled') || type.includes('reminder')) {
    return 'reminder'
  }
  if (
    type.includes('completed') ||
    type.includes('granted') ||
    type.includes('approved') ||
    type === 'report_ready'
  ) {
    return 'success'
  }
  return 'info'
}

function humanizeModule(entityType?: string | null): string | undefined {
  if (!entityType) return undefined
  return entityType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function mapEntry(entry: NotificationEntry): Notification {
  return {
    id: entry.id,
    type: mapApiType(entry),
    title: entry.title,
    message: entry.message,
    timestamp: entry.created_at ? formatRelativeTime(entry.created_at) : '',
    read: Boolean(entry.is_read),
    module: humanizeModule(entry.entity_type),
    actionUrl: entry.action_url || undefined,
    actionLabel: entry.action_url ? 'View' : undefined,
  }
}

function mergeCategoryPreferences(
  fromApi: NotificationPreferences['category_preferences'] | undefined,
): Record<CategoryId, NotificationCategoryChannels> {
  const merged = { ...DEFAULT_CATEGORY_CHANNELS }
  if (!fromApi || typeof fromApi !== 'object') return merged
  for (const id of CATEGORY_IDS) {
    const raw = fromApi[id]
    if (!raw || typeof raw !== 'object') continue
    merged[id] = {
      email: Boolean(raw.email),
      push: Boolean(raw.push),
      in_app: raw.in_app !== false && raw.inApp !== false,
    }
  }
  return merged
}

function buildPreferenceRows(
  t: (key: string) => string,
  categories: Record<CategoryId, NotificationCategoryChannels>,
): NotificationPreferenceRow[] {
  return CATEGORY_IDS.map((id) => ({
    id,
    label: t(`notifications.pref.${id}`),
    description: t(`notifications.pref.${id}_desc`),
    email: categories[id].email,
    push: categories[id].push,
    inApp: categories[id].in_app,
  }))
}

export default function Notifications() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<'notifications' | 'settings'>('notifications')
  const [filter, setFilter] = useState<'all' | 'unread' | 'alerts'>('all')
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [prefsLoading, setPrefsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [prefsError, setPrefsError] = useState<string | null>(null)
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [actionPending, setActionPending] = useState(false)
  const [preferences, setPreferences] = useState<NotificationPreferenceRow[]>(() =>
    buildPreferenceRows(t, DEFAULT_CATEGORY_CHANNELS),
  )
  const [globalChannels, setGlobalChannels] = useState({
    email_enabled: true,
    push_enabled: true,
    sms_enabled: false,
  })
  const [uiPrefs, setUiPrefs] = useState({ soundEnabled: true, desktopEnabled: false })

  const typeStyles: Record<string, { icon: ReactNode; variant: string }> = {
    alert: { icon: <AlertTriangle className="w-5 h-5" />, variant: 'destructive' },
    warning: { icon: <Clock className="w-5 h-5" />, variant: 'warning' },
    success: { icon: <CheckCircle2 className="w-5 h-5" />, variant: 'success' },
    info: { icon: <Info className="w-5 h-5" />, variant: 'info' },
    reminder: { icon: <Bell className="w-5 h-5" />, variant: 'primary' },
  }

  const loadNotifications = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await notificationsApi.list({ page: 1, page_size: 50 })
      setNotifications((data.items || []).map(mapEntry))
      setUnreadCount(data.unread_count ?? (data.items || []).filter((n) => !n.is_read).length)
    } catch (err) {
      setError(getApiErrorMessage(err))
      setNotifications([])
      setUnreadCount(0)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadPreferences = useCallback(async () => {
    setPrefsLoading(true)
    setPrefsError(null)
    try {
      const { data } = await notificationsApi.getPreferences()
      setGlobalChannels({
        email_enabled: data.email_enabled !== false,
        push_enabled: data.push_enabled !== false,
        sms_enabled: Boolean(data.sms_enabled),
      })
      const categories = mergeCategoryPreferences(data.category_preferences)
      setPreferences(buildPreferenceRows(t, categories))
    } catch (err) {
      setPrefsError(getApiErrorMessage(err))
      setPreferences(buildPreferenceRows(t, DEFAULT_CATEGORY_CHANNELS))
    } finally {
      setPrefsLoading(false)
    }
    // t from useTranslation is used for labels only; intentionally omitted to avoid
    // re-fetch loops when translation function identity changes between renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void loadNotifications()
  }, [loadNotifications])

  useEffect(() => {
    if (activeTab === 'settings') {
      void loadPreferences()
    }
  }, [activeTab, loadPreferences])

  const filteredNotifications = useMemo(() => {
    return notifications.filter((n) => {
      if (filter === 'unread') return !n.read
      if (filter === 'alerts') return n.type === 'alert' || n.type === 'warning'
      return true
    })
  }, [notifications, filter])

  const persistCategoryPreferences = async (rows: NotificationPreferenceRow[]) => {
    const category_preferences: Record<string, NotificationCategoryChannels> = {}
    for (const row of rows) {
      category_preferences[row.id] = {
        email: row.email,
        push: row.push,
        in_app: row.inApp,
      }
    }
    setSavingPrefs(true)
    setPrefsError(null)
    try {
      await notificationsApi.updatePreferences({
        ...globalChannels,
        category_preferences,
      })
    } catch (err) {
      setPrefsError(getApiErrorMessage(err))
      void loadPreferences()
    } finally {
      setSavingPrefs(false)
    }
  }

  const markAsRead = async (id: number) => {
    const previous = notifications
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
    setUnreadCount((c) => Math.max(0, c - (previous.find((n) => n.id === id && !n.read) ? 1 : 0)))
    try {
      await notificationsApi.markRead(id)
    } catch (err) {
      setNotifications(previous)
      setError(getApiErrorMessage(err))
      void loadNotifications()
    }
  }

  const markAllAsRead = async () => {
    if (unreadCount === 0 || actionPending) return
    setActionPending(true)
    const previous = notifications
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    setUnreadCount(0)
    try {
      await notificationsApi.markAllRead()
    } catch (err) {
      setNotifications(previous)
      setError(getApiErrorMessage(err))
      void loadNotifications()
    } finally {
      setActionPending(false)
    }
  }

  const deleteNotification = async (id: number) => {
    const previous = notifications
    const removed = previous.find((n) => n.id === id)
    setNotifications((prev) => prev.filter((n) => n.id !== id))
    if (removed && !removed.read) setUnreadCount((c) => Math.max(0, c - 1))
    try {
      await notificationsApi.delete(id)
    } catch (err) {
      setNotifications(previous)
      setError(getApiErrorMessage(err))
      void loadNotifications()
    }
  }

  const clearAll = async () => {
    if (notifications.length === 0 || actionPending) return
    setActionPending(true)
    const previous = notifications
    setNotifications([])
    setUnreadCount(0)
    try {
      await notificationsApi.clearAll()
    } catch (err) {
      setNotifications(previous)
      setError(getApiErrorMessage(err))
      void loadNotifications()
    } finally {
      setActionPending(false)
    }
  }

  const togglePreference = (id: string, channel: 'email' | 'push' | 'inApp') => {
    setPreferences((prev) => {
      const next = prev.map((p) => (p.id === id ? { ...p, [channel]: !p[channel] } : p))
      void persistCategoryPreferences(next)
      return next
    })
  }

  const toggleGlobalChannel = async (channel: 'email_enabled' | 'push_enabled' | 'sms_enabled') => {
    const next = { ...globalChannels, [channel]: !globalChannels[channel] }
    setGlobalChannels(next)
    setSavingPrefs(true)
    setPrefsError(null)
    try {
      const category_preferences: Record<string, NotificationCategoryChannels> = {}
      for (const row of preferences) {
        category_preferences[row.id] = {
          email: row.email,
          push: row.push,
          in_app: row.inApp,
        }
      }
      await notificationsApi.updatePreferences({
        ...next,
        category_preferences,
      })
    } catch (err) {
      setPrefsError(getApiErrorMessage(err))
      void loadPreferences()
    } finally {
      setSavingPrefs(false)
    }
  }

  const updateUiPref = (key: 'soundEnabled' | 'desktopEnabled', value: boolean) => {
    setUiPrefs((prev) => ({ ...prev, [key]: value }))
    if (key === 'desktopEnabled' && value && typeof window !== 'undefined' && 'Notification' in window) {
      try {
        const DesktopNotification = window.Notification
        if (DesktopNotification.permission === 'default') {
          void DesktopNotification.requestPermission()
        }
      } catch {
        // Ignore unsupported Notification API environments
      }
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl relative">
              <Bell className="w-8 h-8 text-primary" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground text-xs font-bold rounded-full flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </div>
            {t('notifications.title')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('notifications.subtitle')}</p>
        </div>
      </div>

      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('notifications')}
          className={cn(
            'px-6 py-3 font-medium transition-all border-b-2',
            activeTab === 'notifications'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground',
          )}
        >
          <span className="flex items-center gap-2">
            <Bell className="w-5 h-5" />
            {t('notifications.title')}
            {unreadCount > 0 && <Badge variant="destructive">{unreadCount}</Badge>}
          </span>
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={cn(
            'px-6 py-3 font-medium transition-all border-b-2',
            activeTab === 'settings'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground',
          )}
        >
          <span className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            {t('notifications.preferences')}
          </span>
        </button>
      </div>

      {activeTab === 'notifications' && (
        <>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              {(['all', 'unread', 'alerts'] as const).map((f) => (
                <Button
                  key={f}
                  variant={filter === f ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilter(f)}
                >
                  {f === 'all'
                    ? t('common.all')
                    : f === 'unread'
                      ? t('notifications.filter.unread', { count: unreadCount })
                      : t('notifications.filter.alerts')}
                </Button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void markAllAsRead()}
                disabled={unreadCount === 0 || actionPending}
              >
                <CheckCheck className="w-4 h-4" />
                {t('notifications.mark_all_read')}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void clearAll()}
                disabled={notifications.length === 0 || actionPending}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
                {t('notifications.clear_all')}
              </Button>
            </div>
          </div>

          {error && (
            <Card className="p-4 border-destructive/40 bg-destructive/5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <p className="text-sm text-destructive">{error}</p>
                <Button variant="outline" size="sm" onClick={() => void loadNotifications()}>
                  {t('common.retry', 'Retry')}
                </Button>
              </div>
            </Card>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>{t('common.loading_data')}</span>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNotifications.map((notification) => (
                <Card
                  key={notification.id}
                  className={cn('p-4', !notification.read && 'border-primary/30 bg-primary/5')}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        'p-2.5 rounded-xl',
                        typeStyles[notification.type].variant === 'destructive' &&
                          'bg-destructive/10 text-destructive',
                        typeStyles[notification.type].variant === 'warning' &&
                          'bg-warning/10 text-warning',
                        typeStyles[notification.type].variant === 'success' &&
                          'bg-success/10 text-success',
                        typeStyles[notification.type].variant === 'info' && 'bg-info/10 text-info',
                        typeStyles[notification.type].variant === 'primary' &&
                          'bg-primary/10 text-primary',
                      )}
                    >
                      {typeStyles[notification.type].icon}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h2
                              className={cn(
                                'font-semibold truncate text-base',
                                notification.read ? 'text-muted-foreground' : 'text-foreground',
                              )}
                            >
                              {notification.title}
                            </h2>
                            {notification.module && (
                              <Badge variant="secondary">{notification.module}</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-muted-foreground">
                              {notification.timestamp}
                            </span>
                            {!notification.read && (
                              <span className="w-2 h-2 bg-primary rounded-full" />
                            )}
                          </div>
                        </div>
                      </div>

                      <p className="text-muted-foreground mt-2 text-sm">{notification.message}</p>

                      <div className="flex items-center gap-2 mt-3 flex-wrap">
                        {notification.actionUrl && (
                          <a
                            href={notification.actionUrl}
                            className="text-sm text-primary hover:underline font-medium"
                          >
                            {notification.actionLabel} →
                          </a>
                        )}
                        <div className="flex-1" />
                        {!notification.read && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void markAsRead(notification.id)}
                          >
                            <Check className="w-4 h-4" />
                            {t('notifications.mark_read')}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void deleteNotification(notification.id)}
                          className="text-destructive hover:text-destructive"
                          aria-label={t('notifications.delete', 'Delete notification')}
                        >
                          <Trash2 className="w-4 h-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}

              {filteredNotifications.length === 0 && (
                <EmptyState
                  icon={<BellOff className="w-8 h-8 text-muted-foreground" />}
                  title={t('notifications.empty')}
                  description={
                    filter === 'unread'
                      ? t('notifications.all_caught_up')
                      : t('notifications.nothing_to_show')
                  }
                />
              )}
            </div>
          )}
        </>
      )}

      {activeTab === 'settings' && (
        <Card className="overflow-hidden">
          <div className="p-6 border-b border-border">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  {t('notifications.preferences_title')}
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('notifications.preferences_description')}
                </p>
              </div>
              {(prefsLoading || savingPrefs) && (
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
              )}
            </div>
            {prefsError && <p className="text-sm text-destructive mt-3">{prefsError}</p>}
          </div>

          <div className="p-6 border-b border-border space-y-4">
            <h3 className="text-sm font-semibold text-foreground">
              {t('notifications.settings.channels')}
            </h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                <span className="text-sm flex items-center gap-2">
                  <Mail className="w-4 h-4" />
                  {t('notifications.settings.email')}
                </span>
                <Switch
                  checked={globalChannels.email_enabled}
                  onCheckedChange={() => void toggleGlobalChannel('email_enabled')}
                />
              </div>
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                <span className="text-sm flex items-center gap-2">
                  <Smartphone className="w-4 h-4" />
                  {t('notifications.settings.push')}
                </span>
                <Switch
                  checked={globalChannels.push_enabled}
                  onCheckedChange={() => void toggleGlobalChannel('push_enabled')}
                />
              </div>
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                <span className="text-sm flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" />
                  SMS
                </span>
                <Switch
                  checked={globalChannels.sms_enabled}
                  onCheckedChange={() => void toggleGlobalChannel('sms_enabled')}
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-[1fr,80px,80px,80px] gap-4 px-6 py-3 bg-surface border-b border-border">
            <div className="text-sm font-medium text-muted-foreground">
              {t('notifications.settings.notification_type')}
            </div>
            <div className="text-sm font-medium text-muted-foreground text-center flex items-center justify-center gap-1">
              <Mail className="w-4 h-4" />
              {t('notifications.settings.email')}
            </div>
            <div className="text-sm font-medium text-muted-foreground text-center flex items-center justify-center gap-1">
              <Smartphone className="w-4 h-4" />
              {t('notifications.settings.push')}
            </div>
            <div className="text-sm font-medium text-muted-foreground text-center flex items-center justify-center gap-1">
              <MessageSquare className="w-4 h-4" />
              {t('notifications.settings.in_app')}
            </div>
          </div>

          {preferences.map((pref) => (
            <div
              key={pref.id}
              className="grid grid-cols-[1fr,80px,80px,80px] gap-4 px-6 py-4 border-b border-border hover:bg-surface transition-colors"
            >
              <div>
                <p className="font-medium text-foreground">{pref.label}</p>
                <p className="text-sm text-muted-foreground mt-0.5">{pref.description}</p>
              </div>

              <div className="flex items-center justify-center">
                <Switch
                  checked={pref.email}
                  onCheckedChange={() => togglePreference(pref.id, 'email')}
                />
              </div>

              <div className="flex items-center justify-center">
                <Switch
                  checked={pref.push}
                  onCheckedChange={() => togglePreference(pref.id, 'push')}
                />
              </div>

              <div className="flex items-center justify-center">
                <Switch
                  checked={pref.inApp}
                  onCheckedChange={() => togglePreference(pref.id, 'inApp')}
                />
              </div>
            </div>
          ))}

          <div className="p-6 border-t border-border">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              {t('notifications.settings.sound_alerts')}
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Volume2 className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium text-foreground">
                      {t('notifications.settings.notification_sounds')}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {t('notifications.settings.notification_sounds_description')}
                    </p>
                  </div>
                </div>
                <Switch
                  checked={uiPrefs.soundEnabled}
                  onCheckedChange={(v) => updateUiPref('soundEnabled', v)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Bell className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium text-foreground">
                      {t('notifications.settings.desktop_notifications')}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {t('notifications.settings.desktop_notifications_description')}
                    </p>
                  </div>
                </div>
                <Switch
                  checked={uiPrefs.desktopEnabled}
                  onCheckedChange={(v) => updateUiPref('desktopEnabled', v)}
                />
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
