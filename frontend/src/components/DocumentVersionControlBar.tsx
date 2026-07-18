/**
 * World-class document version control bar — create → revise → publish honesty.
 * Shows tip / published / draft, immutable history, and gated actions.
 */
import { useMemo, useState } from 'react'
import { History, Lock, Megaphone, GitBranch, Loader2 } from 'lucide-react'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Card } from './ui/Card'
import { Textarea } from './ui/Textarea'
import { cn } from '../helpers/utils'

export interface VersionHistoryItem {
  id: number
  version_number: string
  change_summary?: string | null
  change_notes?: string | null
  change_type?: string | null
  status: string
  is_immutable?: boolean
  read_only?: boolean
  created_by_name?: string | null
  created_at?: string | null
  approved_by_name?: string | null
  approved_date?: string | null
  published_at?: string | null
}

export interface DocumentVersionControlBarProps {
  documentLabel?: string
  currentVersion: string
  status: string
  publishedVersion?: string | null
  workingVersion?: string | null
  versions: VersionHistoryItem[]
  loading?: boolean
  error?: string | null
  canRevise?: boolean
  canPublish?: boolean
  revising?: boolean
  publishing?: boolean
  onRevise?: (changeSummary: string, isMajor: boolean, file?: File | null) => Promise<void> | void
  onPublish?: () => Promise<void> | void
  className?: string
}

const statusVariant = (status: string) => {
  switch (status) {
    case 'published':
    case 'approved':
    case 'effective':
    case 'active':
      return 'success' as const
    case 'draft':
    case 'under_revision':
      return 'secondary' as const
    case 'superseded':
    case 'obsolete':
      return 'outline' as const
    default:
      return 'outline' as const
  }
}

