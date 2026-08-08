/**
 * Shared GraphCoach (X-2).
 *
 * One `<GraphCoach surface=… />` with a per-surface step registry. Flag-gated
 * by `graph_coach` (X-0). Dismiss persists per surface in localStorage so the
 * coach coaches once then stays ambient. Never blocks publish. Never calls
 * Doc Graph the Golden Thread. Never auto-confirms edges.
 */
import { useMemo, useState } from 'react'
import { Compass, X } from 'lucide-react'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { Button } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { getCoachSurfaceDefinition, type GraphCoachSurface } from './coachSteps'
import {
  clampCoachStepIndex,
  coachStepProgress,
  dismissCoach,
  isCoachDismissed,
  shouldShowGraphCoach,
} from './graphCoachHelpers'

export interface GraphCoachProps {
  surface: GraphCoachSurface
  /** Optional override for tests — defaults to live localStorage. */
  storage?: Storage | null
  /** Called after dismiss / complete so hosts can refresh ambient chrome. */
  onDismissed?: () => void
}

export function GraphCoach({ surface, storage, onDismissed }: GraphCoachProps) {
  const graphCoachEnabled = useFeatureFlag('graph_coach')
  const store =
    storage === undefined
      ? typeof localStorage !== 'undefined'
        ? localStorage
        : null
      : storage

  // Local override after dismiss in this mount; storage remains source of truth on remount.
  const [sessionDismissed, setSessionDismissed] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)

  const definition = useMemo(() => getCoachSurfaceDefinition(surface), [surface])
  const steps = definition.steps
  const dismissed = sessionDismissed || isCoachDismissed(surface, store)
  const visible = shouldShowGraphCoach(graphCoachEnabled) && !dismissed && steps.length > 0

  if (!visible) return null

  const index = clampCoachStepIndex(stepIndex, steps.length)
  const step = steps[index]
  const progress = coachStepProgress(index, steps.length)
  const isLast = index >= steps.length - 1

  const finish = () => {
    dismissCoach(surface, store)
    setSessionDismissed(true)
    onDismissed?.()
  }

  return (
    <aside
      className="rounded-lg border border-border bg-muted/20 px-3 py-3 space-y-3"
      data-testid={`graph-coach-${surface}`}
      aria-label={definition.heading}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Compass className="h-4 w-4 text-muted-foreground" aria-hidden />
          {definition.heading}
        </div>
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          aria-label="Dismiss coach"
          data-testid={`graph-coach-dismiss-${surface}`}
          onClick={finish}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ProgressBar
        value={progress}
        size="sm"
        aria-label={`Coach step ${index + 1} of ${steps.length}`}
        data-testid={`graph-coach-progress-${surface}`}
      />

      <div className="space-y-1" data-testid={`graph-coach-step-${surface}-${step.id}`}>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Step {index + 1} of {steps.length} · {step.title}
        </p>
        <p className="text-sm text-foreground">{step.body}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={index === 0}
          data-testid={`graph-coach-back-${surface}`}
          onClick={() => setStepIndex((prev) => clampCoachStepIndex(prev - 1, steps.length))}
        >
          Back
        </Button>
        {!isLast ? (
          <Button
            type="button"
            size="sm"
            data-testid={`graph-coach-next-${surface}`}
            onClick={() => setStepIndex((prev) => clampCoachStepIndex(prev + 1, steps.length))}
          >
            Next
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            data-testid={`graph-coach-done-${surface}`}
            onClick={finish}
          >
            Done
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          data-testid={`graph-coach-skip-${surface}`}
          onClick={finish}
        >
          Skip
        </Button>
      </div>
    </aside>
  )
}

export default GraphCoach
