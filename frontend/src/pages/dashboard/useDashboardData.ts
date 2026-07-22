import { useCallback, useEffect, useState } from 'react'
import {
  actionsApi,
  auditsApi,
  complaintsApi,
  engineersApi,
  executiveDashboardApi,
  incidentsApi,
  nearMissesApi,
  notificationsApi,
  portalComplianceApi,
  riskRegisterApi,
  rtasApi,
  trainingMatrixApi,
  type Incident,
} from '../../api/client'
import { assetHealthAnalyticsApi, type AssetHealthSummary } from '../../api/assetHealthAnalyticsClient'
import { hasRole, isSuperuser } from '../../utils/auth'
import { isGapStatus } from '../workforce/trainingMatrix/trainingMatrixBoardHelpers'
import {
  buildHighlightChips,
  computeRiskTrendDirection,
  derivePersona,
  metricFromSettled,
  metricOk,
  metricUnavailable,
  personaShowsMyDay,
  personaShowsOrgStrip,
  type DashboardPersona,
  type HighlightChip,
  type Metric,
  type RiskTrendDirection,
} from './dashboardMetrics'
import type { PortalMyCompliance } from '../../api/portalComplianceClient'
import type { ActionsViewCounts } from '../../api/actionsClient'
import { weeklyToSparkPoints, type SparkPoint } from './PulseSparkline'
import type { RecentCaseRow, RecentCasesData } from './RecentCasesPanel'

/** Org role tiers used across the app ('manager' on most governance routes, 'supervisor' on workforce routes). */
const ORG_ROLE_NAMES = ['admin', 'manager', 'supervisor'] as const

export interface MyDayData {
  compliance: Metric<PortalMyCompliance>
  trainingTotal: Metric<number>
  trainingGapCount: Metric<number>
  actionCounts: Metric<ActionsViewCounts>
}

export interface PulseData {
  trainingCompliancePct: Metric<number>
  toolCompliancePct: Metric<number>
  incidents7d: Metric<number>
  complaints7d: Metric<number>
  nearMisses7d: Metric<number>
  auditScorePct: Metric<number>
  trainingSeries: Metric<SparkPoint[]>
  toolSeries: Metric<SparkPoint[]>
  incidentsSeries: Metric<SparkPoint[]>
  complaintsSeries: Metric<SparkPoint[]>
  nearMissesSeries: Metric<SparkPoint[]>
  auditSeries: Metric<SparkPoint[]>
}

export interface OrgData {
  unassignedIncidents: Metric<number>
  unassignedComplaints: Metric<number>
  unassignedTotal: Metric<number>
  criticalIncidentsOpen: Metric<number>
  riskHigh: Metric<number>
  riskOutsideAppetite: Metric<number>
  riskTrend: RiskTrendDirection
  assetHealth: Metric<AssetHealthSummary>
  /** @deprecated Prefer recentCases.incidents — kept for callers that still read it. */
  recentIncidents: Metric<Incident[]>
  recentCases: RecentCasesData
}

export interface DashboardData {
  loading: boolean
  error: string | null
  persona: DashboardPersona
  linked: boolean
  isOrgRole: boolean
  unreadCount: number
  myDay: MyDayData
  pulse: PulseData
  org: OrgData
  highlights: HighlightChip[]
  refresh: () => void
}

function auditAverageScore(runs: { status: string; score_percentage?: number | null }[]): number {
  const completed = runs.filter((r) => r.status === 'completed' && r.score_percentage != null)
  if (completed.length === 0) return 0
  return Math.round(
    completed.reduce((sum, r) => sum + (r.score_percentage ?? 0), 0) / completed.length,
  )
}

function seriesMetric(
  trendsOk: boolean,
  series: { week_start: string; count?: number; value?: number | null }[] | undefined,
): Metric<SparkPoint[]> {
  if (!trendsOk) return metricUnavailable()
  const points = weeklyToSparkPoints(series)
  return points.length >= 2 ? metricOk(points) : metricUnavailable()
}

