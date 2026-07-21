import { useCallback, useEffect, useState } from 'react'
import {
  actionsApi,
  auditsApi,
  complaintsApi,
  engineersApi,
  incidentsApi,
  nearMissesApi,
  notificationsApi,
  portalComplianceApi,
  riskRegisterApi,
  trainingMatrixApi,
  type Complaint,
  type Incident,
} from '../../api/client'
import type { NearMiss } from '../../api/nearMissesClient'
import { assetHealthAnalyticsApi, type AssetHealthSummary } from '../../api/assetHealthAnalyticsClient'
import { hasRole, isSuperuser } from '../../utils/auth'
import { isGapStatus } from '../workforce/trainingMatrix/trainingMatrixBoardHelpers'
import {
  buildHighlightChips,
  computeRiskTrendDirection,
  countCreatedWithinDays,
  derivePersona,
  metricFromSettled,
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
  /** Top 5 most-recent incidents, newest first — for the legacy "Recent incidents" panel. */
  recentIncidents: Metric<Incident[]>
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
  const [isOrgRole] = useState(() => isSuperuser() || hasRole(...ORG_ROLE_NAMES))
  const [myDay, setMyDay] = useState<MyDayData>({
    compliance: metricUnavailable(),
    trainingTotal: metricUnavailable(),
    trainingGapCount: metricUnavailable(),
    actionCounts: metricUnavailable(),
  })
  const [pulse, setPulse] = useState<PulseData>({
    trainingCompliancePct: metricUnavailable(),
    toolCompliancePct: metricUnavailable(),
    incidents7d: metricUnavailable(),
    complaints7d: metricUnavailable(),
    nearMisses7d: metricUnavailable(),
    auditScorePct: metricUnavailable(),
  })
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
  })

  const load = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      const engineerResult = await engineersApi.getByUserMe().catch(() => null)
      const isLinked = engineerResult?.data?.linked === true
      setLinked(isLinked)

      const persona = derivePersona({ linked: isLinked, isOrgRole })
      const wantMyDay = personaShowsMyDay(persona)
      const wantOrg = personaShowsOrgStrip(persona)

      const [
        unreadRes,
        complianceRes,
        trainingRes,
        actionCountsRes,
        incidentsRes,
        complaintsRes,
        nearMissesRes,
        auditRunsRes,
        trainingSummaryRes,
        assetHealthRes,
        riskSummaryRes,
        riskTrendsRes,
        unassignedIncidentsRes,
        unassignedComplaintsRes,
      ] = await Promise.allSettled([
        notificationsApi.getUnreadCount(),
        wantMyDay ? portalComplianceApi.myCompliance() : Promise.reject(new Error('skip')),
        wantMyDay ? trainingMatrixApi.myTraining() : Promise.reject(new Error('skip')),
        wantMyDay ? actionsApi.viewCounts() : Promise.reject(new Error('skip')),
        wantOrg ? incidentsApi.list(1, 100) : Promise.reject(new Error('skip')),
        wantOrg ? complaintsApi.list(1, 100) : Promise.reject(new Error('skip')),
        wantOrg ? nearMissesApi.list(1, 100) : Promise.reject(new Error('skip')),
        wantOrg ? auditsApi.listRuns(1, 100) : Promise.reject(new Error('skip')),
        wantOrg ? trainingMatrixApi.getSummary() : Promise.reject(new Error('skip')),
        wantOrg ? assetHealthAnalyticsApi.getSummary() : Promise.reject(new Error('skip')),
        wantOrg ? riskRegisterApi.getSummary() : Promise.reject(new Error('skip')),
        wantOrg ? riskRegisterApi.getTrends(90) : Promise.reject(new Error('skip')),
        wantOrg ? incidentsApi.list(1, 1, { owner: 'unassigned' }) : Promise.reject(new Error('skip')),
        wantOrg ? complaintsApi.list(1, 1, { owner: 'unassigned' }) : Promise.reject(new Error('skip')),
      ])

      setUnreadCount(
        unreadRes.status === 'fulfilled' ? unreadRes.value?.data?.unread_count ?? 0 : 0,
      )

      // ---- My Day ----
      // Note: portalComplianceApi.myCompliance() and trainingMatrixApi.myTraining()
      // already unwrap `.data` inside the client (unlike the raw-axios clients below).
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
      const complaintsMetric = metricFromSettled(complaintsRes, (r) => r.data.items as Complaint[])
      const nearMissesMetric = metricFromSettled(nearMissesRes, (r) => r.data.items as NearMiss[])
      const auditRunsMetric = metricFromSettled(auditRunsRes, (r) => r.data.items)
      // trainingMatrixApi.getSummary() also unwraps `.data` inside the client.
      const trainingSummaryMetric = metricFromSettled(trainingSummaryRes)
      const assetHealthMetric = metricFromSettled(assetHealthRes, (r) => r.data)
      const riskSummaryMetric = metricFromSettled(riskSummaryRes, (r) => r.data)
      const riskTrendsMetric = metricFromSettled(riskTrendsRes, (r) => r.data)

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
          assetHealthMetric.status === 'ok' && assetHealthMetric.value.total > 0
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
            : metricUnavailable(),
        incidents7d:
          incidentsMetric.status === 'ok'
            ? { status: 'ok', value: countCreatedWithinDays(incidentsMetric.value, 7) }
            : metricUnavailable(),
        complaints7d:
          complaintsMetric.status === 'ok'
            ? { status: 'ok', value: countCreatedWithinDays(complaintsMetric.value, 7) }
            : metricUnavailable(),
        nearMisses7d:
          nearMissesMetric.status === 'ok'
            ? { status: 'ok', value: countCreatedWithinDays(nearMissesMetric.value, 7) }
            : metricUnavailable(),
        auditScorePct:
          auditRunsMetric.status === 'ok'
            ? { status: 'ok', value: auditAverageScore(auditRunsMetric.value) }
            : metricUnavailable(),
      })

      // ---- Org Command ----
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
                  (riskSummaryMetric.value.by_level?.critical ?? riskSummaryMetric.value.critical ?? 0),
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
        recentIncidents:
          incidentsMetric.status === 'ok'
            ? {
                status: 'ok',
                value: [...incidentsMetric.value]
                  .sort(
                    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
                  )
                  .slice(0, 5),
              }
            : metricUnavailable(),
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

  const persona = derivePersona({ linked, isOrgRole })

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
