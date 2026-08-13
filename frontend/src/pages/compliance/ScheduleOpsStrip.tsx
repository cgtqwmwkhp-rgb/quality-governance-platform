import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { complianceScheduleApi, getApiErrorMessage } from '../../api/client'
import { Badge } from '../../components/ui'
import { pickSoonestMatchingObligation, type ScheduleOpsPick } from './scheduleOpsPick'

/**
 * Workspace read of Compliance Schedule SoR: owner, days-to-due, existing
 * 60/30/7 notify band. Does not write, does not fork cell-aggregate.
 */
export function ScheduleOpsStrip({ clauseNumber }: { clauseNumber: string }) {
  const { t } = useTranslation()
  const [pick, setPick] = useState<ScheduleOpsPick | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoaded(false)
    setError(null)
    void (async () => {
      try {
        const res = await complianceScheduleApi.listRequirements({ is_active: true })
        if (cancelled) return
        const today = new Date().toISOString().slice(0, 10)
        setPick(pickSoonestMatchingObligation(res.data.items ?? [], clauseNumber, today))
      } catch (err) {
        if (cancelled) return
        setPick(null)
        setError(getApiErrorMessage(err))
      } finally {
        if (!cancelled) setLoaded(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [clauseNumber])

  if (!loaded && !error) {
    return (
      <p className="text-xs text-muted-foreground" data-testid="workspace-schedule-ops-loading">
        {t('compliance.standards_workspace.schedule_ops.loading', {
          defaultValue: 'Loading Schedule obligation…',
        })}
      </p>
    )
  }

  if (error) {
    return (
      <p className="text-xs text-warning" role="status" data-testid="workspace-schedule-ops-error">
        {t('compliance.standards_workspace.schedule_ops.error', {
          defaultValue: 'Schedule obligation could not be loaded. Use Open Compliance Schedule.',
        })}
      </p>
    )
  }

  if (!pick) {
    return (
      <p className="text-xs text-muted-foreground" data-testid="workspace-schedule-ops-empty">
        {t('compliance.standards_workspace.schedule_ops.empty', {
          defaultValue: 'No matching Schedule obligation for this clause. Schedule remains the register.',
        })}
      </p>
    )
  }

  const daysLabel =
    pick.days_remaining < 0
      ? t('compliance.standards_workspace.schedule_ops.overdue_days', {
          defaultValue: '{{days}}d overdue',
          days: Math.abs(pick.days_remaining),
        })
      : t('compliance.standards_workspace.schedule_ops.days', {
          defaultValue: '{{days}}d to due',
          days: pick.days_remaining,
        })

  const notifyLabel = {
    none: t('compliance.standards_workspace.schedule_ops.notify_none', {
      defaultValue: 'Notify window not open',
    }),
    due_60: t('compliance.standards_workspace.schedule_ops.notify_due_60', {
      defaultValue: 'Notify ≤60d',
    }),
    due_30: t('compliance.standards_workspace.schedule_ops.notify_due_30', {
      defaultValue: 'Notify ≤30d',
    }),
    due_7: t('compliance.standards_workspace.schedule_ops.notify_due_7', {
      defaultValue: 'Notify ≤7d',
    }),
    overdue: t('compliance.standards_workspace.schedule_ops.notify_overdue', {
      defaultValue: 'Overdue — reminder due',
    }),
  }[pick.notify_band]

  return (
    <div
      className="flex flex-wrap items-center gap-2 text-xs"
      data-testid="workspace-schedule-ops"
    >
      <span className="font-medium text-muted-foreground uppercase tracking-wide">
        {t('compliance.standards_workspace.schedule_ops.title', { defaultValue: 'Schedule' })}
      </span>
      <Badge variant="outline" data-testid="workspace-schedule-ops-ref">
        {pick.reference_number}
      </Badge>
      <span data-testid="workspace-schedule-ops-owner">
        {pick.owner_name ??
          t('compliance.standards_workspace.schedule_ops.unassigned', { defaultValue: 'Unassigned' })}
      </span>
      <Badge variant="outline" data-testid="workspace-schedule-ops-days">
        {daysLabel}
      </Badge>
      <Badge
        variant={pick.notify_band === 'overdue' || pick.notify_band === 'due_7' ? 'destructive' : 'secondary'}
        data-testid="workspace-schedule-ops-notify"
        data-band={pick.notify_band}
      >
        {notifyLabel}
      </Badge>
    </div>
  )
}