/** Weekly avg score from the same completed runs used for the audit headline %. */
function auditSeriesFromRuns(
  runs: { status: string; score_percentage?: number | null; completed_at?: string | null }[],
): SparkPoint[] {
  const buckets = new Map<string, number[]>()
  for (const run of runs) {
    if (run.status !== 'completed' || run.score_percentage == null || !run.completed_at) continue
    const d = new Date(run.completed_at)
    if (Number.isNaN(d.getTime())) continue
    // Monday-start week key (UTC) — enough for a directional sparkline.
    const day = d.getUTCDay()
    const mondayOffset = day === 0 ? -6 : 1 - day
    const monday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + mondayOffset))
    const key = monday.toISOString().slice(0, 10)
    const list = buckets.get(key) ?? []
    list.push(run.score_percentage)
    buckets.set(key, list)
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([t, scores]) => ({
      t,
      v: Math.round(scores.reduce((s, n) => s + n, 0) / scores.length),
    }))
}

function emptyPulse(): PulseData {
  return {
    trainingCompliancePct: metricUnavailable(),
    toolCompliancePct: metricUnavailable(),
    incidents7d: metricUnavailable(),
    complaints7d: metricUnavailable(),
    nearMisses7d: metricUnavailable(),
    auditScorePct: metricUnavailable(),
    trainingSeries: metricUnavailable(),
    toolSeries: metricUnavailable(),
    incidentsSeries: metricUnavailable(),
    complaintsSeries: metricUnavailable(),
    nearMissesSeries: metricUnavailable(),
    auditSeries: metricUnavailable(),
  }
}

function emptyRecentCases(): RecentCasesData {
  return {
    incidents: metricUnavailable(),
    nearMisses: metricUnavailable(),
    complaints: metricUnavailable(),
    rtas: metricUnavailable(),
  }
}

/**
 * Fetches and normalizes everything the role-aware dashboard needs.
 *
 * Persona-aware: only fires the fetches each persona actually needs. Every
 * derived value is a fail-honest Metric — a rejected request degrades to
 * 'unavailable', never to a fabricated zero (locked design §1/§5).
 */
