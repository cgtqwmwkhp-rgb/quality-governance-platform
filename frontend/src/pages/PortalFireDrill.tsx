import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Flame, Loader2 } from 'lucide-react'
import api from '../api/client'
import {
  createPortalFireDrillApi,
  type PortalFireDrillItem,
  type PortalFireDrillList,
  type PortalFireDrillStatus,
} from '../api/portalFireDrillClient'
import { Card } from '../components/ui/Card'
import { cn } from '../helpers/utils'

const portalFireDrillApi = createPortalFireDrillApi(api)

const STATUS_LABEL: Record<PortalFireDrillStatus, string> = {
  overdue: 'Overdue',
  due_soon: 'Due soon',
  current: 'Current',
}

function statusTone(status?: PortalFireDrillStatus | null): string {
  if (status === 'overdue') return 'bg-destructive/10 text-destructive'
  if (status === 'due_soon') return 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
  return 'bg-muted text-muted-foreground'
}

export default function PortalFireDrill() {
  const navigate = useNavigate()
  const [data, setData] = useState<PortalFireDrillList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<PortalFireDrillItem | null>(null)
  const [notes, setNotes] = useState('')
  const [checkPassed, setCheckPassed] = useState(true)
  const [photo, setPhoto] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [successRef, setSuccessRef] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    void portalFireDrillApi
      .list()
      .then(setData)
      .catch(() => setError('Could not load fire drills. Try again when online.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const evidenceSupported = data?.evidence_capture_supported === true

  const handleComplete = async () => {
    if (!selected) return
    setSubmitting(true)
    setError(null)
    try {
      // v1: evidence upload not supported — notes + check_passed only.
      // Photo input is shown only when the API advertises evidence support.
      if (evidenceSupported && photo) {
        setError('Evidence upload is not available yet. Complete with notes instead.')
        setSubmitting(false)
        return
      }
      const record = await portalFireDrillApi.complete(selected.id, {
        notes: notes.trim() || null,
        check_passed: checkPassed,
      })
      setSuccessRef(record.reference_number)
      setSelected(null)
      setNotes('')
      setCheckPassed(true)
      setPhoto(null)
      reload()
    } catch {
      setError('Could not complete this fire drill. Check your connection and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div data-testid="portal-fire-drill" className="min-h-screen bg-surface">
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/portal')}
            className="p-2 hover:bg-surface rounded-lg"
            aria-label="Back to portal home"
          >
            <ArrowLeft className="w-5 h-5 text-muted-foreground" />
          </button>
          <div>
            <h1 className="text-foreground font-semibold">Fire drills</h1>
            <p className="text-muted-foreground text-xs">Obligations assigned to you</p>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 space-y-4">
        {loading && (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        )}

        {error && (
          <Card
            className="p-4 border-destructive/30 bg-destructive/5"
            data-testid="portal-fire-drill-error"
          >
            <p className="text-sm text-destructive">{error}</p>
          </Card>
        )}

        {successRef && (
          <Card
            className="p-4 border-emerald-500/30 bg-emerald-500/5"
            data-testid="portal-fire-drill-success"
          >
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-foreground">Drill recorded</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Reference {successRef}
                </p>
              </div>
            </div>
          </Card>
        )}

        {!loading && !error && data && data.items.length === 0 && (
          <Card className="p-6 text-center" data-testid="portal-fire-drill-empty">
            <Flame className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-foreground font-medium">No fire drills assigned</p>
            <p className="text-sm text-muted-foreground mt-1">
              When you are the owner of an active fire-drill obligation, it will
              appear here.
            </p>
          </Card>
        )}

        {!loading &&
          data?.items.map((item) => (
            <Card
              key={item.id}
              className="p-4"
              data-testid={`portal-fire-drill-${item.id}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-foreground truncate">{item.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {item.reference_number}
                    {item.location_name ? ` · ${item.location_name}` : ''}
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Due {new Date(item.next_due_date).toLocaleDateString('en-GB')}
                  </p>
                </div>
                {item.status && (
                  <span
                    className={cn(
                      'shrink-0 text-xs font-semibold px-2 py-1 rounded-md',
                      statusTone(item.status),
                    )}
                  >
                    {STATUS_LABEL[item.status]}
                  </span>
                )}
              </div>
              <button
                type="button"
                className="mt-4 w-full rounded-lg bg-primary text-primary-foreground text-sm font-medium py-2.5"
                onClick={() => {
                  setSelected(item)
                  setSuccessRef(null)
                  setNotes('')
                  setCheckPassed(true)
                  setPhoto(null)
                }}
              >
                Record completion
              </button>
            </Card>
          ))}

        {selected && (
          <Card className="p-4 space-y-4" data-testid="portal-fire-drill-complete-form">
            <div>
              <p className="font-semibold text-foreground">{selected.title}</p>
              <p className="text-xs text-muted-foreground">{selected.reference_number}</p>
            </div>

            <label className="block space-y-1.5">
              <span className="text-sm text-foreground">Notes</span>
              <textarea
                className="w-full min-h-[96px] rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Muster point, attendance, issues observed…"
              />
            </label>

            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={checkPassed}
                onChange={(e) => setCheckPassed(e.target.checked)}
                className="rounded border-border"
              />
              Drill passed (uncheck if a corrective action is needed)
            </label>

            {evidenceSupported && (
              <label className="block space-y-1.5">
                <span className="text-sm text-foreground">Photo evidence</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="block w-full text-sm text-muted-foreground"
                  onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
                />
              </label>
            )}

            <div className="flex gap-2">
              <button
                type="button"
                className="flex-1 rounded-lg border border-border py-2.5 text-sm"
                onClick={() => setSelected(null)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="flex-1 rounded-lg bg-primary text-primary-foreground py-2.5 text-sm font-medium disabled:opacity-60"
                onClick={() => void handleComplete()}
                disabled={submitting}
              >
                {submitting ? 'Saving…' : 'Complete'}
              </button>
            </div>
          </Card>
        )}
      </main>
    </div>
  )
}
