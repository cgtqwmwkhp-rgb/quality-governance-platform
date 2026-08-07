/**
 * Relationships Map view (DG-1) — hub + peers SVG over existing edges.
 *
 * No force-directed layout. Map|List toggling lives in DocumentRelationshipsPanel.
 * Never calls Doc Graph the Golden Thread.
 */
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import type { DocumentEdge } from '../../api/documentGraphClient'
import {
  buildRelationshipMapModel,
  relationshipMapEdgeCaption,
} from './relationshipsMapHelpers'

export interface RelationshipsMapViewProps {
  documentId: number
  documentTitle: string
  documentReference?: string | null
  edges: DocumentEdge[]
  /** Resolved counterpart titles keyed by document id (null = ACL-hidden). */
  labels?: Record<number, string | null | undefined>
}

export function RelationshipsMapView({
  documentId,
  documentTitle,
  documentReference = null,
  edges,
  labels = {},
}: RelationshipsMapViewProps) {
  const model = useMemo(
    () =>
      buildRelationshipMapModel(documentId, documentTitle, documentReference, edges, labels),
    [documentId, documentTitle, documentReference, edges, labels],
  )

  const nodeById = useMemo(() => {
    const map = new Map(model.nodes.map((node) => [node.id, node]))
    return map
  }, [model.nodes])

  const peerCount = model.nodes.length - 1

  return (
    <div className="space-y-3" data-testid="relationships-map-view">
      <p className="text-xs text-muted-foreground">
        Hub-and-peers layout of confirmed relationships. Proposed links stay in the list confirm
        queue until a person confirms them.
      </p>

      {peerCount === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="relationships-map-empty">
          No confirmed relationships to place on the map yet.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card/30">
          <svg
            role="img"
            aria-label={`Relationship map for ${documentTitle}`}
            width={model.width}
            height={model.height}
            viewBox={`0 0 ${model.width} ${model.height}`}
            className="mx-auto block max-w-full"
            data-testid="relationships-map-svg"
          >
            {model.links.map((link) => {
              const from = nodeById.get(link.fromId)
              const to = nodeById.get(link.toId)
              if (!from || !to) return null
              const midX = (from.x + to.x) / 2
              const midY = (from.y + to.y) / 2
              return (
                <g key={`link-${link.edgeId}`} data-testid={`relationships-map-link-${link.edgeId}`}>
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    className="stroke-border"
                    strokeWidth={1.5}
                  />
                  <text
                    x={midX}
                    y={midY - 6}
                    textAnchor="middle"
                    className="fill-muted-foreground text-[10px]"
                  >
                    {relationshipMapEdgeCaption(link.edgeType)}
                  </text>
                </g>
              )
            })}

            {model.nodes.map((node) => {
              const radius = node.isHub ? 28 : 22
              const body = (
                <>
                  <circle
                    r={radius}
                    className={
                      node.isHub
                        ? 'fill-primary/15 stroke-primary'
                        : 'fill-card stroke-border'
                    }
                    strokeWidth={node.isHub ? 2 : 1.5}
                  />
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className={
                      node.isHub
                        ? 'fill-foreground text-[11px] font-semibold'
                        : 'fill-foreground text-[10px] font-medium'
                    }
                  >
                    {truncateLabel(node.label, node.isHub ? 14 : 12)}
                  </text>
                  {!node.isHub && node.relationLabel ? (
                    <text
                      y={radius + 14}
                      textAnchor="middle"
                      className="fill-muted-foreground text-[9px]"
                    >
                      {node.relationLabel}
                    </text>
                  ) : null}
                </>
              )
              return (
                <g
                  key={`node-${node.id}`}
                  transform={`translate(${node.x}, ${node.y})`}
                  data-testid={
                    node.isHub
                      ? 'relationships-map-hub'
                      : `relationships-map-node-${node.id}`
                  }
                >
                  {node.isHub ? body : <a href={node.href}><title>{node.label}</title>{body}</a>}
                </g>
              )
            })}
          </svg>
        </div>
      )}

      {peerCount > 0 ? (
        <ul className="space-y-1" data-testid="relationships-map-legend">
          {model.nodes
            .filter((node) => !node.isHub)
            .map((node) => (
              <li key={node.id} className="flex flex-wrap items-center gap-2 text-sm">
                <Link
                  to={node.href}
                  className="font-medium text-foreground hover:underline"
                  data-testid={`relationships-map-legend-${node.id}`}
                >
                  {node.label}
                </Link>
                {node.reference ? (
                  <span className="font-mono text-xs text-muted-foreground">{node.reference}</span>
                ) : null}
                {node.relationLabel ? (
                  <span className="text-xs text-muted-foreground">{node.relationLabel}</span>
                ) : null}
              </li>
            ))}
        </ul>
      ) : null}
    </div>
  )
}

function truncateLabel(label: string, max: number): string {
  const trimmed = label.trim()
  if (trimmed.length <= max) return trimmed
  return `${trimmed.slice(0, Math.max(1, max - 1))}…`
}

export default RelationshipsMapView
