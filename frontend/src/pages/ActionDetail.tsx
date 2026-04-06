import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Copy,
  Download,
  ExternalLink,
  Link2,
  Loader2,
  MessageSquare,
  Paperclip,
  RefreshCw,
  Save,
  Trash2,
} from 'lucide-react'
import {
  actionsApi,
  Action as ApiAction,
  ActionOwnerNote,
  ActionUpdate,
  evidenceAssetsApi,
  EvidenceAsset,
  getApiErrorMessage,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'

const MAX_EVIDENCE_FILE_SIZE_BYTES = 50 * 1024 * 1024
/** Matches `ActionOwnerNoteCreate.body` max_length on the API. */
const MAX_NOTE_BODY_CHARS = 16000

/** Matches backend allowlist in `src/api/routes/evidence_assets.py` (subset for picker UX). */
const EVIDENCE_FILE_INPUT_ACCEPT =
  'image/jpeg,image/png,image/gif,image/webp,image/heic,image/heif,video/mp4,video/webm,video/quicktime,application/pdf,.pdf,.doc,.docx,.xls,.xlsx,audio/mpeg,audio/wav,audio/ogg'

function formatRelativeTime(iso: string): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const sec = Math.round((Date.now() - t) / 1000)
  if (sec < 45) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const h = Math.round(min / 60)
  if (h < 48) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 14) return `${d}d ago`
  return ''
}

function formatFileSize(bytes: number | undefined): string {
  if (bytes == null || Number.isNaN(bytes) || bytes < 0) return ''
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`
  const mb = kb / 1024
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`
}

const SUPPORTED_EVIDENCE_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/heic',
  'image/heif',
  'video/mp4',
  'video/webm',
  'video/quicktime',
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'audio/mpeg',
  'audio/wav',
  'audio/ogg',
]

