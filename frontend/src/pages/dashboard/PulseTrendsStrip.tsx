import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ClipboardCheck,
  GraduationCap,
  MessageSquare,
  ShieldAlert,
  Wrench,
} from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'
import type { Metric } from './dashboardMetrics'
import type { PulseData } from './useDashboardData'

interface PulseTileProps {
  testId: string
  label: string
  icon: React.ElementType
  href: string
  metric: Metric<number>
  /** '%' for percentages, '' for raw counts. */
  suffix?: string
  /** Lower-is-better metrics (e.g. incident counts) flip the warn threshold direction. */
  warnBelow?: number
  warnAbove?: number
}

function PulseTile({
  testId,
  label,
  icon: Icon,
  href,
  metric,
  suffix = '',
  warnBelow,
  warnAbove,
}: PulseTileProps) {
  const isWarn =
    metric.status === 'ok' &&
    ((warnBelow !== undefined && metric.value < warnBelow) ||
      (warnAbove !== undefined && metric.value > warnAbove))

  return (
    <Link to={href} data-testid={testId} className="block">
      <Card
        hoverable
        className={cn('h-full p-4', isWarn && 'border-warning/40 bg-warning/5')}
      >
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Icon className="h-4 w-4" aria-hidden />
          {label}
        </div>
        {metric.status === 'ok' ? (
          <p
            className={cn('mt-2 text-2xl font-bold', isWarn ? 'text-warning' : 'text-foreground')}
            data-testid={`${testId}-value`}
          >
            {metric.value}
            {suffix}
          </p>
        ) : (
          <p className="mt-2 text-2xl font-bold text-muted-foreground" data-testid={`${testId}-value`}>
            —
          </p>
        )}
        {metric.status !== 'ok' && (
          <p className="mt-1 text-xs text-muted-foreground">Unavailable right now</p>
        )}
      </Card>
    </Link>
  )
}

/**
 * Pulse & trends strip (locked design §3) — six tenant-wide health signals,
 * each a clickable drill-down. Fail-honest: an unavailable fetch renders
 * "—", never a silent 0.
 */
export function PulseTrendsStrip({ data }: { data: PulseData }) {
  return (
    <div data-testid="pulse-trends-strip" className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
      <PulseTile
        testId="pulse-training-compliance"
        label="Training compliance"
        icon={GraduationCap}
        href="/workforce/dashboard"
        metric={data.trainingCompliancePct}
        suffix="%"
        warnBelow={80}
      />
      <PulseTile
        testId="pulse-tool-compliance"
        label="Tool compliance"
        icon={Wrench}
        href="/safety-assets/analytics"
        metric={data.toolCompliancePct}
        suffix="%"
        warnBelow={80}
      />
      <PulseTile
        testId="pulse-incidents-7d"
        label="Incidents (7d)"
        icon={AlertTriangle}
        href="/incidents"
        metric={data.incidents7d}
        warnAbove={0}
      />
      <PulseTile
        testId="pulse-complaints-7d"
        label="Complaints (7d)"
        icon={MessageSquare}
        href="/complaints"
        metric={data.complaints7d}
        warnAbove={0}
      />
      <PulseTile
        testId="pulse-near-misses-7d"
        label="Near misses (7d)"
        icon={ShieldAlert}
        href="/near-misses"
        metric={data.nearMisses7d}
      />
      <PulseTile
        testId="pulse-audit-score"
        label="Audit score"
        icon={ClipboardCheck}
        href="/audits"
        metric={data.auditScorePct}
        suffix="%"
        warnBelow={70}
      />
    </div>
  )
}
