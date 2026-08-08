/**
 * Entity360 Connections strip (X-1 / X-3).
 *
 * Self-fetches `/entity-360/{type}/{id}` when `entity_360` is open so
 * DocumentDetail only mounts the component. Bidirectional hops; denied sources
 * carry no counts. Never labels Doc Graph the Golden Thread.
 *
 * Satellite pages pass ``requiresSatellites`` so both `entity_360` and
 * `entity_360_satellites` must be on (nested like job_cell_links).
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitBranch, Loader2 } from 'lucide-react'
import { entity360Api, getApiErrorMessage } from '../../api/client'
import type { Entity360Bundle, Entity360Hop } from '../../api/entity360Client'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { Badge } from '../ui/Badge'
import {
  connectionsHasNeighbors,
  hopCaption,
  shouldFetchEntity360,
  shouldShowEntity360Strip,
  shouldShowSatelliteConnections,
} from './entity360StripHelpers'

export interface Entity360StripProps {
  entityType: string
  entityId: number
  /** Optional master Doc Graph flag — unused for fetch gate today. */
  documentGraphEnabled?: boolean
  /**
   * When true, also requires `entity_360_satellites` (satellite module pages).
   * Document Detail / Job Lifecycle leave this false.
   */
  requiresSatellites?: boolean
}

function HopChip({ hop }: { hop: Entity360Hop }) {
  const label = hopCaption(hop)
  return (
    <Link
      to={hop.href}
      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs text-foreground hover:bg-muted/60"
      data-testid={`entity360-hop-${hop.direction}-${hop.source_type}-${hop.source_id}`}
      title={`${hop.direction} · ${hop.relation} · ${hop.origin}`}
    >
      <span className="text-muted-foreground uppercase tracking-wide">{hop.direction === 'upstream' ? '↑' : '↓'}</span>
      <span className="font-medium">{label}</span>
      {hop.status ? (
        <Badge variant="outline" className="text-[10px] px-1 py-0">
          {hop.status}
        </Badge>
      ) : null}
    </Link>
  )
}

export function Entity360Strip({
  entityType,
  entityId,
  documentGraphEnabled = true,
  requiresSatellites = false,
}: Entity360StripProps) {
  const entity360Enabled = useFeatureFlag('entity_360')
  const satellitesEnabled = useFeatureFlag('entity_360_satellites')
  const visible = requiresSatellites
    ? shouldShowSatelliteConnections(entity360Enabled, satellitesEnabled)
    : shouldShowEntity360Strip(entity360Enabled)
  const shouldFetch = requiresSatellites
    ? shouldShowSatelliteConnections(entity360Enabled, satellitesEnabled)
    : shouldFetchEntity360(entity360Enabled, documentGraphEnabled)

  const [bundle, setBundle] = useState<Entity360Bundle | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!shouldFetch || !entityId || Number.isNaN(entityId)) {
      setBundle(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    setBundle(null)

    void (async () => {
      try {
        const response = await entity360Api.getBundle(entityType, entityId)
        if (cancelled) return
        setBundle(response.data)
      } catch (err) {
        if (cancelled) return
        setBundle(null)
        setError(getApiErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [entityType, entityId, shouldFetch])

  if (!visible) return null

  const hasNeighbors = connectionsHasNeighbors(bundle)
  const deniedOrigins = (bundle?.sources ?? [])
    .filter((s) => s.status === 'denied')
    .map((s) => s.origin)

  return (
    <div
      className="rounded-lg border border-border bg-muted/20 px-3 py-2 space-y-2"
      data-testid="entity360-connections-strip"
    >
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <GitBranch className="h-4 w-4 text-muted-foreground" />
        Connections
        {bundle && !bundle.complete ? (
          <Badge variant="destructive" data-testid="entity360-degraded">
            Degraded
          </Badge>
        ) : null}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-1">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading connections…
        </div>
      ) : null}

      {error ? (
        <p className="text-xs text-destructive" role="alert" data-testid="entity360-error">
          {error}
        </p>
      ) : null}

      {!loading && bundle && !hasNeighbors ? (
        <p className="text-xs text-muted-foreground" data-testid="entity360-empty">
          No upstream or downstream connections recorded yet.
          {deniedOrigins.length > 0
            ? ' Some sources were denied by permission.'
            : null}
        </p>
      ) : null}

      {!loading && bundle && hasNeighbors ? (
        <div className="flex flex-wrap gap-1.5" data-testid="entity360-hops">
          {[...(bundle.upstream ?? []), ...(bundle.downstream ?? [])].map((hop) => (
            <HopChip
              key={`${hop.origin}-${hop.direction}-${hop.relation}-${hop.source_type}-${hop.source_id}-${hop.edge_id ?? 0}`}
              hop={hop}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default Entity360Strip