export default function ActionDetail() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const key = searchParams.get('key') || ''
  const [action, setAction] = useState<ApiAction | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [statusDraft, setStatusDraft] = useState<string>('')

  const [notes, setNotes] = useState<ActionOwnerNote[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [noteDraft, setNoteDraft] = useState('')
  const [postingNote, setPostingNote] = useState(false)

  const [evidence, setEvidence] = useState<EvidenceAsset[]>([])
  const [evidenceLoading, setEvidenceLoading] = useState(false)
  const [uploadingEvidence, setUploadingEvidence] = useState(false)
  const [evidenceSort, setEvidenceSort] = useState<'uploaded' | 'name'>('uploaded')
  const [copyFlash, setCopyFlash] = useState<'key' | 'link' | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const notesListRef = useRef<HTMLUListElement>(null)
  const [inlineMessage, setInlineMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)

  const fetchNotesAndEvidence = useCallback(async (actionKey: string, showLoadError: boolean) => {
    setNotesLoading(true)
    setEvidenceLoading(true)
    try {
      const [notesRes, evRes] = await Promise.all([
        actionsApi.listOwnerNotes(actionKey, 100),
        evidenceAssetsApi.list({ action_key: actionKey, page_size: 50 }),
      ])
      setNotes(notesRes.data.items || [])
      setEvidence(evRes.data.items || [])
    } catch (e: unknown) {
      setNotes([])
      setEvidence([])
      if (showLoadError) {
        setInlineMessage({
          tone: 'error',
          text: getApiErrorMessage(e, 'Notes or attachments could not be loaded. Use Refresh to retry.'),
        })
      }
    } finally {
      setNotesLoading(false)
      setEvidenceLoading(false)
    }
  }, [])

  const load = useCallback(async () => {
    if (!key.trim()) {
      setError('Missing key')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    setInlineMessage(null)
    try {
      const res = await actionsApi.getByKey(key.trim())
      setAction(res.data)
      setStatusDraft(res.data.display_status || res.data.status)
      await fetchNotesAndEvidence(res.data.action_key, true)
    } catch (e: unknown) {
      setError(getApiErrorMessage(e, 'Could not load this action.'))
      setAction(null)
    } finally {
      setLoading(false)
    }
  }, [key, fetchNotesAndEvidence])

  useEffect(() => {
    load()
  }, [load])

  const sortedEvidence = useMemo(() => {
    const arr = [...evidence]
    if (evidenceSort === 'name') {
      arr.sort((a, b) =>
        (a.title || a.original_filename || '').localeCompare(b.title || b.original_filename || '', undefined, {
          sensitivity: 'base',
        }),
      )
    } else {
      arr.sort((a, b) => {
        const ta = new Date(a.created_at || 0).getTime()
        const tb = new Date(b.created_at || 0).getTime()
        return tb - ta
      })
    }
    return arr
  }, [evidence, evidenceSort])

  useEffect(() => {
    if (!action) {
      document.title = 'Action'
      return
    }
    const t = action.title?.trim() || action.action_key
    document.title = `${t} · Action`
    return () => {
      document.title = 'Action'
    }
  }, [action])

  const saveStatus = async () => {
    if (!action) return
    setSaving(true)
    setError(null)
    try {
      const payload: ActionUpdate = { status: statusDraft }
      const res = await actionsApi.update(action.id, action.source_type, payload)
      setAction(res.data)
      setStatusDraft(res.data.display_status || res.data.status)
    } catch (e: unknown) {
      setError(getApiErrorMessage(e, 'Update failed. Check permissions and status value.'))
    } finally {
      setSaving(false)
    }
  }

  const submitNote = async () => {
    if (!action || !noteDraft.trim()) return
    const body = noteDraft.trim()
    if (body.length > MAX_NOTE_BODY_CHARS) {
      setInlineMessage({
        tone: 'error',
        text: `Note is too long (max ${MAX_NOTE_BODY_CHARS} characters).`,
      })
      return
    }
    setPostingNote(true)
    setInlineMessage(null)
    try {
      const res = await actionsApi.appendOwnerNote(action.action_key, body)
      setNotes((prev) => [res.data, ...prev])
      setNoteDraft('')
      setInlineMessage({ tone: 'success', text: 'Note added.' })
      window.requestAnimationFrame(() => {
        notesListRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      })
    } catch (e: unknown) {
      setInlineMessage({
        tone: 'error',
        text: getApiErrorMessage(e, 'Could not add note. Check permissions and try again.'),
      })
    } finally {
      setPostingNote(false)
    }
  }

  const handleEvidenceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!action || !e.target.files?.length) return
    setUploadingEvidence(true)
    const files = Array.from(e.target.files)
    try {
      let index = 0
      for (const file of files) {
        index += 1
        if (files.length > 1) {
          setInlineMessage({ tone: 'success', text: `Uploading file ${index} of ${files.length}…` })
        }
        const okMime =
          SUPPORTED_EVIDENCE_MIME_TYPES.includes(file.type) ||
          file.type.startsWith('image/') ||
          file.type.startsWith('video/')
        if (!okMime) {
          throw new Error(
            `${file.name} is not a supported type. Use images, PDF, Office documents, video, or audio listed in the evidence module.`,
          )
        }
        if (file.size > MAX_EVIDENCE_FILE_SIZE_BYTES) {
          throw new Error(`${file.name} exceeds the 50MB upload limit.`)
        }
        await evidenceAssetsApi.upload(file, {
          source_module: 'action',
          source_id: 0,
          action_key: action.action_key,
          title: file.name,
          visibility: 'internal_customer',
        })
      }
      const evRes = await evidenceAssetsApi.list({ action_key: action.action_key, page_size: 50 })
      setEvidence(evRes.data.items || [])
      const n = files.length
      setInlineMessage({
        tone: 'success',
        text: n === 1 ? 'Uploaded 1 file.' : `Uploaded ${n} files.`,
      })
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : getApiErrorMessage(err, 'Upload failed. Check file type, size (max 50MB), and permissions.')
      setInlineMessage({ tone: 'error', text: msg })
    } finally {
      setUploadingEvidence(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const downloadAsset = async (assetId: number) => {
    setInlineMessage(null)
    try {
      const res = await evidenceAssetsApi.getSignedUrl(assetId)
      window.open(res.data.signed_url, '_blank', 'noopener,noreferrer')
    } catch (e: unknown) {
      setInlineMessage({
        tone: 'error',
        text: getApiErrorMessage(e, 'Could not open download link.'),
      })
    }
  }

  const deleteAsset = async (assetId: number) => {
    if (!action) return
    if (
      !window.confirm(
        'Remove this attachment from the action? The file may remain in storage per retention policy.',
      )
    ) {
      return
    }
    try {
      await evidenceAssetsApi.delete(assetId)
      const evRes = await evidenceAssetsApi.list({ action_key: action.action_key, page_size: 50 })
      setEvidence(evRes.data.items || [])
      setInlineMessage({ tone: 'success', text: 'Attachment removed.' })
    } catch (e: unknown) {
      setInlineMessage({
        tone: 'error',
        text: getApiErrorMessage(e, 'Could not remove attachment.'),
      })
    }
  }

  const pageUrl =
    typeof window !== 'undefined'
      ? `${window.location.origin}${location.pathname}${location.search}`
      : ''

  const copyToClipboard = async (text: string, flash: 'key' | 'link') => {
    try {
      await navigator.clipboard.writeText(text)
      setCopyFlash(flash)
      window.setTimeout(() => setCopyFlash(null), 2000)
    } catch {
      setInlineMessage({ tone: 'error', text: 'Clipboard not available.' })
    }
  }

  if (!key.trim()) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Open an action from the Actions list.</p>
        <Button variant="outline" className="mt-4" asChild>
          <Link to="/actions">Back to Actions</Link>
        </Button>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        Loading…
      </div>
    )
  }

  if (error || !action) {
    return (
      <div className="p-6 space-y-4">
        <p className="text-destructive">{error || 'Not found'}</p>
        <Button variant="outline" asChild>
          <Link to="/actions">Back to Actions</Link>
        </Button>
      </div>
    )
  }

  const statusDirty = statusDraft !== (action.display_status || action.status)

  return (
    <div className="space-y-6 p-4 max-w-3xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/actions">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Actions
          </Link>
        </Button>
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-mono text-primary">{action.action_key}</p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            aria-label="Copy action key"
            onClick={() => copyToClipboard(action.action_key, 'key')}
          >
            <Copy className="w-3.5 h-3.5 mr-1" />
            {copyFlash === 'key' ? 'Copied' : 'Copy key'}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            aria-label="Copy link to this page"
            onClick={() => pageUrl && copyToClipboard(pageUrl, 'link')}
          >
            <Link2 className="w-3.5 h-3.5 mr-1" />
            {copyFlash === 'link' ? 'Copied' : 'Copy link'}
          </Button>
        </div>
        <h1 className="text-2xl font-bold text-foreground mt-1">{action.title}</h1>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="secondary">{action.source_type}</Badge>
          <Badge variant="outline">{action.display_status}</Badge>
          <Badge variant="outline">raw: {action.status}</Badge>
          {action.priority ? (
            <Badge variant="outline">priority: {action.priority}</Badge>
          ) : null}
        </div>
        <dl className="mt-3 grid gap-1 text-sm text-muted-foreground sm:grid-cols-2">
          {action.due_date ? (
            <div>
              <dt className="inline font-medium text-foreground/80">Due</dt>{' '}
              <dd className="inline">
                {new Date(action.due_date).toLocaleString(undefined, {
                  dateStyle: 'medium',
                  timeStyle: undefined,
                })}
              </dd>
            </div>
          ) : null}
          {action.owner_email ? (
            <div>
              <dt className="inline font-medium text-foreground/80">Owner</dt>{' '}
              <dd className="inline">{action.owner_email}</dd>
            </div>
          ) : null}
          {action.assigned_to_email ? (
            <div>
              <dt className="inline font-medium text-foreground/80">Assignee</dt>{' '}
              <dd className="inline">{action.assigned_to_email}</dd>
            </div>
          ) : null}
          {action.completed_at ? (
            <div>
              <dt className="inline font-medium text-foreground/80">Completed</dt>{' '}
              <dd className="inline">
                {new Date(action.completed_at).toLocaleString(undefined, {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </dd>
            </div>
          ) : null}
        </dl>
        {action.completion_notes?.trim() ? (
          <div className="mt-3 rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Completion notes
            </p>
            <p className="text-sm text-foreground whitespace-pre-wrap mt-1">{action.completion_notes}</p>
          </div>
        ) : null}
      </div>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div aria-live="polite" aria-atomic="true">
            {inlineMessage ? (
              <p
                className={
                  inlineMessage.tone === 'success'
                    ? 'text-sm text-green-700 dark:text-green-400'
                    : 'text-sm text-destructive'
                }
                role="status"
              >
                {inlineMessage.text}
              </p>
            ) : null}
          </div>
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Description
            </p>
            <p className="text-foreground whitespace-pre-wrap mt-1">{action.description || '—'}</p>
          </div>

          {action.source_type === 'audit_finding' && action.audit_run_id ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link to={`/audits/${action.audit_run_id}/execute`}>
                  Open audit run
                  <ExternalLink className="w-3 h-3 ml-1" />
                </Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link to={`/audits/${action.audit_run_id}/import-review`}>Import review</Link>
              </Button>
            </div>
          ) : null}

          <div className="border-t border-border pt-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-foreground flex items-center gap-2">
                <MessageSquare className="w-4 h-4" />
                Owner commentary
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!action || notesLoading || evidenceLoading}
                onClick={() => action && fetchNotesAndEvidence(action.action_key, false)}
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                Refresh
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Each entry is stored with your account and a server timestamp (newest first). Up to 100 notes
              are shown.
            </p>
            <form
              className="space-y-2"
              onSubmit={(e) => {
                e.preventDefault()
                submitNote()
              }}
            >
              <Textarea
                value={noteDraft}
                onChange={(e) => {
                  const v = e.target.value
                  setNoteDraft(v.length > MAX_NOTE_BODY_CHARS ? v.slice(0, MAX_NOTE_BODY_CHARS) : v)
                }}
                onKeyDown={(e) => {
                  if (e.key !== 'Enter' || !(e.metaKey || e.ctrlKey)) return
                  e.preventDefault()
                  if (!postingNote && noteDraft.trim()) void submitNote()
                }}
                placeholder="Add an update for this action…"
                rows={3}
                maxLength={MAX_NOTE_BODY_CHARS}
                className="resize-y min-h-[80px]"
                disabled={postingNote}
                aria-label="Owner commentary text"
              />
              <p className="text-xs text-muted-foreground">
                {noteDraft.length} / {MAX_NOTE_BODY_CHARS} ·{' '}
                <kbd className="rounded border border-border px-1 text-[10px]">⌘</kbd>/
                <kbd className="rounded border border-border px-1 text-[10px]">Ctrl</kbd>+
                <kbd className="rounded border border-border px-1 text-[10px]">Enter</kbd> to submit
              </p>
              <Button type="submit" disabled={postingNote || !noteDraft.trim()}>
                {postingNote ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                Add note
              </Button>
            </form>
            {notesLoading ? (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading notes…
              </p>
            ) : notes.length === 0 ? (
              <p className="text-sm text-muted-foreground">No notes yet.</p>
            ) : (
              <ul
                ref={notesListRef}
                className="space-y-3 border border-border rounded-md p-3 bg-muted/30"
              >
                {notes.map((n) => {
                  const rel = n.created_at ? formatRelativeTime(n.created_at) : ''
                  return (
                    <li key={n.id} className="text-sm border-b border-border/60 last:border-0 pb-3 last:pb-0">
                      <p className="text-xs text-muted-foreground">
                        {n.author_email || `User #${n.author_id}`}
                        {' · '}
                        {n.created_at ? (
                          <>
                            {rel ? <span>{rel} · </span> : null}
                            {new Date(n.created_at).toLocaleString(undefined, {
                              dateStyle: 'medium',
                              timeStyle: 'short',
                            })}
                          </>
                        ) : (
                          '—'
                        )}
                      </p>
                      <p className="text-foreground whitespace-pre-wrap mt-1">{n.body}</p>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          <div className="border-t border-border pt-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-foreground flex items-center gap-2">
                <Paperclip className="w-4 h-4" />
                Documents & evidence
              </p>
              {evidence.length > 0 ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="sr-only" id="evidence-sort-label">
                    Sort attachments
                  </span>
                  <Select
                    value={evidenceSort}
                    onValueChange={(v) => setEvidenceSort(v as 'uploaded' | 'name')}
                  >
                    <SelectTrigger className="h-8 w-[180px]" aria-labelledby="evidence-sort-label">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="uploaded">Newest uploaded</SelectItem>
                      <SelectItem value="name">Name (A–Z)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ) : null}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept={EVIDENCE_FILE_INPUT_ACCEPT}
              aria-label="Upload evidence files"
              onChange={handleEvidenceUpload}
            />
            <Button
              type="button"
              variant="secondary"
              disabled={uploadingEvidence}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadingEvidence ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : (
                <Paperclip className="w-4 h-4 mr-1" />
              )}
              Upload files
            </Button>
            {evidenceLoading ? (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading attachments…
              </p>
            ) : evidence.length === 0 ? (
              <p className="text-sm text-muted-foreground">No attachments yet.</p>
            ) : (
              <ul className="space-y-2">
                {sortedEvidence.map((a) => (
                  <li
                    key={a.id}
                    className="flex flex-wrap items-center justify-between gap-2 text-sm border border-border rounded-md px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="text-foreground block truncate">
                        {a.title || a.original_filename || `Asset #${a.id}`}
                      </span>
                      <span className="text-xs text-muted-foreground block truncate">
                        {[formatFileSize(a.file_size_bytes), a.content_type, a.asset_type]
                          .filter(Boolean)
                          .join(' · ')}
                        {a.created_at
                          ? ` · uploaded ${new Date(a.created_at).toLocaleString(undefined, {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })}`
                          : ''}
                      </span>
                    </div>
                    <span className="flex gap-1 shrink-0">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Download ${a.title || a.original_filename || 'attachment'}`}
                        onClick={() => downloadAsset(a.id)}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Remove ${a.title || a.original_filename || 'attachment'}`}
                        onClick={() => deleteAsset(a.id)}
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="border-t border-border pt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-foreground">Update status</p>
              {statusDirty ? (
                <Badge variant="outline" className="text-amber-800 dark:text-amber-200 border-amber-600/40">
                  Unsaved change
                </Badge>
              ) : null}
            </div>
            <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
              <div className="flex-1">
                <Select value={statusDraft} onValueChange={setStatusDraft}>
                  <SelectTrigger>
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">open</SelectItem>
                    <SelectItem value="in_progress">in_progress</SelectItem>
                    <SelectItem value="pending_verification">pending_verification</SelectItem>
                    <SelectItem value="completed">completed</SelectItem>
                    <SelectItem value="cancelled">cancelled</SelectItem>
                    <SelectItem value="closed">closed (CAPA)</SelectItem>
                    <SelectItem value="verification">verification (CAPA)</SelectItem>
                    <SelectItem value="overdue">overdue (CAPA)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" onClick={saveStatus} disabled={saving || !statusDirty}>
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-1" />
                )}
                Save
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Use values your source supports; CAPA rows accept closed / verification / overdue.
            </p>
          </div>

          <div className="border-t border-border pt-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Assignee email (optional)
            </p>
            <form
              className="flex flex-col sm:flex-row gap-2 mt-2"
              onSubmit={async (e) => {
                e.preventDefault()
                const fd = new FormData(e.currentTarget)
                const email = String(fd.get('email') || '').trim()
                if (!email || !action) return
                setSaving(true)
                try {
                  const res = await actionsApi.update(action.id, action.source_type, {
                    assigned_to_email: email,
                  })
                  setAction(res.data)
                } catch (err: unknown) {
                  setInlineMessage({
                    tone: 'error',
                    text: getApiErrorMessage(err, 'Could not update assignee.'),
                  })
                } finally {
                  setSaving(false)
                }
              }}
            >
              <Input name="email" type="email" placeholder="user@company.com" className="flex-1" />
              <Button type="submit" variant="secondary" disabled={saving}>
                Assign
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
