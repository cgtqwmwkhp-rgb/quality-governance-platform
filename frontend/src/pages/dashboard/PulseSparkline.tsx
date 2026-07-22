import { cn } from '../../helpers/utils'

export type SparkPoint = { t: string; v: number }

/**
 * Compact SVG sparkline for pulse tiles. Renders only when ≥2 real points exist
 * (never fabricates a flat zero line from missing history).
 */
export function PulseSparkline({
  points,
  lowerIsBetter = false,
  className,
  testId,
}: {
  points: SparkPoint[] | null | undefined
  /** When true, a falling series is "good" (counts). Default: rising is good (%). */
  lowerIsBetter?: boolean
  className?: string
  testId?: string
}) {
  if (!points || points.length < 2) return null

  const values = points.map((p) => p.v)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const w = 72
  const h = 28
  const pad = 2

  const coords = points.map((p, i) => {
    const x = pad + (i / (points.length - 1)) * (w - pad * 2)
    const y = pad + (1 - (p.v - min) / span) * (h - pad * 2)
    return `${x},${y}`
  })
  const polyline = coords.join(' ')

  const first = values[0]
  const last = values[values.length - 1]
  const rising = last > first
  const flat = last === first
  const improving = flat ? null : lowerIsBetter ? !rising : rising

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={cn('h-7 w-[4.5rem] shrink-0', className)}
      role="img"
      aria-label={`Trend ${flat ? 'flat' : improving ? 'improving' : 'worsening'} over ${points.length} weeks`}
      data-testid={testId}
    >
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={polyline}
        className={cn(
          flat && 'text-muted-foreground',
          improving === true && 'text-success',
          improving === false && 'text-warning',
        )}
      />
    </svg>
  )
}

/** Map executive-dashboard weekly points → sparkline points (prefer `value`). */
export function weeklyToSparkPoints(
  series: { week_start: string; count?: number; value?: number | null }[] | undefined,
): SparkPoint[] {
  if (!Array.isArray(series)) return []
  return series
    .map((p) => {
      // Explicit null value = sparse week (e.g. no audits completed) — omit.
      if (Object.prototype.hasOwnProperty.call(p, 'value') && p.value === null) {
        return null
      }
      const v = p.value != null ? Number(p.value) : p.count != null ? Number(p.count) : NaN
      if (!Number.isFinite(v)) return null
      return { t: p.week_start, v }
    })
    .filter((p): p is SparkPoint => p != null)
}

