import { metricOk, metricUnavailable, type Metric } from './dashboardMetrics'

/** Server-side 7d audit average from executive dashboard / audit analytics SSOT. */
export function auditScoreMetricFromDashboard(
  audits: { avg_score?: number | null } | undefined | null,
): Metric<number> {
  const score = audits?.avg_score
  if (score == null || !Number.isFinite(Number(score))) return metricUnavailable()
  return metricOk(Math.round(Number(score)))
}
