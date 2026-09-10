/**
 * The findings list editor (INV-C7).
 *
 * Replaces the single findings textarea. Each finding is its own row with its own
 * text, position, and delete; the concatenated string the closure gate and the
 * generated pack still read is derived server-side from these rows, so there is
 * nothing to keep in step here.
 *
 * Presentational on purpose: it owns the draft text of the row being edited and
 * nothing else. Every mutation is handed up to `InvestigationDetail`, which calls
 * the API and passes the server's ordered list back down — so the order shown is
 * always the order stored, never an optimistic guess that a failed request would
 * leave on screen.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowDown, ArrowUp, Check, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/Textarea'
import type { InvestigationFinding } from '../../api/client'

export interface InvestigationFindingsEditorProps {
  findings: InvestigationFinding[]
  loading: boolean
  /** Set while any mutation is in flight; every control is disabled meanwhile. */
  saving: boolean
  error: string | null
  readOnly?: boolean
  onAdd: (body: string) => Promise<boolean>
  onUpdate: (findingId: number, body: string) => Promise<boolean>
  onDelete: (findingId: number) => Promise<boolean>
  onMove: (findingId: number, direction: -1 | 1) => Promise<boolean>
  onRetry: () => void
}

export default function InvestigationFindingsEditor({
  findings,
  loading,
  saving,
  error,
  readOnly = false,
  onAdd,
  onUpdate,
  onDelete,
  onMove,
  onRetry,
}: InvestigationFindingsEditorProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingBody, setEditingBody] = useState('')

  // A finding deleted in another tab must not leave this one editing a row that
  // is no longer in the list, with a save button that can only 404.
  useEffect(() => {
    if (editingId !== null && !findings.some((finding) => finding.id === editingId)) {
      setEditingId(null)
      setEditingBody('')
    }
  }, [findings, editingId])

  const busy = saving || loading
  const canAdd = draft.trim().length > 0 && !busy && !readOnly

  const handleAdd = async () => {
    if (!canAdd) return
    const body = draft.trim()
    const saved = await onAdd(body)
    // Cleared only after the parent confirms success, so a failed add keeps the text.
    if (saved) setDraft('')
  }

  const handleSaveEdit = async (findingId: number) => {
    const body = editingBody.trim()
    if (!body) return
    const saved = await onUpdate(findingId, body)
    if (saved) {
      setEditingId(null)
      setEditingBody('')
    }
  }

  return (
    <div className="space-y-4" data-testid="investigation-findings-list">
      {error ? (
        <div className="flex items-center justify-between gap-3" role="alert">
          <p className="text-sm text-destructive" data-testid="investigation-findings-error">
            {error}
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={onRetry}
            data-testid="investigation-findings-retry"
          >
            {t('investigations.findings.retry')}
          </Button>
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="investigation-findings-loading">
          <Loader2 className="inline w-4 h-4 mr-2 animate-spin" />
          {t('investigations.findings.loading')}
        </p>
      ) : null}

      {!loading && findings.length === 0 && !error ? (
        <p className="text-sm text-muted-foreground" data-testid="investigation-findings-empty">
          {t('investigations.findings.empty')}
        </p>
      ) : null}

      <ol className="space-y-3">
        {findings.map((finding, index) => (
          <li
            key={finding.id}
            className="rounded-md border border-border p-3"
            data-testid={`investigation-finding-${finding.id}`}
          >
            {editingId === finding.id ? (
              <div className="space-y-2">
                <label htmlFor={`inv-finding-edit-${finding.id}`} className="sr-only">
                  {t('investigations.findings.edit_label')}
                </label>
                <Textarea
                  id={`inv-finding-edit-${finding.id}`}
                  rows={3}
                  value={editingBody}
                  onChange={(event) => setEditingBody(event.target.value)}
                  data-testid={`investigation-finding-edit-input-${finding.id}`}
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={busy || editingBody.trim().length === 0}
                    onClick={() => void handleSaveEdit(finding.id)}
                    data-testid={`investigation-finding-save-${finding.id}`}
                  >
                    <Check className="w-4 h-4 mr-1" />
                    {t('investigations.findings.save')}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      setEditingId(null)
                      setEditingBody('')
                    }}
                    data-testid={`investigation-finding-cancel-${finding.id}`}
                  >
                    <X className="w-4 h-4 mr-1" />
                    {t('investigations.findings.cancel')}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-3">
                <div className="flex gap-3">
                  <span className="text-sm text-muted-foreground tabular-nums">{index + 1}.</span>
                  <p
                    className="text-sm text-foreground whitespace-pre-wrap"
                    data-testid={`investigation-finding-body-${finding.id}`}
                  >
                    {finding.body}
                  </p>
                </div>
                {readOnly ? null : (
                  <div className="flex shrink-0 gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={t('investigations.findings.move_up')}
                      disabled={busy || index === 0}
                      onClick={() => void onMove(finding.id, -1)}
                      data-testid={`investigation-finding-up-${finding.id}`}
                    >
                      <ArrowUp className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={t('investigations.findings.move_down')}
                      disabled={busy || index === findings.length - 1}
                      onClick={() => void onMove(finding.id, 1)}
                      data-testid={`investigation-finding-down-${finding.id}`}
                    >
                      <ArrowDown className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={t('investigations.findings.edit_label')}
                      disabled={busy}
                      onClick={() => {
                        setEditingId(finding.id)
                        setEditingBody(finding.body)
                      }}
                      data-testid={`investigation-finding-edit-${finding.id}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={t('investigations.findings.delete')}
                      disabled={busy}
                      onClick={() => void onDelete(finding.id)}
                      data-testid={`investigation-finding-delete-${finding.id}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>

      {readOnly ? null : (
        <div className="space-y-2">
          <label
            htmlFor="inv-finding-new"
            className="block text-sm font-medium text-muted-foreground"
          >
            {t('investigations.findings.add_label')}
          </label>
          <Textarea
            id="inv-finding-new"
            rows={3}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={t('investigations.findings.add_placeholder')}
            data-testid="investigation-finding-new-input"
          />
          <Button
            size="sm"
            disabled={!canAdd}
            onClick={() => void handleAdd()}
            data-testid="investigation-finding-add"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-2" />
            )}
            {t('investigations.findings.add')}
          </Button>
        </div>
      )}
    </div>
  )
}
