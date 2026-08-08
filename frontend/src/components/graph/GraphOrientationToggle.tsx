/**
 * Graph orientation swap control (X-2).
 *
 * Flag-gated by `graph_coach` so the V/H primitive ships with the shared coach
 * programme without inventing a second flag. Surfaces own layout application.
 */
import { useEffect, useState } from 'react'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { Button } from '../ui/Button'
import {
  DEFAULT_GRAPH_ORIENTATION,
  graphOrientationLabel,
  readStoredGraphOrientation,
  resolveGraphOrientation,
  writeStoredGraphOrientation,
  type GraphOrientation,
} from './graphOrientation'
import { shouldShowGraphCoach } from './graphCoachHelpers'

export interface GraphOrientationToggleProps {
  /** Persistence + test-id namespace (e.g. document_relationships). */
  surface: string
  value?: GraphOrientation
  defaultValue?: GraphOrientation
  onChange?: (orientation: GraphOrientation) => void
  storage?: Storage | null
}

export function GraphOrientationToggle({
  surface,
  value,
  defaultValue = DEFAULT_GRAPH_ORIENTATION,
  onChange,
  storage,
}: GraphOrientationToggleProps) {
  const graphCoachEnabled = useFeatureFlag('graph_coach')
  const store =
    storage === undefined
      ? typeof localStorage !== 'undefined'
        ? localStorage
        : null
      : storage

  const [internal, setInternal] = useState<GraphOrientation>(() => {
    if (value !== undefined) return resolveGraphOrientation(value, defaultValue)
    return readStoredGraphOrientation(surface, store) ?? resolveGraphOrientation(defaultValue)
  })

  useEffect(() => {
    if (value !== undefined) {
      setInternal(resolveGraphOrientation(value, defaultValue))
    }
  }, [value, defaultValue])

  if (!shouldShowGraphCoach(graphCoachEnabled)) return null

  const current = value !== undefined ? resolveGraphOrientation(value, defaultValue) : internal

  const setOrientation = (next: GraphOrientation) => {
    if (value === undefined) {
      setInternal(next)
      writeStoredGraphOrientation(surface, next, store)
    }
    onChange?.(next)
  }

  return (
    <div
      className="inline-flex rounded-md border border-border p-0.5"
      role="group"
      aria-label="Graph orientation"
      data-testid={`graph-orientation-toggle-${surface}`}
    >
      {(['horizontal', 'vertical'] as const).map((orientation) => (
        <Button
          key={orientation}
          type="button"
          size="sm"
          variant={current === orientation ? 'default' : 'ghost'}
          aria-pressed={current === orientation}
          data-testid={`graph-orientation-${surface}-${orientation}`}
          onClick={() => setOrientation(orientation)}
        >
          {graphOrientationLabel(orientation)}
        </Button>
      ))}
    </div>
  )
}

export default GraphOrientationToggle
