import { Link } from 'react-router-dom'
import { AlertCircle, Minus, PackageCheck, ShieldAlert, TrendingDown, TrendingUp } from 'lucide-react'
import { Card, CardContent } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'
import type { OrgData } from './useDashboardData'

const TREND_ICON = {
  increasing: TrendingUp,
  decreasing: TrendingDown,
  stable: Minus,
} as const

function TrendBadge({ trend }: { trend: OrgData['riskTrend'] }) {
  if (!trend) {
    return <span className="text-xs text-muted-foreground">Trend unavailable</span>
  }
  const Icon = TREND_ICON[trend]
  const tone =
    trend === 'increasing' ? 'text-destructive' : trend === 'decreasing' ? 'text-success' : 'text-muted-foreground'
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs font-medium capitalize', tone)}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {trend}
    </span>
  )
}

/**
 * Org Command strip (locked design §4) — manager-facing tenant-wide
 * signals: unassigned intake, risk + forecast, asset health. Rendered full
 * for the manager persona and condensed for dual-role (My Day + compact org).
 */
export function OrgCommandStrip({ data, compact = false }: { data: OrgData; compact?: boolean }) {
  const { unassignedTotal, unassignedIncidents, unassignedComplaints, riskHigh, riskOutsideAppetite, riskTrend, assetHealth } = data

  return (
    <div
      data-testid="org-command-strip"
      className={cn('grid gap-4', compact ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-3')}
    >
      {/* Unassigned intake */}
      <Link to="/incidents?owner=unassigned" data-testid="org-unassigned-tile">
        <Card hoverable className={cn('h-full p-5', compact && 'p-4')}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Unassigned intake</p>
              <p className="mt-1 text-2xl font-bold text-foreground">
                {unassignedTotal.status === 'ok' ? unassignedTotal.value : '—'}
              </p>
              {unassignedTotal.status === 'ok' ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {unassignedIncidents.status === 'ok' ? unassignedIncidents.value : '—'} incidents ·{' '}
                  {unassignedComplaints.status === 'ok' ? unassignedComplaints.value : '—'} complaints
                </p>
              ) : (
                <p className="mt-1 text-xs text-muted-foreground">Unavailable right now</p>
              )}
            </div>
            <div className="rounded-xl bg-warning/10 p-3 text-warning">
              <AlertCircle className="h-5 w-5" aria-hidden />
            </div>
          </div>
        </Card>
      </Link>

      {/* Risk + forecast */}
      <Link to="/risk-register?hero=outside_appetite" data-testid="org-risk-forecast-tile">
        <Card hoverable className={cn('h-full p-5', compact && 'p-4')}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Risk + forecast</p>
              <p className="mt-1 text-2xl font-bold text-foreground">
                {riskHigh.status === 'ok' ? riskHigh.value : '—'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {riskOutsideAppetite.status === 'ok'
                  ? `${riskOutsideAppetite.value} outside appetite`
                  : 'Appetite data unavailable'}
              </p>
              <div className="mt-2">
                <TrendBadge trend={riskTrend} />
              </div>
            </div>
            <div className="rounded-xl bg-destructive/10 p-3 text-destructive">
              <ShieldAlert className="h-5 w-5" aria-hidden />
            </div>
          </div>
        </Card>
      </Link>

      {/* Asset health */}
      <Link to="/safety-assets/analytics" data-testid="org-asset-health-tile">
        <Card hoverable className={cn('h-full p-5', compact && 'p-4')}>
          <CardContent className="p-0">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Asset health</p>
                <p className="mt-1 text-2xl font-bold text-foreground">
                  {assetHealth.status === 'ok' ? assetHealth.value.total : '—'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">registered safety assets</p>
              </div>
              <div className="rounded-xl bg-primary/10 p-3 text-primary">
                <PackageCheck className="h-5 w-5" aria-hidden />
              </div>
            </div>
            {assetHealth.status === 'ok' ? (
              <div className="mt-3 flex gap-3 text-xs">
                <span className="flex items-center gap-1 text-destructive">
                  {assetHealth.value.expiry_bands.overdue ?? 0} overdue
                </span>
                <span className="flex items-center gap-1 text-warning">
                  {assetHealth.value.by_status.quarantined ?? 0} quarantined
                </span>
              </div>
            ) : (
              <p className="mt-3 text-xs text-muted-foreground">Metrics are currently unavailable.</p>
            )}
          </CardContent>
        </Card>
      </Link>
    </div>
  )
}
