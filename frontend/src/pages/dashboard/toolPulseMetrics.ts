import { metricOk, metricUnavailable, type Metric } from './dashboardMetrics'

/** Only the fields the pulse headline needs; the full shape lives in assetHealthAnalyticsClient. */
type AssetHealthSummaryLike = {
  total?: number | null
  expiry_bands?: Record<string, number> | null
  by_status?: Record<string, number> | null
}

/**
 * Headline tool-compliance % for the whole registry.
 *
 * An empty registry reports unavailable rather than 100%. Zero registered assets
 * is an unpopulated registry, not a fleet in good order, and a green 100% on it
 * reads as reassurance the data cannot support. Decided by David 28/07/2026,
 * replacing the earlier vacuous-compliance behaviour.
 */
export function toolComplianceMetricFromSummary(
  summary: AssetHealthSummaryLike | undefined | null,
): Metric<number> {
  if (summary?.total == null) return metricUnavailable()

  const total = Number(summary.total)
  if (!Number.isFinite(total) || total <= 0) return metricUnavailable()

  const overdue = Number(summary.expiry_bands?.overdue ?? 0)
  const quarantined = Number(summary.by_status?.quarantined ?? 0)
  if (!Number.isFinite(overdue) || !Number.isFinite(quarantined)) return metricUnavailable()

  // An asset counted in both bands would otherwise drive this past 100% the wrong way.
  const compliant = Math.min(Math.max(total - overdue - quarantined, 0), total)
  return metricOk(Math.round((100 * compliant) / total))
}
