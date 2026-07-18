import type { Action, CustomerPackSummary, EvidenceAsset, InvestigationComment, TimelineEvent } from '../../api/client'

export type ActivityKind =
  | 'revision'
  | 'comment'
  | 'capa'
  | 'evidence'
  | 'pack'
  | 'manual'

export interface ActivitySpineItem {
  id: string
  kind: ActivityKind
  eventType: string
  title: string
  body?: string
  createdAt: string
  actorId?: number | null
  hrefTab?: 'timeline' | 'evidence' | 'actions' | 'report' | 'rca' | 'summary'
  meta?: Record<string, unknown>
}

function asIso(value: string | undefined | null, fallback = ''): string {
  return value || fallback
}

export function buildActivitySpine(input: {
  timeline: TimelineEvent[]
  comments: InvestigationComment[]
  actions: Action[]
  evidence: EvidenceAsset[]
  packs: CustomerPackSummary[]
}): ActivitySpineItem[] {
  const items: ActivitySpineItem[] = []

  for (const event of input.timeline) {
    const isManual = event.event_type === 'MANUAL_ENTRY'
    items.push({
      id: `rev-${event.id}`,
      kind: isManual ? 'manual' : 'revision',
      eventType: event.event_type,
      title: event.event_type.replace(/_/g, ' '),
      body:
        typeof event.new_value === 'string'
          ? event.new_value
          : event.field_path || undefined,
      createdAt: asIso(event.created_at),
      actorId: event.actor_id,
      hrefTab: isManual ? 'timeline' : undefined,
      meta: { field_path: event.field_path, event_metadata: event.event_metadata },
    })
  }

  for (const comment of input.comments) {
    // Prefer revision COMMENT_ADDED when present; still surface comments as spine rows
    // so notes appear even if revision emission lagged.
    items.push({
      id: `comment-${comment.id}`,
      kind: 'comment',
      eventType: 'COMMENT_ADDED',
      title: 'Comment',
      body: comment.content,
      createdAt: asIso(comment.created_at),
      actorId: comment.author_id,
      hrefTab: 'summary',
    })
  }

  for (const action of input.actions) {
    items.push({
      id: `capa-${action.id}`,
      kind: 'capa',
      eventType: 'CAPA',
      title: action.reference_number || `CAPA #${action.id}`,
      body: `${action.title} · ${action.display_status || action.status}`,
      createdAt: asIso(action.created_at),
      hrefTab: 'actions',
      meta: { action_key: action.action_key, action_id: action.id },
    })
  }

  for (const asset of input.evidence) {
    items.push({
      id: `evidence-${asset.id}`,
      kind: 'evidence',
      eventType: 'EVIDENCE',
      title: asset.title || asset.original_filename || `Evidence #${asset.id}`,
      body: `${asset.visibility.replace(/_/g, ' ')}${asset.contains_pii ? ' · PII' : ''}`,
      createdAt: asIso(asset.created_at),
      hrefTab: 'evidence',
      meta: { asset_id: asset.id, visibility: asset.visibility },
    })
  }

  for (const pack of input.packs) {
    items.push({
      id: `pack-${pack.id}`,
      kind: 'pack',
      eventType: 'PACK_GENERATED',
      title: `${pack.audience.replace(/_/g, ' ')} pack`,
      body: pack.checksum_sha256 ? `SHA256 ${pack.checksum_sha256.slice(0, 12)}…` : undefined,
      createdAt: asIso(pack.generated_at),
      hrefTab: 'report',
      meta: { pack_id: pack.id, audience: pack.audience },
    })
  }

  return items.sort((a, b) => {
    const ta = Date.parse(a.createdAt) || 0
    const tb = Date.parse(b.createdAt) || 0
    if (tb !== ta) return tb - ta
    return a.id.localeCompare(b.id)
  })
}

export function filterActivitySpine(
  items: ActivitySpineItem[],
  filter: string,
): ActivitySpineItem[] {
  if (!filter || filter === 'all') return items
  const f = filter.toUpperCase()
  if (f === 'COMMENT_ADDED') return items.filter((i) => i.kind === 'comment' || i.eventType === 'COMMENT_ADDED')
  if (f === 'PACK_GENERATED') return items.filter((i) => i.kind === 'pack' || i.eventType === 'PACK_GENERATED')
  if (f === 'CAPA') return items.filter((i) => i.kind === 'capa')
  if (f === 'EVIDENCE') return items.filter((i) => i.kind === 'evidence')
  if (f === 'MANUAL_ENTRY') return items.filter((i) => i.kind === 'manual' || i.eventType === 'MANUAL_ENTRY')
  return items.filter((i) => i.eventType === f)
}