export function DocumentVersionControlBar({
  documentLabel = 'Document',
  currentVersion,
  status,
  publishedVersion,
  workingVersion,
  versions,
  loading = false,
  error = null,
  canRevise = true,
  canPublish = true,
  revising = false,
  publishing = false,
  onRevise,
  onPublish,
  className,
}: DocumentVersionControlBarProps) {
  const [showRevise, setShowRevise] = useState(false)
  const [changeSummary, setChangeSummary] = useState('')
  const [isMajor, setIsMajor] = useState(false)
  const [revisionFile, setRevisionFile] = useState<File | null>(null)

  const hasOpenDraft = useMemo(
    () => versions.some((v) => v.status === 'draft' && !v.is_immutable && !v.read_only),
    [versions],
  )
  const hasPublished = useMemo(
    () =>
      Boolean(publishedVersion) ||
      versions.some((v) =>
        ['published', 'approved', 'effective', 'active'].includes(v.status),
      ),
    [publishedVersion, versions],
  )
  // Pre-publish: allow revise to bump the working draft. Post-publish: block while a draft is open.
  const reviseBlocked = hasOpenDraft && hasPublished

  const sorted = useMemo(
    () =>
      [...versions].sort((a, b) => {
        const aTime = a.created_at || a.published_at || ''
        const bTime = b.created_at || b.published_at || ''
        return bTime.localeCompare(aTime)
      }),
    [versions],
  )

  const handleRevise = async () => {
    if (!onRevise || changeSummary.trim().length < 10) return
    await onRevise(changeSummary.trim(), isMajor, revisionFile)
    setChangeSummary('')
    setIsMajor(false)
    setRevisionFile(null)
    setShowRevise(false)
  }

  return (
    <div className={cn('space-y-4', className)} data-testid="document-version-control-bar">
      <Card className="p-4 border-border/80 bg-gradient-to-br from-background via-background to-muted/30">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
              <History className="h-3.5 w-3.5" />
              Version control
            </div>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="text-lg font-semibold text-foreground truncate">{documentLabel}</h3>
              <span className="font-mono text-sm text-primary" data-testid="version-tip">
                v{currentVersion}
              </span>
              <Badge variant={statusVariant(status)} data-testid="version-doc-status">
                {status}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span data-testid="version-published">
                Published:{' '}
                <strong className="text-foreground">
                  {publishedVersion ? `v${publishedVersion}` : '— none yet'}
                </strong>
              </span>
              <span data-testid="version-working">
                Working draft:{' '}
                <strong className="text-foreground">
                  {workingVersion ? `v${workingVersion}` : '— none'}
                </strong>
              </span>
            </div>
            <p className="text-xs text-muted-foreground max-w-2xl">
              Published versions are immutable. Revise opens a draft tip; publish freezes it and
              supersedes the prior published copy.
            </p>
          </div>

          <div className="flex flex-wrap gap-2 shrink-0">
            {canRevise && onRevise && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRevise((v) => !v)}
                disabled={revising || reviseBlocked}
                data-testid="version-revise-btn"
                title={
                  reviseBlocked
                    ? 'Publish or discard the open draft first'
                    : 'Open or bump a revision draft'
                }
              >
                <GitBranch className="w-4 h-4 mr-2" />
                Revise
              </Button>
            )}
            {canPublish && onPublish && (
              <Button
                size="sm"
                onClick={() => void onPublish()}
                disabled={publishing || !hasOpenDraft}
                data-testid="version-publish-btn"
              >
                {publishing ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Megaphone className="w-4 h-4 mr-2" />
                )}
                Publish
              </Button>
            )}
          </div>
        </div>

        {showRevise && (
          <div className="mt-4 space-y-3 border-t border-border pt-4" data-testid="version-revise-form">
            <Textarea
              placeholder="Change summary (what changed and why) — min 10 characters"
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              rows={3}
              data-testid="version-change-summary"
            />
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={isMajor}
                onChange={(e) => setIsMajor(e.target.checked)}
                data-testid="version-major-toggle"
              />
              Major version bump (e.g. 1.0 → 2.0)
            </label>
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground" htmlFor="version-revision-file">
                Replacement file (optional — triggers re-index)
              </label>
              <input
                id="version-revision-file"
                type="file"
                accept=".pdf,.doc,.docx,.xlsx,.xls,.csv,.md,.txt,.png,.jpg,.jpeg"
                onChange={(e) => setRevisionFile(e.target.files?.[0] ?? null)}
                data-testid="version-revision-file"
              />
              {revisionFile && (
                <p className="text-xs text-muted-foreground" data-testid="version-filename-hint">
                  Selected: {revisionFile.name}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => void handleRevise()}
                disabled={revising || changeSummary.trim().length < 10}
                data-testid="version-revise-submit"
              >
                {revising ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Create draft version
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowRevise(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Card>

      {error && (
        <div
          className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          data-testid="version-history-error"
        >
          {error}
        </div>
      )}

      <Card className="p-4" data-testid="version-history-list">
        <h4 className="font-medium text-foreground mb-3">Version history</h4>
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : sorted.length === 0 ? (
          <p className="text-sm text-muted-foreground" data-testid="version-history-empty">
            No version history yet. Create or upload a document to start at v1.0 draft.
          </p>
        ) : (
          <ol className="relative space-y-3 border-l border-border ml-2 pl-4">
            {sorted.map((v) => {
              const immutable = Boolean(v.is_immutable || v.read_only || v.status === 'superseded' || v.status === 'published')
              const summary = v.change_summary || v.change_notes || '—'
              return (
                <li key={v.id} className="relative" data-testid={`version-row-${v.version_number}`}>
                  <span className="absolute -left-[1.35rem] top-1.5 h-2.5 w-2.5 rounded-full bg-primary/80 ring-2 ring-background" />
                  <div className="rounded-lg border border-border/80 bg-card/40 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-medium text-foreground">v{v.version_number}</span>
                        <Badge variant={statusVariant(v.status)}>{v.status}</Badge>
                        {immutable && (
                          <Badge variant="outline" data-testid={`version-immutable-${v.version_number}`}>
                            <Lock className="w-3 h-3 mr-1" />
                            Read-only
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {v.created_at ? new Date(v.created_at).toLocaleString() : '—'}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">{summary}</p>
                    {(v.created_by_name || v.approved_by_name) && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {v.created_by_name ? `Author: ${v.created_by_name}` : null}
                        {v.created_by_name && v.approved_by_name ? ' · ' : null}
                        {v.approved_by_name ? `Published by: ${v.approved_by_name}` : null}
                      </p>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </Card>
    </div>
  )
}

export default DocumentVersionControlBar
