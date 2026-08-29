import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ClipboardCheck, Loader2 } from 'lucide-react'
import { auditsApi, getApiErrorMessage, type AuditRun } from '../api/client'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { toast } from '../contexts/ToastContext'
import { isShowableAssignedAudit } from './portalAssignedAuditsHonesty'

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; items: AuditRun[]; total: number }
  | { status: 'error'; message: string }

function formatWhen(value?: string): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString()
}

export default function PortalAudits() {
  const navigate = useNavigate()
  const { announce } = useLiveAnnouncer()
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  const load = useCallback(async () => {
    setState({ status: 'loading' })
    try {
      const response = await auditsApi.listAssignedToMe(1, 100)
      const items = (response.data.items ?? []).filter(isShowableAssignedAudit)
      const total = typeof response.data.total === 'number' ? items.length : items.length
      setState({ status: 'ready', items, total })
    } catch (err) {
      const message = getApiErrorMessage(err)
      toast.error(message)
      setState({ status: 'error', message })
    }
  }, [])

  useEffect(() => {
    announce('Assigned audits loaded')
  }, [announce])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div data-testid="portal-audits" className="min-h-screen bg-surface">
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            type="button"
            aria-label="Back to portal home"
            onClick={() => navigate('/portal')}
            className="w-11 h-11 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-primary" />
            <span className="font-semibold text-foreground">Audits</span>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Assigned to you</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Opening an audit uses the staff audit workspace. You will leave the Employee Portal.
          </p>
        </div>

        {state.status === 'loading' ? (
          <div className="flex items-center gap-2 text-muted-foreground" data-testid="portal-audits-loading">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading assigned audits
          </div>
        ) : null}

        {state.status === 'error' ? (
          <Card className="p-4 border-amber-500/30 bg-amber-500/5" data-testid="portal-audits-error">
            <p className="font-medium text-foreground">Couldn’t load assigned audits</p>
            <p className="text-sm text-muted-foreground mt-1">{state.message}</p>
            <Button type="button" className="mt-3 min-h-11" onClick={() => void load()}>
              Try again
            </Button>
          </Card>
        ) : null}

        {state.status === 'ready' && state.items.length === 0 ? (
          <EmptyState
            icon={<ClipboardCheck className="w-8 h-8 text-muted-foreground" />}
            title="No audits assigned to you"
            description="When a manager assigns you an inspection, it will show here. This is not a fake zero from a failed request."
          />
        ) : null}

        {state.status === 'ready'
          ? state.items.map((run) => {
              const when = formatWhen(run.scheduled_date)
              return (
                <Card key={run.id} className="p-4" data-testid={`portal-audit-row-${run.id}`}>
                  <p className="text-xs text-muted-foreground">{run.reference_number}</p>
                  <h2 className="font-semibold text-foreground mt-1">
                    {run.title || run.reference_number}
                  </h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    {[run.location, when, run.status].filter(Boolean).join(' · ')}
                  </p>
                  <Button
                    type="button"
                    className="mt-4 min-h-11 w-full"
                    data-testid={`portal-audit-open-${run.id}`}
                    aria-label={`Open ${run.reference_number} in the staff audit workspace`}
                    onClick={() => navigate(`/audits/${run.id}/execute`)}
                  >
                    Open in audit workspace
                  </Button>
                </Card>
              )
            })
          : null}
      </main>
    </div>
  )
}
