import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'
import { formatDisplayDate, formatReference } from '../../helpers/formatters'
import type { Metric } from './dashboardMetrics'

export type RecentCaseKind = 'incidents' | 'near_misses' | 'complaints' | 'rtas'

export interface RecentCaseRow {
  id: number
  reference: string
  title: string
  severity: string
  status: string
  date: string
}

/**
 * Each tab binds a different date column (see `useDashboardData`): incidents show when
 * they were reported, near misses when the event happened, and so on. A single "Date"
 * header made those read as the same thing — an incident reported today but backdated
 * to 2024 looked like the dashboard and /incidents disagreed (PX-122). Name the field.
 *
 * The other half of PX-122 is still open: /incidents shows `incident_date` under a
 * column also headed "Date", so the two surfaces still need reading together. That
 * header lives in `pages/Incidents.tsx`, which another lane owns; it wants the label
 * "Occurred" and `formatDisplayDate` from `helpers/formatters`.
 */
const TABS: {
  id: RecentCaseKind
  label: string
  href: string
  empty: string
  dateLabel: string
}[] = [
  {
    id: 'incidents',
    label: 'Incidents',
    href: '/incidents',
    empty: 'No incidents found',
    dateLabel: 'Reported',
  },
  {
    id: 'near_misses',
    label: 'Near misses',
    href: '/near-misses',
    empty: 'No near misses found',
    dateLabel: 'Occurred',
  },
  {
    id: 'complaints',
    label: 'Complaints',
    href: '/complaints',
    empty: 'No complaints found',
    dateLabel: 'Received',
  },
  {
    id: 'rtas',
    label: 'RTAs',
    href: '/rtas',
    empty: 'No road traffic accidents found',
    dateLabel: 'Logged',
  },
]

function severityVariant(severity: string): 'critical' | 'high' | 'medium' | 'low' {
  const s = severity.toLowerCase()
  if (s === 'critical') return 'critical'
  if (s === 'high') return 'high'
  if (s === 'medium') return 'medium'
  return 'low'
}

function statusVariant(status: string): 'resolved' | 'in-progress' | 'submitted' {
  const s = status.toLowerCase()
  if (s === 'closed' || s === 'resolved') return 'resolved'
  if (s.includes('investigation') || s === 'in_progress' || s === 'acknowledged') return 'in-progress'
  return 'submitted'
}

export interface RecentCasesData {
  incidents: Metric<RecentCaseRow[]>
  nearMisses: Metric<RecentCaseRow[]>
  complaints: Metric<RecentCaseRow[]>
  rtas: Metric<RecentCaseRow[]>
}

/**
 * Cascading recent-cases panel — four compact tabs to switch between
 * Incidents, Near misses, Complaints, and RTAs.
 */
export function RecentCasesPanel({ data }: { data: RecentCasesData }) {
  const [tab, setTab] = useState<RecentCaseKind>('incidents')

  const active = useMemo(() => TABS.find((t) => t.id === tab) ?? TABS[0], [tab])

  const metric: Metric<RecentCaseRow[]> =
    tab === 'incidents'
      ? data.incidents
      : tab === 'near_misses'
        ? data.nearMisses
        : tab === 'complaints'
          ? data.complaints
          : data.rtas

  // Hide entire panel only when every feed failed — empty ok lists still show.
  const anyOk =
    data.incidents.status === 'ok' ||
    data.nearMisses.status === 'ok' ||
    data.complaints.status === 'ok' ||
    data.rtas.status === 'ok'
  if (!anyOk) return null

  const rows = metric.status === 'ok' ? metric.value : []

  return (
    <Card data-testid="recent-cases-panel">
      <CardHeader className="space-y-3">
        <div className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Recent cases</CardTitle>
          <Button variant="link" size="sm" asChild>
            <Link to={active.href} data-testid="recent-cases-view-all">
              View All <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        </div>
        <div
          className="flex flex-wrap gap-1.5"
          role="tablist"
          aria-label="Recent case type"
          data-testid="recent-cases-tabs"
        >
          {TABS.map((t) => {
            const selected = t.id === tab
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={selected}
                data-testid={`recent-cases-tab-${t.id}`}
                onClick={() => setTab(t.id)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                  selected
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </CardHeader>
      <CardContent>
        {metric.status !== 'ok' ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Unavailable right now
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Reference
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Severity
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Status
                  </th>
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-muted-foreground"
                    data-testid="recent-cases-date-header"
                  >
                    {active.dateLabel}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      {active.empty}
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr
                      key={`${tab}-${row.id}`}
                      className="border-b border-border/50 transition-colors hover:bg-surface"
                    >
                      <td className="px-4 py-3 font-mono text-sm text-primary">
                        {formatReference(row.reference)}
                      </td>
                      <td className="px-4 py-3 text-sm text-foreground">{row.title}</td>
                      <td className="px-4 py-3">
                        <Badge variant={severityVariant(row.severity)}>{row.severity}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={statusVariant(row.status)}>
                          {row.status.replace(/_/g, ' ')}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {formatDisplayDate(row.date)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
