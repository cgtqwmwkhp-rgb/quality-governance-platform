import { metricOk, metricUnavailable, type Metric } from './dashboardMetrics'

/** Only the fields the pulse headline needs; the full row type lives in trainingMatrixClient. */
type RoleMetricLike = { role: string; total?: number | null; pct?: number | null }

/**
 * Headline Atlas module_ok % for the whole org.
 *
 * `pct` is 0 whenever `total` is 0 — the API and computeModuleRoleStats both use
 * that convention — so reading `pct` on its own reports an unpopulated
 * requirements matrix as 0% compliance, which then trips the tile's warnBelow
 * threshold and shows amber. Guard on the denominator the percentage came from.
 */
export function trainingComplianceMetricFromSummary(
  summary: { module_ok?: RoleMetricLike[] | null } | undefined | null,
): Metric<number> {
  const overall = summary?.module_ok?.find((row) => row.role === 'Overall')
  if (!overall) return metricUnavailable()

  // Check for null/undefined before Number(), because Number(null) is a finite 0
  // and would put the fabricated zero straight back.
  if (overall.total == null || overall.pct == null) return metricUnavailable()

  const total = Number(overall.total)
  if (!Number.isFinite(total) || total <= 0) return metricUnavailable()

  const pct = Number(overall.pct)
  if (!Number.isFinite(pct)) return metricUnavailable()

  return metricOk(Math.round(pct))
}
