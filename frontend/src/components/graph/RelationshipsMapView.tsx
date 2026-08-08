/**
 * Relationships Map view (DG-1/DG-2) — hub + peers SVG over existing edges.
 *
 * No force-directed layout. Map|List toggling lives in DocumentRelationshipsPanel.
 * Optional Library→hub DnD propose (flag-gated) never auto-confirms.
 * Never calls Doc Graph the Golden Thread.
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { DocumentEdge } from '../../api/documentGraphClient'
import {
  parseLibraryDocumentDrag,
  type LibraryDocumentDragPayload,
} from './documentGraphDndHelpers'
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
  /** When true, hub accepts library-document drops to propose an edge. */
  dndEnabled?: boolean
  onLibraryDocumentDrop?: (payload: LibraryDocumentDragPayload) => void
}

export function RelationshipsMapView({
  documentId,
  documentTitle,
  documentReference = null,
  edges,
  labels = {},
  dndEnabled = false,
  onLibraryDocumentDrop,
}: RelationshipsMapViewProps) {
  const [dropActive, setDropActive] = useState(false)

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

  const handleDragOver = (event: React.DragEvent) => {
    if (!dndEnabled || !onLibraryDocumentDrop) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    if (!dropActive) setDropActive(true)
  }

  const handleDragLeave = (event: React.DragEvent) => {
    if (!dndEnabled) return
    // Only clear when leaving the drop surface (not child SVG nodes).
    if (event.currentTarget.contains(event.relatedTarget as Node)) return
    setDropActive(false)
  }

  const handleDrop = (event: React.DragEvent) => {
    if (!dndEnabled || !onLibraryDocumentDrop) return
    event.preventDefault()
    event.stopPropagation()
    setDropActive(false)
    const payload = parseLibraryDocumentDrag(event.dataTransfer)
    if (payload) onLibraryDocumentDrop(payload)
  }

  return (
    <div className="space-y-3" data-testid="relationships-map-view">
      <p className="text-xs text-muted-foreground">
        Hub-and-peers layout of confirmed relationships. Proposed links stay in the list confirm
        queue until a person confirms them.
        {dndEnabled
          ? ' Drag a library document onto the hub to propose a typed edge — never auto-confirmed.'
          : null}
      </p>

      {dndEnabled ? (
        // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- HTML5 drop target is mouse-only; typed propose / confirm flows remain keyboard-accessible
        <div
          role="region"
          aria-label={`${documentTitle} hub — drop a library document to propose a relationship`}
          className={
            dropActive
              ? 'rounded-lg border-2 border-dashed border-primary bg-primary/5 p-3 transition-colors'
              : 'rounded-lg border-2 border-dashed border-border bg-card/20 p-3 transition-colors'
          }
          data-testid="relationships-map-drop-zone"
          onDragEnter={handleDragOver}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <p className="mb-2 text-center text-xs text-muted-foreground" data-testid="relationships-map-drop-hint">
            {documentTitle} · hub · drop here to propose
          </p>
          {renderMapBody({ model, nodeById, peerCount, documentTitle })}
        </div>
      ) : (
        renderMapBody({ model, nodeById, peerCount, documentTitle })
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

function renderMapBody({
  model,
  nodeById,
  peerCount,
  documentTitle,
}: {
  model: ReturnType<typeof buildRelationshipMapModel>
  nodeById: Map<number, (typeof model.nodes)[number]>
  peerCount: number
  documentTitle: string
}) {
  if (peerCount === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="relationships-map-empty">
        No confirmed relationships to place on the map yet.
      </p>
    )
  }

  return (
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
  )
}

function truncateLabel(label: string, max: number): string {
  const trimmed = label.trim()
  if (trimmed.length <= max) return trimmed
  return `${trimmed.slice(0, Math.max(1, max - 1))}…`
}

export default RelationshipsMapView
