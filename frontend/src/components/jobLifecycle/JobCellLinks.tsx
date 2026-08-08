/**
 * JobCellLinks — JL-3 cell hyperlinks (audit · app · external).
 *
 * Flag-gated by `job_cell_links` (and parent `job_lifecycle`). App / audit
 * hrefs come from the API (X-1 href_registry) — no parallel FE URL builders.
 *
 * JL-UX-W1: do NOT refetch on every parent render. Links are seeded from the
 * cell list payload (`listCells` embeds `links[]`); mutations update local
 * state + notify parent. A parent-updating callback must never sit in the
 * fetch effect dependency chain (that caused the 429 storm).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Loader2, Plus, Trash2 } from 'lucide-react'
import { getApiErrorMessage, jobLifecycleApi } from '../../api/client'
import type { JobCellLink, JobCellLinkCreatePayload, JobCellLinkKind } from '../../api/jobLifecycleClient'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Input } from '../ui/Input'
import {
  JOB_CELL_LINK_KINDS,
  jobCellLinkKindLabel,
  jobCellLinkOpenTarget,
  jobCellLinkRel,
  resolveJobCellLinkHref,
  shouldShowJobCellLinks,
} from './jobCellLinksHelpers'

export interface JobCellLinksProps {
  jobTypeId: number
  laneId: number
  stepId: number
  jobLifecycleEnabled: boolean
  jobCellLinksEnabled: boolean
  /** Seed from cell list payload; refreshed after mutations via onLinksChange. */
  initialLinks?: JobCellLink[]
  onLinksChange?: (links: JobCellLink[]) => void
}

function linksSeedKey(jobTypeId: number, laneId: number, stepId: number, links: JobCellLink[]): string {
  return `${jobTypeId}:${laneId}:${stepId}:${links.map((l) => l.id).join(',')}`
}

