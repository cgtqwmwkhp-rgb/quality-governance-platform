import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { CalendarClock, Plus } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { ErrorState } from '../components/ui/async'
import { getCurrentUserId } from '../utils/auth'
import { complianceScheduleApi, getApiErrorMessage } from '../api/client'
import type {
  CatalogueTemplate,
  ComplianceRequirement,
  ComplianceScheduleStats,
  ComplianceStatus,
} from '../api/complianceScheduleClient'
import { ownershipOf, statusChipClass, statusLabel, type Ownership } from './complianceScheduleHelpers'
import { toast } from '../contexts/ToastContext'

export default function ComplianceSchedule() {
  const { t } = useTranslation()
  const [items, setItems] = useState<ComplianceRequirement[]>([])
  const [stats, setStats] = useState<ComplianceScheduleStats | null>(null)
  const [catalogue, setCatalogue] = useState<CatalogueTemplate[]>([])
  const [statusFilter, setStatusFilter] = useState<ComplianceStatus | ''>('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activating, setActivating] = useState<string | null>(null)
  const currentUserId = useMemo(() => getCurrentUserId(), [])

  const ownershipLabel = (ownership: Ownership): string => {
    if (ownership === 'you') return t('compliance.schedule.owner.you', 'Owned by you')
    if (ownership === 'other') return t('compliance.schedule.owner.other', 'Owned by someone else')
    return t('compliance.schedule.owner.unassigned', 'Unassigned')
  }

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [listRes, statsRes, catRes] = await Promise.all([
        complianceScheduleApi.listRequirements({
          is_active: true,
          status: statusFilter || undefined,
          page_size: 100,
        }),
        complianceScheduleApi.getStats(),
        complianceScheduleApi.listCatalogue(),
      ])
      setItems(listRes.data.items)
      setStats(statsRes.data)
      setCatalogue(catRes.data.items)
    } catch (err) {
      // Cleared so no stale register is left on screen under a failure notice,
      // which would misreport how many obligations there are.
      setItems([])
      setStats(null)
      setCatalogue([])
      setLoadError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  const activate = async (key: string) => {
    setActivating(key)
    try {
      const nextDue = new Date()
      nextDue.setUTCMonth(nextDue.getUTCMonth() + 1)
      await complianceScheduleApi.activateCatalogue(key, {
        next_due_date: nextDue.toISOString().slice(0, 10),
        // An obligation with no owner falls back to whoever holds the admin role,
        // and in an estate where nobody holds it the reminder reaches no one at
        // all. Defaulting to the person activating it means someone is always
        // told; the row shows who, so it can be reassigned rather than assumed.
        owner_id: currentUserId ?? undefined,
      })
      toast.success(t('compliance.schedule.activate.success', 'Requirement activated'))
      await load()
    } catch {
      toast.error(t('compliance.schedule.activate.error', 'Could not activate template'))
    } finally {
      setActivating(null)
    }
  }

  return (
    <div className="space-y-6" data-testid="compliance-schedule-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <CalendarClock className="h-6 w-6" />
            {t('compliance.schedule.title', 'Compliance Schedule')}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t(
              'compliance.schedule.subtitle',
              'Organisation and location obligations — Current, Due soon, or Overdue.',
            )}
          </p>
        </div>
        <div className="flex gap-2">
          {(['', 'current', 'due_soon', 'overdue'] as const).map((s) => (
            <Button
              key={s || 'all'}
              variant={statusFilter === s ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(s)}
              data-testid={`compliance-schedule-filter-${s || 'all'}`}
            >
              {s ? statusLabel(s) : t('compliance.schedule.filter.all', 'All')}
            </Button>
          ))}
        </div>
      </div>

      {loadError ? (
        <ErrorState
          title={t('compliance.schedule.load_error', 'Could not load Compliance Schedule')}
          description={t(
            'compliance.schedule.load_error_hint',
            'The register could not be read, so this is not a statement that you have no obligations. Nothing has been changed.',
          )}
          message={loadError}
          onRetry={() => void load()}
          retryLabel={t('common.retry', 'Try again')}
          data-testid="compliance-schedule-load-error"
        />
      ) : (
        <>
          {stats && (
            <div
              className="grid grid-cols-2 md:grid-cols-4 gap-3"
              data-testid="compliance-schedule-stats"
            >
              {(
                [
                  ['total_active', t('compliance.schedule.stats.active', 'Active')],
                  ['current', t('compliance.schedule.status.current', 'Current')],
                  ['due_soon', t('compliance.schedule.status.due_soon', 'Due soon')],
                  ['overdue', t('compliance.schedule.status.overdue', 'Overdue')],
                ] as const
              ).map(([key, label]) => (
                <div key={key} className="rounded-lg border border-border bg-card px-4 py-3">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="text-2xl font-semibold mt-1">{stats[key]}</div>
                </div>
              ))}
            </div>
          )}

          <section className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3 font-medium">
              {t('compliance.schedule.requirements', 'Requirements')}
            </div>
            {loading ? (
              <p className="p-6 text-sm text-muted-foreground">
                {t('common.loading', 'Loading…')}
              </p>
            ) : items.length === 0 ? (
              <div
                className="p-6 text-sm text-muted-foreground"
                data-testid="compliance-schedule-empty"
              >
                {t(
                  'compliance.schedule.empty',
                  'No active requirements yet. Activate a catalogue template below.',
                )}
              </div>
            ) : (
              <ul className="divide-y divide-border" data-testid="compliance-schedule-list">
                {items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <Link
                        to={`/compliance-schedule/${item.id}`}
                        className="font-medium text-foreground hover:underline"
                        data-testid={`compliance-schedule-row-${item.id}`}
                      >
                        {item.title}
                      </Link>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {item.reference_number} · {t('compliance.schedule.due', 'Due')}{' '}
                        {item.next_due_date} ·{' '}
                        <span data-testid={`compliance-schedule-owner-${item.id}`}>
                          {ownershipLabel(ownershipOf(item.owner_id, currentUserId))}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${statusChipClass(item.status)}`}
                    >
                      {statusLabel(item.status)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3 font-medium">
              {t('compliance.schedule.catalogue', 'Catalogue')}
            </div>
            <ul className="divide-y divide-border" data-testid="compliance-schedule-catalogue">
              {catalogue.map((tpl) => (
                <li
                  key={tpl.template_key}
                  className="flex items-center justify-between gap-3 px-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="font-medium">{tpl.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {tpl.template_key}
                      {tpl.statutory
                        ? ` · ${t('compliance.schedule.statutory', 'Statutory')}`
                        : ''}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={activating === tpl.template_key}
                    onClick={() => void activate(tpl.template_key)}
                    data-testid={`compliance-schedule-activate-${tpl.template_key}`}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    {t('compliance.schedule.activate', 'Activate')}
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}
