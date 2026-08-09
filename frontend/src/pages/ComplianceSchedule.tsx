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
  LocationCoverageGaps,
} from '../api/complianceScheduleClient'
import { ownershipOf, statusChipClass, statusLabel } from './complianceScheduleHelpers'
import { useOwnershipLabel } from './compliance/useOwnershipLabel'
import { RequirementFormDialog } from './compliance/RequirementFormDialog'
import { coverageCopy } from './complianceScheduleCoverageI18n'
import { importCopy } from './complianceScheduleImportI18n'
import { toast } from '../contexts/ToastContext'
import type {
  ComplianceImportValidationReport,
} from '../api/complianceScheduleClient'

export default function ComplianceSchedule() {
  const { t, i18n } = useTranslation()
  const cov = coverageCopy(i18n.language)
  const imp = importCopy(i18n.language)
  const [items, setItems] = useState<ComplianceRequirement[]>([])
  const [stats, setStats] = useState<ComplianceScheduleStats | null>(null)
  const [coverage, setCoverage] = useState<LocationCoverageGaps | null>(null)
  const [catalogue, setCatalogue] = useState<CatalogueTemplate[]>([])
  const [statusFilter, setStatusFilter] = useState<ComplianceStatus | ''>('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activating, setActivating] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importReport, setImportReport] = useState<ComplianceImportValidationReport | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  // Active and retired obligations are two views rather than one mixed list,
  // because the API's is_active filter is a plain boolean defaulting to true —
  // there is no value that means "both", so a combined list is not available to
  // ask for.
  const [showInactive, setShowInactive] = useState(false)
  const currentUserId = useMemo(() => getCurrentUserId(), [])
  const ownershipLabel = useOwnershipLabel()

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [listRes, statsRes, catRes] = await Promise.all([
        complianceScheduleApi.listRequirements({
          is_active: !showInactive,
          status: statusFilter || undefined,
          page_size: 100,
        }),
        complianceScheduleApi.getStats(),
        complianceScheduleApi.listCatalogue(),
      ])
      setItems(listRes.data.items)
      setStats(statsRes.data)
      setCatalogue(catRes.data.items)
      try {
        const coverageRes = await complianceScheduleApi.getLocationCoverageGaps()
        setCoverage(coverageRes.data)
      } catch {
        // Soft-fail: coverage is additive Wave 3; do not blank the register.
        setCoverage(null)
      }
    } catch (err) {
      // Cleared so no stale register is left on screen under a failure notice,
      // which would misreport how many obligations there are.
      setItems([])
      setStats(null)
      setCatalogue([])
      setCoverage(null)
      setLoadError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [statusFilter, showInactive])

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
    } catch (err) {
      // Activation now refuses a template already live at this location, and the
      // refusal names the obligation that already covers it. A fixed string here
      // would discard that and leave the user pressing a button that keeps
      // failing for reasons the server has already explained.
      toast.error(
        getApiErrorMessage(
          err,
          t('compliance.schedule.activate.error', 'Could not activate template'),
        ),
      )
    } finally {
      setActivating(null)
    }
  }

  const runImportDryRun = async () => {
    if (!importFile) {
      toast.error(imp.emptyFile)
      return
    }
    setImportBusy(true)
    try {
      const res = await complianceScheduleApi.importDryRun(importFile)
      setImportReport(res.data)
      if (!res.data.ok) toast.error(imp.blocked)
    } catch (err) {
      toast.error(getApiErrorMessage(err, imp.blocked))
    } finally {
      setImportBusy(false)
    }
  }

  const runImportCommit = async () => {
    if (!importFile || !importReport?.ok) {
      toast.error(imp.blocked)
      return
    }
    setImportBusy(true)
    try {
      await complianceScheduleApi.importCommit(importFile)
      toast.success(imp.success)
      setImportOpen(false)
      setImportFile(null)
      setImportReport(null)
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err, imp.blocked))
    } finally {
      setImportBusy(false)
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
        <div className="flex flex-wrap items-center gap-2">
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
          <Button
            variant={showInactive ? 'default' : 'outline'}
            size="sm"
            aria-pressed={showInactive}
            onClick={() => setShowInactive((v) => !v)}
            data-testid="compliance-schedule-toggle-inactive"
          >
            {t('compliance.schedule.filter.inactive', 'Retired')}
          </Button>
          {!showInactive && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setImportOpen(true)
                setImportReport(null)
              }}
              data-testid="compliance-schedule-import-csv-button"
            >
              {imp.button}
            </Button>
          )}
          {!showInactive && (
            <Button
              size="sm"
              onClick={() => setFormOpen(true)}
              data-testid="compliance-schedule-add"
            >
              <Plus className="h-4 w-4 mr-1" />
              {t('compliance.schedule.form.create', 'Add obligation')}
            </Button>
          )}
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
          {stats && !showInactive && (
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
              {showInactive
                ? t('compliance.schedule.retired_requirements', 'Retired obligations')
                : t('compliance.schedule.requirements', 'Requirements')}
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
                {showInactive
                  ? t(
                      'compliance.schedule.empty_inactive',
                      'Nothing has been retired. Obligations you retire are kept here and can be reactivated.',
                    )
                  : t(
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
                          {ownershipLabel(
                            ownershipOf(item.owner_id, currentUserId),
                            item.owner_name,
                          )}
                        </span>
                      </div>
                    </div>
                    {showInactive ? (
                      // A retired obligation still carries a computed status, and
                      // labelling it "Overdue" would claim a breach that is not
                      // being tracked and will not be notified. The view is keyed
                      // on rather than the row's own flag because the request
                      // filtered on is_active, so every row here is retired by
                      // construction — no row can disagree with the heading.
                      <span
                        className="shrink-0 rounded bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground"
                        data-testid={`compliance-schedule-retired-${item.id}`}
                      >
                        {t('compliance.schedule.filter.inactive', 'Retired')}
                      </span>
                    ) : (
                      <span
                        className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${statusChipClass(item.status)}`}
                      >
                        {statusLabel(item.status)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {coverage && !showInactive && (
            <section
              className="rounded-lg border border-border bg-card"
              data-testid="compliance-schedule-coverage-gaps"
            >
              <div className="border-b border-border px-4 py-3">
                <div className="font-medium">{cov.title}</div>
                <p className="text-xs text-muted-foreground mt-1">{cov.subtitle}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>
                    {cov.locations}: {coverage.total_locations}
                  </span>
                  <span>
                    {cov.missingFra}: {coverage.missing_fra}
                  </span>
                  <span>
                    {cov.missingDrill}: {coverage.missing_fire_drill}
                  </span>
                  <span>
                    {cov.missingBoth}: {coverage.missing_both}
                  </span>
                </div>
              </div>
              {coverage.items.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted-foreground">{cov.emptyLocations}</p>
              ) : (
                <ul className="divide-y divide-border">
                  {coverage.items.map((row) => (
                    <li
                      key={row.location_id}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                      data-testid={`compliance-schedule-coverage-${row.location_id}`}
                    >
                      <div className="min-w-0">
                        <div className="font-medium">{row.location_name}</div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          #{row.location_id} · {row.location_kind}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span
                          className={
                            row.missing_fra
                              ? 'rounded bg-destructive/10 px-2 py-0.5 font-medium text-destructive'
                              : 'rounded bg-muted px-2 py-0.5 text-muted-foreground'
                          }
                        >
                          {row.missing_fra ? cov.gapFra : cov.okFra}
                        </span>
                        <span
                          className={
                            row.missing_fire_drill
                              ? 'rounded bg-destructive/10 px-2 py-0.5 font-medium text-destructive'
                              : 'rounded bg-muted px-2 py-0.5 text-muted-foreground'
                          }
                        >
                          {row.missing_fire_drill ? cov.gapDrill : cov.okDrill}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {!showInactive && (
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
          )}
        </>
      )}

      <RequirementFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSaved={() => void load()}
      />

      {importOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          data-testid="compliance-schedule-import-dialog"
        >
          <div className="w-full max-w-lg rounded-lg border border-border bg-card p-4 shadow-lg space-y-3">
            <div className="font-medium">{imp.title}</div>
            <p className="text-xs text-muted-foreground">{imp.subtitle}</p>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                setImportFile(e.target.files?.[0] ?? null)
                setImportReport(null)
              }}
              data-testid="compliance-schedule-import-file"
            />
            {importReport && (
              <div className="text-xs space-y-1 rounded border border-border p-2">
                <div>
                  {imp.creates}: {importReport.creates} · {imp.errors}:{' '}
                  {importReport.error_rows}
                </div>
                {importReport.errors.slice(0, 5).map((err) => (
                  <div key={`${err.row}-${err.code}`} className="text-destructive">
                    Row {err.row}: {err.message}
                  </div>
                ))}
              </div>
            )}
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={importBusy}
                onClick={() => {
                  setImportOpen(false)
                  setImportFile(null)
                  setImportReport(null)
                }}
              >
                {imp.cancel}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={importBusy}
                onClick={() => void runImportDryRun()}
                data-testid="compliance-schedule-import-dry-run"
              >
                {imp.dryRun}
              </Button>
              <Button
                size="sm"
                disabled={importBusy || !importReport?.ok}
                onClick={() => void runImportCommit()}
                data-testid="compliance-schedule-import-commit"
              >
                {imp.commit}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