export default function JobCellLinks({
  jobTypeId,
  laneId,
  stepId,
  jobLifecycleEnabled,
  jobCellLinksEnabled,
  initialLinks = [],
  onLinksChange,
}: JobCellLinksProps) {
  const visible = shouldShowJobCellLinks(jobLifecycleEnabled, jobCellLinksEnabled)
  const [links, setLinks] = useState<JobCellLink[]>(initialLinks)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState<JobCellLinkKind>('app')
  const [label, setLabel] = useState('')
  const [entityType, setEntityType] = useState('document')
  const [entityId, setEntityId] = useState('')
  const [externalUrl, setExternalUrl] = useState('')
  const [auditRunId, setAuditRunId] = useState('')
  const [auditFindingId, setAuditFindingId] = useState('')

  const onLinksChangeRef = useRef(onLinksChange)
  onLinksChangeRef.current = onLinksChange

  const applyLinks = useCallback((next: JobCellLink[]) => {
    setLinks(next)
    onLinksChangeRef.current?.(next)
  }, [])

  const seedKey = linksSeedKey(jobTypeId, laneId, stepId, initialLinks)
  const seedKeyRef = useRef(seedKey)
  useEffect(() => {
    if (seedKeyRef.current === seedKey) return
    seedKeyRef.current = seedKey
    setLinks(initialLinks)
    setError(null)
  }, [seedKey, initialLinks])

  if (!visible) return null

  async function onAdd() {
    const trimmedLabel = label.trim()
    if (!trimmedLabel) {
      setError('Label is required')
      return
    }
    let payload: JobCellLinkCreatePayload
    if (kind === 'app') {
      const id = Number(entityId)
      if (!entityType.trim() || !Number.isFinite(id) || id <= 0) {
        setError('App links need entity type and a positive entity id')
        return
      }
      payload = {
        kind: 'app',
        label: trimmedLabel,
        entity_type: entityType.trim().toLowerCase(),
        entity_id: id,
      }
    } else if (kind === 'external') {
      if (!externalUrl.trim()) {
        setError('External links need an https URL')
        return
      }
      payload = {
        kind: 'external',
        label: trimmedLabel,
        external_url: externalUrl.trim(),
      }
    } else {
      const runId = Number(auditRunId)
      const findingId = Number(auditFindingId)
      if (!Number.isFinite(runId) || runId <= 0 || !Number.isFinite(findingId) || findingId <= 0) {
        setError('Audit links need run id and finding id')
        return
      }
      payload = {
        kind: 'audit_outcome',
        label: trimmedLabel,
        audit_run_id: runId,
        audit_finding_id: findingId,
      }
    }

    setSaving(true)
    setError(null)
    try {
      const res = await jobLifecycleApi.createCellLink(jobTypeId, laneId, stepId, payload)
      applyLinks([...links, res.data])
      setLabel('')
      setEntityId('')
      setExternalUrl('')
      setAuditRunId('')
      setAuditFindingId('')
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function onRemove(linkId: number) {
    setSaving(true)
    setError(null)
    try {
      await jobLifecycleApi.deleteCellLink(linkId)
      applyLinks(links.filter((l) => l.id !== linkId))
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="p-4 space-y-3" data-testid="job-cell-links">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">Step links</h2>
        <Badge variant="outline" className="text-[10px]">
          audit · app · external
        </Badge>
      </div>
      <p className="text-[11px] text-muted-foreground">
        App and audit hrefs resolve through the shared registry — no parallel URL builders.
        Links are seeded from the cell list (no refetch storm).
      </p>

      {error ? (
        <p className="text-xs text-destructive" data-testid="job-cell-links-error">
          {error}
        </p>
      ) : null}

      <ul className="space-y-1.5" data-testid="job-cell-links-list">
        {links.map((link) => {
          const href = resolveJobCellLinkHref(link)
          const external = link.kind === 'external'
          return (
            <li
              key={link.id}
              className="flex items-center gap-2 rounded border border-border bg-background px-2 py-1.5"
              data-testid={`job-cell-link-${link.id}`}
            >
              <Badge variant="secondary" className="text-[10px] shrink-0">
                {jobCellLinkKindLabel(link.kind)}
              </Badge>
              {external ? (
                <a
                  href={href}
                  target={jobCellLinkOpenTarget(link)}
                  rel={jobCellLinkRel(link)}
                  className="flex-1 truncate text-xs hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {link.label}
                  <ExternalLink className="inline h-3 w-3 ml-1 opacity-60" />
                </a>
              ) : (
                <Link
                  to={href}
                  className="flex-1 truncate text-xs hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {link.label}
                </Link>
              )}
              <button
                type="button"
                className="text-muted-foreground hover:text-destructive"
                aria-label={`Remove link ${link.label}`}
                data-testid={`job-cell-link-remove-${link.id}`}
                disabled={saving}
                onClick={() => void onRemove(link.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          )
        })}
        {links.length === 0 ? (
          <li className="text-xs text-muted-foreground py-1">No step links yet.</li>
        ) : null}
      </ul>

      <div className="space-y-2 border-t border-border pt-3" data-testid="job-cell-links-form">
        <div className="flex flex-wrap gap-2">
          {JOB_CELL_LINK_KINDS.map((k) => (
            <Button
              key={k}
              type="button"
              size="sm"
              variant={kind === k ? 'default' : 'outline'}
              onClick={() => setKind(k)}
              data-testid={`job-cell-links-kind-${k}`}
            >
              {jobCellLinkKindLabel(k)}
            </Button>
          ))}
        </div>
        <Input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label…"
          data-testid="job-cell-links-label"
        />
        {kind === 'app' ? (
          <div className="grid grid-cols-2 gap-2">
            <Input
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              placeholder="entity type (document, risk…)"
              data-testid="job-cell-links-entity-type"
            />
            <Input
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="entity id"
              inputMode="numeric"
              data-testid="job-cell-links-entity-id"
            />
          </div>
        ) : null}
        {kind === 'external' ? (
          <Input
            value={externalUrl}
            onChange={(e) => setExternalUrl(e.target.value)}
            placeholder="https://…"
            data-testid="job-cell-links-external-url"
          />
        ) : null}
        {kind === 'audit_outcome' ? (
          <div className="grid grid-cols-2 gap-2">
            <Input
              value={auditRunId}
              onChange={(e) => setAuditRunId(e.target.value)}
              placeholder="audit run id"
              inputMode="numeric"
              data-testid="job-cell-links-audit-run-id"
            />
            <Input
              value={auditFindingId}
              onChange={(e) => setAuditFindingId(e.target.value)}
              placeholder="finding id"
              inputMode="numeric"
              data-testid="job-cell-links-audit-finding-id"
            />
          </div>
        ) : null}
        <Button
          type="button"
          size="sm"
          onClick={() => void onAdd()}
          disabled={saving}
          data-testid="job-cell-links-add"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Add link
        </Button>
      </div>
    </Card>
  )
}
