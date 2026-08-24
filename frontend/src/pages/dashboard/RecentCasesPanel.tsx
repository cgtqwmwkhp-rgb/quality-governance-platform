import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { CaseRegisterReferenceLink } from '../../components/register/CaseRegisterReferenceLink'
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
  /**
   * Register route for this tab. Detail routes are `${href}/:id` for all four
   * kinds — see the `incidents|near-misses|rtas|complaints` routes in `App.tsx`.
   */
  href: string
  /** Singular noun for a row's accessible name, matching each register's own wording. */
  noun: string
  empty: string
  dateLabel: string
}[] = [
  {
    id: 'incidents',
    label: 'Incidents',
    href: '/incidents',
    noun: 'incident',
    empty: 'No incidents found',
    dateLabel: 'Reported',
  },
  {
    id: 'near_misses',
    label: 'Near misses',
    href: '/near-misses',
    noun: 'near miss',
    empty: 'No near misses found',
    dateLabel: 'Occurred',
  },
  {
    id: 'complaints',
    label: 'Feedback',
    href: '/complaints',
    noun: 'feedback',
    empty: 'No feedback found',
    dateLabel: 'Received',
  },
  {
    id: 'rtas',
    label: 'RTAs',
    href: '/rtas',
    noun: 'road traffic accident',
    empty: 'No road traffic accidents found',
    dateLabel: 'Logged',
  },
]

/**
 * Detail route for a row, or `null` when the feed gave us no usable id.
 *
 * The reference cell was styled `text-primary` but was plain text, so the one
 * thing on the dashboard that looked like a link to a case was not one: no
 * middle-click, no open-in-new-tab, no copy-link, nothing for the keyboard
 * (FR-DASH-RECENT-01). Registers already solved this with a real `<Link>` in the
 * reference cell plus a row-level click (PX-173 / PX-200); this reuses the same
 * anchor component so the two surfaces stay in step.
 *
 * A row with no id gets no link rather than a guessed one — `/incidents/0` and
 * `/incidents/undefined` both resolve to a detail page that cannot load, which
 * reads as a broken record instead of a missing id.
 */
function detailPath(href: string, id: number): string | null {
  if (!Number.isInteger(id) || id <= 0) return null
  return `${href}/${id}`
}

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
 * Incidents, Near misses, Feedback, and RTAs.
 *
 * Rows open their own case: a real anchor on the reference (so middle-click,
 * open-in-new-tab and copy-link all work) plus a row-level click for the rest of
 * the row. See `detailPath`.
 */
export function RecentCasesPanel({ data }: { data: RecentCasesData }) {
  const [tab, setTab] = useState<RecentCaseKind>('incidents')
  const navigate = useNavigate()

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
                  rows.map((row) => {
                    const reference = formatReference(row.reference)
                    const to = detailPath(active.href, row.id)
                    return (
                      <tr
                        key={`${tab}-${row.id}`}
                        data-testid="recent-cases-row"
                        className={cn(
                          'border-b border-border/50 transition-colors hover:bg-surface',
                          to && 'cursor-pointer',
                        )}
                        onClick={to ? () => navigate(to) : undefined}
                        onKeyDown={
                          to
                            ? (event) => {
                                // Only the row's own keystrokes open it, so a key pressed
                                // inside a cell never navigates the dashboard away.
                                if (event.target !== event.currentTarget) return
                                if (event.key === 'Enter' || event.key === ' ') {
                                  event.preventDefault()
                                  navigate(to)
                                }
                              }
                            : undefined
                        }
                        tabIndex={to ? 0 : undefined}
                        aria-label={to ? `View ${active.noun}: ${reference}` : undefined}
                      >
                        <td className="px-4 py-3">
                          {to ? (
                            <CaseRegisterReferenceLink to={to}>
                              {reference}
                            </CaseRegisterReferenceLink>
                          ) : (
                            <span className="font-mono text-sm text-muted-foreground">
                              {reference}
                            </span>
                          )}
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
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
