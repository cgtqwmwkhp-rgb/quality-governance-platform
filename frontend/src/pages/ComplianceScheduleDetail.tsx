import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { complianceScheduleApi } from '../api/client'
import { getCurrentUserId } from '../utils/auth'
import type { ComplianceRecord, ComplianceRequirement } from '../api/complianceScheduleClient'
import {
  anchorHint,
  anchorLabel,
  frequencyLabel,
  ownershipOf,
  statusChipClass,
  statusLabel,
} from './complianceScheduleHelpers'
import { useOwnershipLabel } from './compliance/useOwnershipLabel'
import { RecordCompletionSheet } from './compliance/RecordCompletionSheet'
import { RequirementFormDialog } from './compliance/RequirementFormDialog'
import { RequirementLifecycleControls } from './compliance/RequirementLifecycleControls'
import { RecordEvidenceSection } from './compliance/RecordEvidenceSection'
import { RecordFilingControl } from './compliance/RecordFilingControl'
import { toast } from '../contexts/ToastContext'

export default function ComplianceScheduleDetail() {
  const { id } = useParams<{ id: string }>()
  const requirementId = Number(id)
  const { t } = useTranslation()
  const currentUserId = useMemo(() => getCurrentUserId(), [])
  const ownershipLabel = useOwnershipLabel()
  const [requirement, setRequirement] = useState<ComplianceRequirement | null>(null)
  const [records, setRecords] = useState<ComplianceRecord[]>([])
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!Number.isFinite(requirementId)) return
    setLoading(true)
    try {
      const [reqRes, recRes] = await Promise.all([
        complianceScheduleApi.getRequirement(requirementId),
        complianceScheduleApi.listRecords(requirementId, { page_size: 50 }),
      ])
      setRequirement(reqRes.data)
      setRecords(recRes.data.items)
    } catch {
      toast.error(t('compliance.schedule.detail.load_error', 'Could not load requirement'))
      setRequirement(null)
    } finally {
      setLoading(false)
    }
  }, [requirementId, t])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return <p className="p-6 text-sm text-muted-foreground">{t('common.loading', 'Loading…')}</p>
  }

  if (!requirement) {
    return (
      <div className="p-6" data-testid="compliance-schedule-detail-missing">
        <p className="text-sm text-muted-foreground">
          {t('compliance.schedule.detail.not_found', 'Requirement not found')}
        </p>
        <Link to="/compliance-schedule" className="text-sm underline mt-2 inline-block">
          {t('compliance.schedule.back', 'Back to schedule')}
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6" data-testid="compliance-schedule-detail">
      <div>
        <Link
          to="/compliance-schedule"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('compliance.schedule.back', 'Back to schedule')}
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{requirement.title}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {requirement.reference_number} · {requirement.taxonomy_id}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${statusChipClass(requirement.status)}`}
            >
              {statusLabel(requirement.status)}
            </span>
            {requirement.is_active && (
              <>
                <Button
                  variant="outline"
                  data-testid="compliance-schedule-open-edit"
                  onClick={() => setEditOpen(true)}
                >
                  {t('compliance.schedule.edit.cta', 'Edit')}
                </Button>
                <Button
                  data-testid="compliance-schedule-open-complete"
                  onClick={() => setSheetOpen(true)}
                >
                  {t('compliance.schedule.complete.cta', 'Record completion')}
                </Button>
              </>
            )}
            <RequirementLifecycleControls requirement={requirement} onChanged={() => void load()} />
          </div>
        </div>
      </div>

      {!requirement.is_active && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
          data-testid="compliance-schedule-inactive-banner"
        >
          <p className="font-medium">
            {t('compliance.schedule.inactive.banner_title', 'This obligation is retired')}
          </p>
          <p className="mt-1">
            {t(
              'compliance.schedule.inactive.banner_body',
              'It is off the active register and generates no reminders. Its history below is unchanged. Reactivate it to put it back on the schedule.',
            )}
          </p>
        </div>
      )}

      {requirement.description && (
        <p
          className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
          data-testid="compliance-schedule-detail-description"
        >
          {requirement.description}
        </p>
      )}

      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-lg border border-border bg-card p-4 text-sm">
        <div>
          <dt className="text-muted-foreground">{t('compliance.schedule.due', 'Due')}</dt>
          <dd className="font-medium mt-0.5">{requirement.next_due_date}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('compliance.schedule.last_completed', 'Last completed')}
          </dt>
          <dd className="font-medium mt-0.5">
            {requirement.last_completed_at
              ? new Date(requirement.last_completed_at).toLocaleString()
              : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('compliance.schedule.frequency', 'Frequency')}
          </dt>
          <dd className="font-medium mt-0.5" data-testid="compliance-schedule-detail-frequency">
            {frequencyLabel(requirement.frequency_months, requirement.frequency_days) ??
              t('compliance.schedule.frequency.none', 'No fixed interval')}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t('compliance.schedule.anchor', 'Anchor')}</dt>
          <dd className="font-medium mt-0.5" data-testid="compliance-schedule-detail-anchor">
            {anchorLabel(requirement.anchor)}
          </dd>
          {anchorHint(requirement.anchor) && (
            <p className="text-xs text-muted-foreground mt-0.5">{anchorHint(requirement.anchor)}</p>
          )}
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('compliance.schedule.statutory_status', 'Statutory')}
          </dt>
          <dd className="font-medium mt-0.5" data-testid="compliance-schedule-detail-statutory">
            {requirement.statutory
              ? t('compliance.schedule.statutory.yes', 'Required by law')
              : t('compliance.schedule.statutory.no', 'Not a statutory obligation')}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t('compliance.schedule.owner', 'Owner')}</dt>
          <dd className="font-medium mt-0.5" data-testid="compliance-schedule-detail-owner">
            {ownershipLabel(ownershipOf(requirement.owner_id, currentUserId))}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('compliance.schedule.regulatory_basis', 'Regulatory basis')}
          </dt>
          <dd className="font-medium mt-0.5">{requirement.regulatory_basis || '—'}</dd>
        </div>
        {requirement.location_id != null && (
          <div>
            <dt className="text-muted-foreground">
              {t('compliance.schedule.location', 'Location')}
            </dt>
            {/* The register has no name for this id without reaching into the
                safety-assets module, which sits behind a different permission.
                Showing the reference is honest; hiding a site-scoped obligation
                would not be. */}
            <dd className="font-medium mt-0.5" data-testid="compliance-schedule-detail-location">
              #{requirement.location_id}
            </dd>
          </div>
        )}
      </dl>

      <section className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3 font-medium">
          {t('compliance.schedule.records', 'Occurrence records')}
        </div>
        {records.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground space-y-1">
            <p data-testid="compliance-schedule-records-empty">
              {t('compliance.schedule.records.empty', 'No completed or missed occurrences yet.')}
            </p>
            <p data-testid="compliance-schedule-evidence-needs-record">
              {t(
                'compliance.schedule.evidence.needs_record',
                'Evidence attaches to an occurrence once one is recorded — not to the obligation itself.',
              )}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border" data-testid="compliance-schedule-records">
            {records.map((rec) => (
              <li key={rec.id} className="px-4 py-3 text-sm">
                <div className="font-medium">
                  {rec.reference_number} · {rec.outcome}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {t('compliance.schedule.due', 'Due')} {rec.due_date}
                  {rec.completed_at ? ` · ${new Date(rec.completed_at).toLocaleString()}` : ''}
                </div>
                <RecordEvidenceSection recordId={rec.id} referenceNumber={rec.reference_number} />
                <RecordFilingControl record={rec} onFiled={() => void load()} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <RecordCompletionSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        requirementId={requirement.id}
        requirementTitle={requirement.title}
        nextDueDate={requirement.next_due_date}
        onCompleted={() => void load()}
      />

      <RequirementFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        requirement={requirement}
        onSaved={() => void load()}
      />
    </div>
  )
}
