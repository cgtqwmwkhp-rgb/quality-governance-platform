import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, AlertCircle, Info, Pause, Play, Radio } from 'lucide-react'
import { cn } from '../../helpers/utils'
import type { HighlightChip, HighlightTone } from './dashboardMetrics'

const TONE_STYLES: Record<HighlightTone, string> = {
  critical: 'border-destructive/30 bg-destructive/5 text-destructive hover:bg-destructive/10',
  warning: 'border-warning/30 bg-warning/5 text-warning hover:bg-warning/10',
  info: 'border-info/30 bg-info/5 text-info hover:bg-info/10',
}

const TONE_ICON: Record<HighlightTone, React.ElementType> = {
  critical: AlertTriangle,
  warning: AlertCircle,
  info: Info,
}

/** Persisted preference: auto-scroll the highlight rail when chips overflow. */
export const HIGHLIGHT_RAIL_SCROLL_KEY = 'qgp.dashboard.highlightRail.autoScroll'

function readAutoScrollPref(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const raw = window.localStorage.getItem(HIGHLIGHT_RAIL_SCROLL_KEY)
    if (raw === null) return false // calm static wrap by default
    return raw === 'true'
  } catch {
    return false
  }
}

function Chip({ chip }: { chip: HighlightChip }) {
  const Icon = TONE_ICON[chip.tone]
  return (
    <Link
      to={chip.href}
      data-testid={`highlight-chip-${chip.id}`}
      className={cn(
        'inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full border px-3.5 py-2 text-sm font-medium transition-colors',
        TONE_STYLES[chip.tone],
      )}
    >
      <Icon className="h-4 w-4" aria-hidden />
      {chip.label}
    </Link>
  )
}

/**
 * Live Highlight Rail (locked design §1).
 *
 * Renders nothing when there are no priority items — an empty rail is honest
 * signal ("all clear"), not a loading placeholder or fabricated zero.
 *
 * When chips overflow, auto-scroll is off by default (static wrap / manual
 * horizontal scroll). Users can opt into marquee via a toggle; preference is
 * persisted. System prefers-reduced-motion always disables marquee.
 */
export function HighlightRail({ chips }: { chips: HighlightChip[] }) {
  const [reduceMotion, setReduceMotion] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false,
  )
  const [autoScroll, setAutoScroll] = useState(readAutoScrollPref)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduceMotion(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const setAutoScrollPref = (next: boolean) => {
    setAutoScroll(next)
    try {
      window.localStorage.setItem(HIGHLIGHT_RAIL_SCROLL_KEY, String(next))
    } catch {
      // ignore quota / private-mode failures — in-memory toggle still works
    }
  }

  if (chips.length === 0) {
    return (
      <div
        data-testid="highlight-rail-empty"
        className="flex items-center gap-2 rounded-xl border border-success/20 bg-success/5 px-4 py-3 text-sm text-success"
      >
        <Radio className="h-4 w-4" aria-hidden />
        All clear — no priority items right now.
      </div>
    )
  }

  const canMarquee = chips.length > 4 && !reduceMotion
  const shouldScroll = canMarquee && autoScroll

  return (
    <div
      data-testid="highlight-rail"
      className="relative overflow-hidden rounded-xl border border-border bg-card p-2"
    >
      <div className="flex items-start gap-2">
        <div
          className={cn(
            'min-w-0 flex-1',
            shouldScroll ? 'overflow-hidden' : 'overflow-x-auto',
          )}
        >
          <div
            className={cn(
              'flex gap-2',
              shouldScroll
                ? 'w-max animate-highlight-rail hover:[animation-play-state:paused] focus-within:[animation-play-state:paused]'
                : 'flex-wrap',
            )}
          >
            {chips.map((chip) => (
              <Chip key={chip.id} chip={chip} />
            ))}
            {shouldScroll &&
              chips.map((chip) => <Chip key={`${chip.id}-repeat`} chip={chip} />)}
          </div>
        </div>

        {canMarquee && (
          <button
            type="button"
            data-testid="highlight-rail-scroll-toggle"
            aria-pressed={autoScroll}
            aria-label={autoScroll ? 'Stop auto-scroll' : 'Start auto-scroll'}
            title={autoScroll ? 'Stop auto-scroll' : 'Start auto-scroll'}
            onClick={() => setAutoScrollPref(!autoScroll)}
            className={cn(
              'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
              autoScroll && 'border-primary/30 text-primary',
            )}
          >
            {autoScroll ? (
              <Pause className="h-4 w-4" aria-hidden />
            ) : (
              <Play className="h-4 w-4" aria-hidden />
            )}
          </button>
        )}
      </div>
    </div>
  )
}