export function useDashboardData(): DashboardData {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [unreadCount, setUnreadCount] = useState(0)
  const [linked, setLinked] = useState(false)
  /** True when getByUserMe failed — treat as possibly-linked so we don't hide My Day. */
  const [linkCheckFailed, setLinkCheckFailed] = useState(false)
  const [isOrgRole] = useState(() => isSuperuser() || hasRole(...ORG_ROLE_NAMES))
  const [myDay, setMyDay] = useState<MyDayData>({
    compliance: metricUnavailable(),
    trainingTotal: metricUnavailable(),
    trainingGapCount: metricUnavailable(),
    actionCounts: metricUnavailable(),
  })
  const [pulse, setPulse] = useState<PulseData>(emptyPulse)
  const [org, setOrg] = useState<OrgData>({
    unassignedIncidents: metricUnavailable(),
    unassignedComplaints: metricUnavailable(),
    unassignedTotal: metricUnavailable(),
    criticalIncidentsOpen: metricUnavailable(),
    riskHigh: metricUnavailable(),
    riskOutsideAppetite: metricUnavailable(),
    riskTrend: null,
    assetHealth: metricUnavailable(),
    recentIncidents: metricUnavailable(),
    recentCases: emptyRecentCases(),
  })

  const load = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      let isLinked = false
      let linkFailed = false
      try {
        const engineerResult = await engineersApi.getByUserMe()
        isLinked = engineerResult?.data?.linked === true
      } catch {
        // Do not misclassify as unlinked — keep My Day fetches so linked engineers
        // are not dropped onto an org-only shell when the link probe fails.
        linkFailed = true
        setError(
          'Could not verify your engineer profile link. Showing personal My Day where possible — retry to refresh.',
        )
      }
      setLinked(isLinked)
      setLinkCheckFailed(linkFailed)

      const persona = derivePersona({
        linked: isLinked || linkFailed,
        isOrgRole,
      })
      const wantMyDay = personaShowsMyDay(persona)
      const wantOrg = personaShowsOrgStrip(persona)

      const [
        unreadRes,
        complianceRes,
        trainingRes,
        actionCountsRes,
        incidentsRes,
        execDash7Res,
        execDash56Res,
        auditRunsRes,
        trainingSummaryRes,
        assetHealthRes,
        riskSummaryRes,
        riskTrendsRes,
        unassignedIncidentsRes,
        unassignedComplaintsRes,
        nearMissesRes,
        complaintsListRes,
        rtasRes,
      ] = await Promise.allSettled([
        notificationsApi.getUnreadCount(),
        wantMyDay ? portalComplianceApi.myCompliance() : Promise.reject(new Error('skip')),
        wantMyDay ? trainingMatrixApi.myTraining() : Promise.reject(new Error('skip')),
        wantMyDay ? actionsApi.viewCounts() : Promise.reject(new Error('skip')),
        wantOrg ? incidentsApi.list(1, 100) : Promise.reject(new Error('skip')),
        // Period totals (not page-capped) for 7d pulse tiles.
        wantOrg ? executiveDashboardApi.getDashboard(7) : Promise.reject(new Error('skip')),
        // Weekly sparkline series (8 weeks).
        wantOrg ? executiveDashboardApi.getDashboard(56) : Promise.reject(new Error('skip')),
        wantOrg ? auditsApi.listRuns(1, 100) : Promise.reject(new Error('skip')),
        wantOrg ? trainingMatrixApi.getSummary() : Promise.reject(new Error('skip')),
        wantOrg ? assetHealthAnalyticsApi.getSummary() : Promise.reject(new Error('skip')),
        wantOrg ? riskRegisterApi.getSummary() : Promise.reject(new Error('skip')),
        wantOrg ? riskRegisterApi.getTrends(90) : Promise.reject(new Error('skip')),
        wantOrg ? incidentsApi.list(1, 1, { owner: 'unassigned' }) : Promise.reject(new Error('skip')),
        wantOrg ? complaintsApi.list(1, 1, { owner: 'unassigned' }) : Promise.reject(new Error('skip')),
        wantOrg ? nearMissesApi.list(1, 25) : Promise.reject(new Error('skip')),
        wantOrg ? complaintsApi.list(1, 25) : Promise.reject(new Error('skip')),
        wantOrg ? rtasApi.list(1, 25) : Promise.reject(new Error('skip')),
      ])

      setUnreadCount(
        unreadRes.status === 'fulfilled' ? unreadRes.value?.data?.unread_count ?? 0 : 0,
      )

      // ---- My Day ----
      const complianceMetric = metricFromSettled(complianceRes)
      const trainingMetric = metricFromSettled(trainingRes)
      const actionCountsMetric = metricFromSettled(actionCountsRes, (r) => r.data)

      setMyDay({
        compliance: complianceMetric,
        trainingTotal:
          trainingMetric.status === 'ok'
            ? { status: 'ok', value: trainingMetric.value.total }
            : metricUnavailable(),
        trainingGapCount:
          trainingMetric.status === 'ok'
            ? {
                status: 'ok',
                value: trainingMetric.value.items.filter((row) => isGapStatus(row.status)).length,
              }
            : metricUnavailable(),
        actionCounts: actionCountsMetric,
      })

      // ---- Pulse & trends (tenant-wide) ----
      const incidentsMetric = metricFromSettled(incidentsRes, (r) => r.data.items as Incident[])
      const execDash7Metric = metricFromSettled(execDash7Res, (r) => r.data)
      const execDash56Metric = metricFromSettled(execDash56Res, (r) => r.data)
      const auditRunsMetric = metricFromSettled(auditRunsRes, (r) => r.data.items)
      const trainingSummaryMetric = metricFromSettled(trainingSummaryRes)
      const assetHealthMetric = metricFromSettled(assetHealthRes, (r) => r.data)
      const riskSummaryMetric = metricFromSettled(riskSummaryRes, (r) => r.data)
      const riskTrendsMetric = metricFromSettled(riskTrendsRes, (r) => r.data)
      const trendsOk = execDash56Metric.status === 'ok'
      const trends = trendsOk ? execDash56Metric.value.trends : undefined

      setPulse({
        trainingCompliancePct:
          trainingSummaryMetric.status === 'ok'
            ? {
                status: 'ok',
                value: trainingSummaryMetric.value.module_ok.find((s) => s.role === 'Overall')
                  ?.pct ?? 0,
              }
            : metricUnavailable(),
        toolCompliancePct:
          assetHealthMetric.status === 'ok'
            ? assetHealthMetric.value.total > 0
              ? {
                  status: 'ok',
                  value: Math.round(
                    (100 *
                      (assetHealthMetric.value.total -
                        (assetHealthMetric.value.expiry_bands.overdue ?? 0) -
                        (assetHealthMetric.value.by_status.quarantined ?? 0))) /
                      assetHealthMetric.value.total,
                  ),
                }
              : metricOk(100)
            : metricUnavailable(),
        incidents7d:
          execDash7Metric.status === 'ok'
            ? metricOk(execDash7Metric.value.incidents?.total_in_period ?? 0)
            : metricUnavailable(),
        complaints7d:
          execDash7Metric.status === 'ok'
            ? metricOk(execDash7Metric.value.complaints?.total_in_period ?? 0)
            : metricUnavailable(),
        nearMisses7d:
          execDash7Metric.status === 'ok'
            ? metricOk(execDash7Metric.value.near_misses?.total_in_period ?? 0)
            : metricUnavailable(),
        auditScorePct:
          auditRunsMetric.status === 'ok'
            ? { status: 'ok', value: auditAverageScore(auditRunsMetric.value) }
            : metricUnavailable(),
        // Training headline is Atlas module_ok %; cell expiry backcast is a different
        // metric — omit sparkline until we have honest historical module_ok snapshots.
        trainingSeries: metricUnavailable(),
        toolSeries: seriesMetric(trendsOk, trends?.tool_compliance_weekly),
        incidentsSeries: seriesMetric(trendsOk, trends?.incidents_weekly),
        complaintsSeries: seriesMetric(trendsOk, trends?.complaints_weekly),
        nearMissesSeries: seriesMetric(trendsOk, trends?.near_misses_weekly),
        // Same completed-run set as the headline % (not exec-dashboard weekly avg).
        auditSeries:
          auditRunsMetric.status === 'ok'
            ? (() => {
                const points = auditSeriesFromRuns(auditRunsMetric.value)
                return points.length >= 2 ? metricOk(points) : metricUnavailable()
              })()
            : metricUnavailable(),
      })

      // ---- Org Command + recent cases ----
      const unassignedIncidentsMetric = metricFromSettled(
        unassignedIncidentsRes,
        (r) => r.data.total ?? 0,
      )
      const unassignedComplaintsMetric = metricFromSettled(
        unassignedComplaintsRes,
        (r) => r.data.total ?? 0,
      )
      const unassignedTotal: Metric<number> =
        unassignedIncidentsMetric.status === 'ok' && unassignedComplaintsMetric.status === 'ok'
          ? {
              status: 'ok',
              value: unassignedIncidentsMetric.value + unassignedComplaintsMetric.value,
            }
          : metricUnavailable()

      // Keep API list order (incidents: reported_date DESC).
      const recentIncidents: Metric<Incident[]> =
        incidentsMetric.status === 'ok'
          ? { status: 'ok', value: incidentsMetric.value.slice(0, 5) }
          : metricUnavailable()

      const nearMissesMetric = metricFromSettled(nearMissesRes, (r) => r.data.items)
      const complaintsMetric = metricFromSettled(complaintsListRes, (r) => r.data.items)
      const rtasMetric = metricFromSettled(rtasRes, (r) => r.data.items)

      const recentCases: RecentCasesData = {
        incidents:
          recentIncidents.status === 'ok'
            ? metricOk(
                recentIncidents.value.map(
                  (i): RecentCaseRow => ({
                    id: i.id,
                    reference: i.reference_number,
                    title: i.title,
                    severity: i.severity,
                    status: i.status,
                    date: i.reported_date || i.created_at,
                  }),
                ),
              )
            : metricUnavailable(),
        nearMisses:
          nearMissesMetric.status === 'ok'
            ? metricOk(
                // API paginates by event_date desc — keep that order (do not re-sort by created_at).
                nearMissesMetric.value.slice(0, 5).map(
                  (n): RecentCaseRow => ({
                    id: n.id,
                    reference: n.reference_number,
                    title: n.description?.slice(0, 80) || n.location || 'Near miss',
                    severity: n.potential_severity || n.priority || 'medium',
                    status: n.status,
                    date: n.event_date || n.created_at,
                  }),
                ),
              )
            : metricUnavailable(),
        complaints:
          complaintsMetric.status === 'ok'
            ? metricOk(
                // API paginates by received_date desc — keep that order.
                complaintsMetric.value.slice(0, 5).map(
                  (c): RecentCaseRow => ({
                    id: c.id,
                    reference: c.reference_number,
                    title: c.title,
                    severity: c.priority || 'medium',
                    status: c.status,
                    date: c.received_date || c.created_at,
                  }),
                ),
              )
            : metricUnavailable(),
        rtas:
          rtasMetric.status === 'ok'
            ? metricOk(
                // API paginates by created_at desc — show that date so the
                // column matches list order (reported/collision can diverge).
                rtasMetric.value.slice(0, 5).map(
                  (r): RecentCaseRow => ({
                    id: r.id,
                    reference: r.reference_number,
                    title: r.title,
                    severity: r.severity,
                    status: r.status,
                    date: r.created_at || r.reported_date || r.collision_date,
                  }),
                ),
              )
            : metricUnavailable(),
      }

      setOrg({
        unassignedIncidents: unassignedIncidentsMetric,
        unassignedComplaints: unassignedComplaintsMetric,
        unassignedTotal,
        criticalIncidentsOpen:
          incidentsMetric.status === 'ok'
            ? {
                status: 'ok',
                value: incidentsMetric.value.filter(
                  (i) => i.status !== 'closed' && (i.severity === 'critical' || i.severity === 'high'),
                ).length,
              }
            : metricUnavailable(),
        riskHigh:
          riskSummaryMetric.status === 'ok'
            ? {
                status: 'ok',
                value:
                  (riskSummaryMetric.value.by_level?.high ?? riskSummaryMetric.value.high ?? 0) +
                  (riskSummaryMetric.value.by_level?.critical ??
                    riskSummaryMetric.value.critical ??
                    0),
              }
            : metricUnavailable(),
        riskOutsideAppetite:
          riskSummaryMetric.status === 'ok'
            ? { status: 'ok', value: riskSummaryMetric.value.outside_appetite ?? 0 }
            : metricUnavailable(),
        riskTrend:
          riskTrendsMetric.status === 'ok'
            ? computeRiskTrendDirection(
                Array.isArray(riskTrendsMetric.value)
                  ? riskTrendsMetric.value
                  : riskTrendsMetric.value.series,
              )
            : null,
        assetHealth: assetHealthMetric,
        recentIncidents,
        recentCases,
      })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load dashboard data:', err)
      setError('Failed to load data. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [isOrgRole])

  useEffect(() => {
    void load()
  }, [load])

  const persona = derivePersona({ linked: linked || linkCheckFailed, isOrgRole })

  const highlights = buildHighlightChips({
    myDay: personaShowsMyDay(persona)
      ? {
          clearState:
            myDay.compliance.status === 'ok'
              ? { status: 'ok', value: myDay.compliance.value.clear_state }
              : metricUnavailable(),
          trainingGapCount: myDay.trainingGapCount,
          myOverdueActions:
            myDay.actionCounts.status === 'ok'
              ? { status: 'ok', value: myDay.actionCounts.value.my_overdue }
              : metricUnavailable(),
        }
      : undefined,
    org: personaShowsOrgStrip(persona)
      ? {
          unassignedTotal: org.unassignedTotal,
          criticalIncidentsOpen: org.criticalIncidentsOpen,
          outsideAppetiteRisks: org.riskOutsideAppetite,
          assetsOverdue:
            org.assetHealth.status === 'ok'
              ? { status: 'ok', value: org.assetHealth.value.expiry_bands.overdue ?? 0 }
              : metricUnavailable(),
          assetsQuarantined:
            org.assetHealth.status === 'ok'
              ? { status: 'ok', value: org.assetHealth.value.by_status.quarantined ?? 0 }
              : metricUnavailable(),
        }
      : undefined,
  })

  return {
    loading,
    error,
    persona,
    linked,
    isOrgRole,
    unreadCount,
    myDay,
    pulse,
    org,
    highlights,
    refresh: () => void load(),
  }
}
