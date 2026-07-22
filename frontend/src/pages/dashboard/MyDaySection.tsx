import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  GraduationCap,
  ShieldAlert,
  Truck,
  Wrench,
  Zap,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'
import type { MyDayData } from './useDashboardData'
import type { PortalClearState } from '../../api/portalComplianceClient'

function clearStateCopy(state: PortalClearState): {
  title: string
  icon: React.ElementType
  tone: string
} {
  if (state === 'blocked') {
    return { title: 'Not clear to work', icon: ShieldAlert, tone: 'text-destructive' }
  }
  if (state === 'attention') {
    return { title: 'Needs attention', icon: AlertTriangle, tone: 'text-warning' }
  }
  return { title: 'Clear to work', icon: CheckCircle2, tone: 'text-success' }
}

function Unavailable({ label }: { label: string }) {
  return <p className="text-sm text-muted-foreground">{label} unavailable right now.</p>
}

/**
 * My Day — stage-first section for any user linked to an engineer profile
 * (locked design §2/§5). Mirrors the Portal.tsx clear-to-work visual
 * language so the same status reads consistently between the field portal
 * and the admin dashboard.
 */
export function MyDaySection({ data }: { data: MyDayData }) {
  const { compliance, trainingTotal, trainingGapCount, actionCounts } = data

  return (
    <Card data-testid="my-day-section" className="border-primary/20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          My Day
          <span className="text-xs font-normal text-muted-foreground">
            Your assets, training, and actions
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Clear-to-work (assets + van) */}
        <Link
          to="/portal/tools"
          data-testid="my-day-clear-to-work"
          className={cn(
            'rounded-xl border-2 p-4 transition-colors hover:border-primary/40',
            compliance.status === 'ok' &&
              compliance.value.clear_state === 'blocked' &&
              'border-destructive/40 bg-destructive/5',
            compliance.status === 'ok' &&
              compliance.value.clear_state === 'attention' &&
              'border-warning/40 bg-warning/5',
            compliance.status === 'ok' &&
              compliance.value.clear_state === 'clear' &&
              'border-success/30 bg-success/5',
            compliance.status !== 'ok' && 'border-border bg-surface',
          )}
        >
          <div className="flex items-start gap-3">
            <Wrench className="h-5 w-5 shrink-0 text-primary" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-muted-foreground">Assets &amp; van</p>
              {compliance.status === 'ok' ? (
                <>
                  {(() => {
                    const copy = clearStateCopy(compliance.value.clear_state)
                    const Icon = copy.icon
                    return (
                      <p className={cn('mt-1 flex items-center gap-1.5 font-semibold', copy.tone)}>
                        <Icon className="h-4 w-4" aria-hidden />
                        {copy.title}
                      </p>
                    )
                  })()}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {compliance.value.tool_summary.overdue} asset overdue ·{' '}
                    {compliance.value.van_summary.defect_counts.total} open van fault
                    {compliance.value.van_summary.defect_counts.total === 1 ? '' : 's'}
                  </p>
                </>
              ) : (
                <Unavailable label="Asset &amp; van status" />
              )}
            </div>
          </div>
        </Link>

        {/* Training */}
        <Link
          to="/portal/work#training"
          data-testid="my-day-training"
          className="rounded-xl border-2 border-border p-4 transition-colors hover:border-primary/40 hover:bg-muted/40"
        >
          <div className="flex items-start gap-3">
            <GraduationCap className="h-5 w-5 shrink-0 text-primary" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-muted-foreground">Training</p>
              {trainingTotal.status === 'ok' && trainingGapCount.status === 'ok' ? (
                <>
                  <p className="mt-1 font-semibold text-foreground">
                    {trainingTotal.value - trainingGapCount.value} / {trainingTotal.value} modules
                    OK
                  </p>
                  {trainingGapCount.value > 0 ? (
                    <p className="mt-1 text-xs text-warning">
                      {trainingGapCount.value} overdue module
                      {trainingGapCount.value === 1 ? '' : 's'}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-muted-foreground">
                      All required modules on track
                    </p>
                  )}
                </>
              ) : (
                <Unavailable label="Training status" />
              )}
            </div>
          </div>
        </Link>

        {/* My actions */}
        <Link
          to="/actions?view=my"
          data-testid="my-day-actions"
          className="rounded-xl border-2 border-border p-4 transition-colors hover:border-primary/40 hover:bg-muted/40"
        >
          <div className="flex items-start gap-3">
            <Zap className="h-5 w-5 shrink-0 text-primary" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-muted-foreground">My actions</p>
              {actionCounts.status === 'ok' ? (
                <>
                  <p className="mt-1 font-semibold text-foreground">
                    {actionCounts.value.my} assigned
                  </p>
                  {actionCounts.value.my_overdue > 0 ? (
                    <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                      {actionCounts.value.my_overdue} overdue
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-muted-foreground">None overdue</p>
                  )}
                </>
              ) : (
                <Unavailable label="Action counts" />
              )}
            </div>
          </div>
        </Link>
      </CardContent>
      <div className="flex justify-end px-5 pb-4">
        <Link
          to="/portal/van"
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <Truck className="h-3.5 w-3.5" aria-hidden />
          View my van checks <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </div>
    </Card>
  )
}
