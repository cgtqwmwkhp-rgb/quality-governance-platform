/**
 * Plantexpand interlocking-octagon mark, recolored for QGP.
 * Top-left ring → brand lime; bottom-right ring → deep green; hashes → charcoal.
 */
import { cn } from '../helpers/utils'

type BrandMarkProps = {
  className?: string
  size?: number
  /** onBrand: high-contrast mark for gradient-brand tiles */
  variant?: 'color' | 'onBrand'
  title?: string
}

const COLORS = {
  color: {
    ringA: 'hsl(82 85% 45%)', // brand lime (was burgundy)
    ringB: 'hsl(82 45% 22%)', // deep green (was charcoal)
    hash: 'hsl(220 20% 12%)',
  },
  onBrand: {
    ringA: 'hsl(220 20% 10%)',
    ringB: 'hsl(220 15% 18%)',
    hash: 'hsl(0 0% 100%)',
  },
} as const

/** Regular flat-top octagon centered at (cx,cy) with outer radius r */
function octagonPoints(cx: number, cy: number, r: number): string {
  const k = r / (1 + Math.SQRT2)
  const pts = [
    [cx - k, cy - r],
    [cx + k, cy - r],
    [cx + r, cy - k],
    [cx + r, cy + k],
    [cx + k, cy + r],
    [cx - k, cy + r],
    [cx - r, cy + k],
    [cx - r, cy - k],
  ]
  return pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
}

export function BrandMark({
  className,
  size = 40,
  variant = 'color',
  title = 'Quality Governance Platform',
}: BrandMarkProps) {
  const c = COLORS[variant]
  const stroke = 5.2
  // Two interlocking octagons along the diagonal
  const a = { cx: 26, cy: 26, r: 16.5 }
  const b = { cx: 38, cy: 38, r: 16.5 }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>

      {/* Ring A (top-left) — drawn first */}
      <polygon
        points={octagonPoints(a.cx, a.cy, a.r)}
        stroke={c.ringA}
        strokeWidth={stroke}
        strokeLinejoin="round"
        fill="none"
      />

      {/* Ring B (bottom-right) — paints over at crossings for link effect */}
      <polygon
        points={octagonPoints(b.cx, b.cy, b.r)}
        stroke={c.ringB}
        strokeWidth={stroke}
        strokeLinejoin="round"
        fill="none"
      />

      {/* Re-paint A segments that should pass over B for true interlock */}
      <path
        d="M32.2 18.8 L34.5 21.1 M18.8 32.2 L21.1 34.5"
        stroke={c.ringA}
        strokeWidth={stroke}
        strokeLinecap="round"
      />

      {/* Hash marks — interior NW of ring A */}
      <g stroke={c.hash} strokeWidth="1.75" strokeLinecap="round">
        <line x1="15.2" y1="22.5" x2="18.6" y2="19.1" />
        <line x1="14.4" y1="26.0" x2="18.2" y2="22.2" />
        <line x1="14.4" y1="29.5" x2="18.2" y2="25.7" />
        <line x1="15.2" y1="32.8" x2="18.8" y2="29.2" />
        <line x1="17.0" y1="35.5" x2="20.4" y2="32.1" />
      </g>

      {/* Hash marks — interior SE of ring B */}
      <g stroke={c.hash} strokeWidth="1.75" strokeLinecap="round">
        <line x1="43.6" y1="44.9" x2="47.0" y2="41.5" />
        <line x1="45.8" y1="46.8" x2="49.6" y2="43.0" />
        <line x1="48.0" y1="48.0" x2="51.8" y2="44.2" />
        <line x1="49.8" y1="50.5" x2="53.6" y2="46.7" />
        <line x1="50.6" y1="53.8" x2="54.0" y2="50.4" />
      </g>
    </svg>
  )
}

/** Rounded brand tile used in shell / auth headers */
export function BrandMarkTile({
  className,
  size = 44,
  iconSize,
}: {
  className?: string
  size?: number
  iconSize?: number
}) {
  const mark = iconSize ?? Math.round(size * 0.72)
  return (
    <div
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/25 shadow-glow',
        className,
      )}
      style={{ width: size, height: size }}
    >
      <BrandMark size={mark} variant="color" />
    </div>
  )
}
