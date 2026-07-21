/** Lightweight SVG charts for GapBoard Analytics — no new chart dependency. */

export function ComplianceBarChart({
  items,
}: {
  items: { label: string; okPct: number; gapPct: number }[]
}) {
  return (
    <div className="space-y-3" data-testid="training-matrix-analytics-bars">
      {items.map((item) => (
        <div key={item.label}>
          <div className="flex justify-between text-xs mb-1">
            <span className="font-medium">{item.label}</span>
            <span className="text-muted-foreground">
              {item.okPct}% OK · {item.gapPct}% gap
            </span>
          </div>
          <div className="flex h-3 w-full overflow-hidden rounded-sm bg-muted">
            <div className="bg-emerald-600 h-full" style={{ width: `${item.okPct}%` }} />
            <div className="bg-rose-600 h-full" style={{ width: `${item.gapPct}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function StatusPieChart({
  slices,
}: {
  slices: { label: string; value: number; color: string }[]
}) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1
  let angle = -90
  const paths: { d: string; color: string; label: string; value: number }[] = []
  for (const slice of slices) {
    if (slice.value <= 0) continue
    const sweep = (slice.value / total) * 360
    const start = angle
    const end = angle + sweep
    angle = end
    const r = 40
    const cx = 50
    const cy = 50
    const rad = (deg: number) => (Math.PI / 180) * deg
    const x1 = cx + r * Math.cos(rad(start))
    const y1 = cy + r * Math.sin(rad(start))
    const x2 = cx + r * Math.cos(rad(end))
    const y2 = cy + r * Math.sin(rad(end))
    const large = sweep > 180 ? 1 : 0
    paths.push({
      d: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`,
      color: slice.color,
      label: slice.label,
      value: slice.value,
    })
  }
  return (
    <div className="flex items-center gap-4" data-testid="training-matrix-analytics-pie">
      <svg viewBox="0 0 100 100" className="w-28 h-28 shrink-0">
        {paths.map((p) => (
          <path key={p.label} d={p.d} fill={p.color} />
        ))}
      </svg>
      <ul className="text-xs space-y-1">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}: {s.value}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function DueForwardBars({ d30, d90 }: { d30: number; d90: number }) {
  const max = Math.max(d30, d90, 1)
  return (
    <div className="space-y-3" data-testid="training-matrix-analytics-due">
      {[
        { label: 'Due in next 30 days', value: d30 },
        { label: 'Due in next 90 days', value: d90 },
      ].map((row) => (
        <div key={row.label}>
          <div className="flex justify-between text-xs mb-1">
            <span>{row.label}</span>
            <span className="font-medium">{row.value}</span>
          </div>
          <div className="h-3 rounded-sm bg-muted overflow-hidden">
            <div
              className="h-full bg-amber-500"
              style={{ width: `${Math.round((100 * row.value) / max)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
