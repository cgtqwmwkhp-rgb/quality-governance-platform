import { FormEvent, useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Edit, Loader2, Plus, RefreshCw, Trash2, Webhook } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Card, CardContent } from '../../components/ui/Card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'
import { Input } from '../../components/ui/Input'
import { Switch } from '../../components/ui/Switch'
import {
  partnerWebhooksApi,
  type PartnerWebhookSubscription,
  type PartnerWebhookSubscriptionInput,
} from '../../services/api'

const PAGE_SIZE = 25

type SubscriptionForm = {
  name: string
  url: string
  secret: string
  events: string[]
  is_active: boolean
}

const EMPTY_FORM: SubscriptionForm = {
  name: '',
  url: '',
  secret: '',
  events: [],
  is_active: true,
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

export default function PartnerWebhooks() {
  const { t } = useTranslation()
  const [subscriptions, setSubscriptions] = useState<PartnerWebhookSubscription[]>([])
  const [events, setEvents] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<PartnerWebhookSubscription | null>(null)
  const [form, setForm] = useState<SubscriptionForm>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<PartnerWebhookSubscription | null>(null)

  const loadSubscriptions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await partnerWebhooksApi.listSubscriptions(offset, PAGE_SIZE)
      setSubscriptions(response.items)
      setTotal(response.total)
    } catch (loadError) {
      setError(getErrorMessage(loadError, t('admin.webhooks.load_error', 'Unable to load webhook subscriptions.')))
    } finally {
      setLoading(false)
    }
  }, [offset, t])

  useEffect(() => {
    void loadSubscriptions()
  }, [loadSubscriptions])

  useEffect(() => {
    let cancelled = false
    const loadEvents = async () => {
      try {
        const response = await partnerWebhooksApi.listEvents()
        if (!cancelled) setEvents(response.events)
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, t('admin.webhooks.events_error', 'Unable to load webhook events.')))
        }
      }
    }
    void loadEvents()
    return () => {
      cancelled = true
    }
  }, [t])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  const openEdit = (subscription: PartnerWebhookSubscription) => {
    setEditing(subscription)
    setForm({
      name: subscription.name || '',
      url: subscription.url,
      secret: '',
      events: subscription.events,
      is_active: subscription.is_active,
    })
    setDialogOpen(true)
  }

  const toggleEvent = (event: string) => {
    setForm((current) => ({
      ...current,
      events: current.events.includes(event)
        ? current.events.filter((selected) => selected !== event)
        : [...current.events, event],
    }))
  }

  const saveSubscription = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!form.url || !form.events.length || (!editing && form.secret.length < 16)) {
      setError(
        t(
          'admin.webhooks.validation_error',
          'Enter a valid URL, select at least one event, and provide a secret of at least 16 characters.',
        ),
      )
      return
    }

    setSaving(true)
    setError(null)
    try {
      const baseInput: PartnerWebhookSubscriptionInput = {
        name: form.name.trim() || null,
        url: form.url.trim(),
        events: form.events,
        is_active: form.is_active,
      }
      if (editing) {
        if (form.secret) baseInput.secret = form.secret
        await partnerWebhooksApi.updateSubscription(editing.id, baseInput)
      } else {
        await partnerWebhooksApi.createSubscription({ ...baseInput, secret: form.secret })
      }
      setDialogOpen(false)
      await loadSubscriptions()
    } catch (saveError) {
      setError(getErrorMessage(saveError, t('admin.webhooks.save_error', 'Unable to save webhook subscription.')))
    } finally {
      setSaving(false)
    }
  }

  const setActive = async (subscription: PartnerWebhookSubscription, isActive: boolean) => {
    setError(null)
    try {
      await partnerWebhooksApi.updateSubscription(subscription.id, {
        name: subscription.name,
        url: subscription.url,
        events: subscription.events,
        is_active: isActive,
      })
      await loadSubscriptions()
    } catch (saveError) {
      setError(getErrorMessage(saveError, t('admin.webhooks.save_error', 'Unable to save webhook subscription.')))
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setSaving(true)
    setError(null)
    try {
      await partnerWebhooksApi.deleteSubscription(deleteTarget.id)
      setDeleteTarget(null)
      if (subscriptions.length === 1 && offset > 0) setOffset(Math.max(0, offset - PAGE_SIZE))
      else await loadSubscriptions()
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, t('admin.webhooks.delete_error', 'Unable to delete webhook subscription.')))
    } finally {
      setSaving(false)
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('admin.webhooks.title', 'Partner webhooks')}</h1>
          <p className="mt-1 text-muted-foreground">
            {t('admin.webhooks.subtitle', 'Create and manage tenant-scoped partner event subscriptions.')}
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="w-4 h-4" />
          {t('admin.webhooks.add', 'Add webhook')}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <p className="text-sm text-muted-foreground">
              {t('admin.webhooks.total', '{{count}} subscriptions', { count: total })}
            </p>
            <Button variant="ghost" size="sm" onClick={() => void loadSubscriptions()} disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              {t('common.refresh', 'Refresh')}
            </Button>
          </div>

          {loading ? (
            <div className="flex justify-center py-16" aria-label={t('common.loading', 'Loading')}>
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : subscriptions.length === 0 ? (
            <div className="py-16 text-center">
              <Webhook className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
              <p className="font-medium">{t('admin.webhooks.empty_title', 'No webhook subscriptions')}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('admin.webhooks.empty_subtitle', 'Add a webhook to deliver supported partner events.')}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {subscriptions.map((subscription) => (
                <div key={subscription.id} className="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h2 className="truncate font-medium">{subscription.name || subscription.url}</h2>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          subscription.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {subscription.is_active
                          ? t('admin.webhooks.active', 'Active')
                          : t('admin.webhooks.inactive', 'Inactive')}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{subscription.url}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {subscription.events.map((event) => (
                        <span key={event} className="rounded bg-surface px-2 py-0.5 text-xs text-muted-foreground">
                          {event}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={subscription.is_active}
                      onCheckedChange={(checked) => void setActive(subscription, checked)}
                      aria-label={t('admin.webhooks.toggle', 'Toggle webhook subscription')}
                    />
                    <Button variant="ghost" size="icon" onClick={() => openEdit(subscription)} aria-label={t('common.edit', 'Edit')}>
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(subscription)}
                      aria-label={t('common.delete', 'Delete')}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {t('a11y.page_of', 'Page {{current}} of {{total}}', { current: page, total: pageCount })}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={offset === 0 || loading} onClick={() => setOffset(offset - PAGE_SIZE)}>
            {t('common.previous', 'Previous')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            {t('common.next', 'Next')}
          </Button>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? t('admin.webhooks.edit', 'Edit webhook') : t('admin.webhooks.add', 'Add webhook')}
            </DialogTitle>
            <DialogDescription>
              {t('admin.webhooks.form_help', 'The signing secret is write-only and is never returned after saving.')}
            </DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={(event) => void saveSubscription(event)}>
            <label className="block space-y-1 text-sm font-medium">
              {t('admin.webhooks.name', 'Name')}
              <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              {t('admin.webhooks.url', 'Endpoint URL')}
              <Input
                type="url"
                required
                placeholder="https://partner.example/webhooks"
                value={form.url}
                onChange={(event) => setForm({ ...form, url: event.target.value })}
              />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              {t('admin.webhooks.secret', 'Signing secret')}
              <Input
                type="password"
                required={!editing}
                minLength={editing ? undefined : 16}
                placeholder={editing ? t('admin.webhooks.secret_unchanged', 'Leave blank to keep unchanged') : undefined}
                value={form.secret}
                onChange={(event) => setForm({ ...form, secret: event.target.value })}
              />
            </label>
            <fieldset>
              <legend className="text-sm font-medium">{t('admin.webhooks.events', 'Events')}</legend>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {events.map((event) => (
                  <label key={event} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.events.includes(event)}
                      onChange={() => toggleEvent(event)}
                      className="rounded border-border"
                    />
                    {event}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="flex items-center gap-2 text-sm font-medium">
              <Switch checked={form.is_active} onCheckedChange={(checked) => setForm({ ...form, is_active: checked })} />
              {t('admin.webhooks.enabled', 'Enabled')}
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button type="submit" disabled={saving || events.length === 0}>
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                {t('common.save', 'Save')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.webhooks.delete_title', 'Delete webhook?')}</DialogTitle>
            <DialogDescription>
              {t('admin.webhooks.delete_description', 'This permanently removes the subscription and its delivery history.')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={saving}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button variant="destructive" onClick={() => void confirmDelete()} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {t('common.delete', 'Delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
