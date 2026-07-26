/**
 * Investigation coverage of the source registers (PX-136).
 *
 * A short list of investigations reads as "the register is covered" even when almost every
 * real incident has nothing attached to it. This turns the server's per-register counts into
 * a statement the reader can act on. It reports the gap; it does not close it — creating the
 * missing investigations is a deliberate act by a person, not something a page does.
 */
import api from '../../api/client'

export interface SourceCoverageItem {
  source_type: string
  total: number
  investigated: number
  not_investigated: number
}

export interface SourceCoverageResponse {
  items: SourceCoverageItem[]
  total: number
  investigated: number
  not_investigated: number
}

/** Register labels, matching the create-from-record dialog. */
const SOURCE_TYPE_LABELS: Record<string, string> = {
  reporting_incident: 'incident',
  near_miss: 'near miss',
  road_traffic_collision: 'road traffic collision',
  complaint: 'complaint',
}

/** Plural forms that are not formed by appending an "s". */
const SOURCE_TYPE_PLURALS: Record<string, string> = {
  near_miss: 'near misses',
}

export function sourceTypeLabel(sourceType: string, count: number): string {
  const singular = SOURCE_TYPE_LABELS[sourceType] || sourceType.replace(/_/g, ' ')
  if (count === 1) return singular
  return SOURCE_TYPE_PLURALS[sourceType] || `${singular}s`
}

export async function fetchSourceCoverage(): Promise<SourceCoverageResponse> {
  const response = await api.get<SourceCoverageResponse>('/api/v1/investigations/source-coverage')
  return response.data
}

export interface SourceCoverageHonesty {
  /** True when at least one source record has no investigation. */
  hasGap: boolean
  headline: string
  detail: string
}

/**
 * Build the honesty copy. Returns `hasGap: false` when the registers are empty or fully
 * covered, so the strip stays off rather than manufacturing a warning out of no data.
 */
export function buildSourceCoverageHonesty(
  coverage: SourceCoverageResponse | null | undefined,
): SourceCoverageHonesty {
  const items = coverage?.items ?? []
  const gaps = items
    .filter((item) => item.not_investigated > 0)
    .sort((a, b) => b.not_investigated - a.not_investigated)

  if (!coverage || gaps.length === 0) {
    return { hasGap: false, headline: '', detail: '' }
  }

  const breakdown = gaps
    .map((item) => `${item.not_investigated} ${sourceTypeLabel(item.source_type, item.not_investigated)}`)
    .join(', ')

  return {
    hasGap: true,
    headline: `${coverage.not_investigated} source ${
      coverage.not_investigated === 1 ? 'record has' : 'records have'
    } no investigation`,
    detail:
      `${breakdown}. This list only shows investigations that exist, so it is not evidence ` +
      'that the underlying records were investigated.',
  }
}
