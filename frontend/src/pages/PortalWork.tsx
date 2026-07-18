import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  ArrowLeft,
  BookOpen,
  Briefcase,
  ClipboardList,
  ExternalLink,
  IdCard,
  Loader2,
} from 'lucide-react'
import {
  actionsApi,
  documentCampaignApi,
  engineersApi,
  getApiErrorMessage,
  policyAcknowledgmentsApi,
  type Action,
  type DocumentCampaignAssignment,
  type PolicyAcknowledgment,
} from '../api/client'
import type { EngineerSelfProfile } from '../api/engineersClient'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { toast } from '../contexts/ToastContext'

type LoadState<T> = {
  items: T[]
  loading: boolean
  error: string | null
}

type PassportState =
  | { status: 'loading' }
  | { status: 'linked'; engineer: EngineerSelfProfile }
  | { status: 'unlinked' }
  | { status: 'error'; message: string }

function isNotFound(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 404
}

function reportFailure(err: unknown): string {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

function formatDue(due?: string | null): string | null {
  if (!due) return null
  const d = new Date(due)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString()
}

function isOverdue(due?: string | null, status?: string): boolean {
  if (!due) return false
  if (status && ['completed', 'closed', 'cancelled', 'verified'].includes(status)) return false
  const d = new Date(due)
  if (Number.isNaN(d.getTime())) return false
  return d.getTime() < Date.now()
}

export default function PortalWork() {
  const navigate = useNavigate()
  const { announce } = useLiveAnnouncer()

  const [actions, setActions] = useState<LoadState<Action>>({
    items: [],
    loading: true,
    error: null,
  })
  const [reading, setReading] = useState<LoadState<PolicyAcknowledgment>>({
    items: [],
    loading: true,
    error: null,
  })
  const [campaigns, setCampaigns] = useState<LoadState<DocumentCampaignAssignment>>({
    items: [],
    loading: true,
    error: null,
  })
  const [passport, setPassport] = useState<PassportState>({ status: 'loading' })

  const loadActions = useCallback(async () => {
    setActions((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const response = await actionsApi.list(1, 20, undefined, undefined, undefined, {
        assigned_to: 'me',
      })
      setActions({
        items: response.data.items ?? [],
        loading: false,
        error: null,
      })
    } catch (err) {
      setActions({ items: [], loading: false, error: reportFailure(err) })
    }
  }, [])

  const loadReading = useCallback(async () => {
    setReading((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const response = await policyAcknowledgmentsApi.listMyPending()
      setReading({
        items: response.data.items ?? [],
        loading: false,
        error: null,
      })
    } catch (err) {
      setReading({ items: [], loading: false, error: reportFailure(err) })
    }
  }, [])

  const loadCampaigns = useCallback(async () => {
    setCampaigns((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const response = await documentCampaignApi.listMyAssignments()
      const pending = (response.data.items ?? []).filter((item) => item.status !== 'completed')
      setCampaigns({
        items: pending,
        loading: false,
        error: null,
      })
    } catch (err) {
      setCampaigns({ items: [], loading: false, error: reportFailure(err) })
    }
  }, [])

  const loadPassport = useCallback(async () => {
    setPassport({ status: 'loading' })
    try {
      const response = await engineersApi.getByUserMe()
      const profile = response.data
      if (!profile.linked || profile.id == null) {
        setPassport({ status: 'unlinked' })
        return
      }
      setPassport({ status: 'linked', engineer: profile })
    } catch (err) {
      if (isNotFound(err)) {
        setPassport({ status: 'unlinked' })
        return
      }
      setPassport({ status: 'error', message: reportFailure(err) })
    }
  }, [])

  useEffect(() => {
    announce('My Work inbox loaded')
    void loadActions()
    void loadReading()
    void loadCampaigns()
    void loadPassport()
  }, [announce, loadActions, loadReading, loadCampaigns, loadPassport])

  const handleOpenReading = async (item: PolicyAcknowledgment) => {
    try {
      await policyAcknowledgmentsApi.recordOpen(item.id)
      // Portal cannot host document ack theatre — open in full app for real read.
      window.open(`/documents/${item.policy_id}?tab=qa`, '_blank', 'noopener,noreferrer')
    } catch (err) {
      reportFailure(err)
    }
  }

  const overdueCount = actions.items.filter((a) => isOverdue(a.due_date, a.display_status || a.status))
    .length
  const pendingReadingCount = reading.items.length + campaigns.items.length

  return (
    <div data-testid="portal-work" className="min-h-screen bg-surface">
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            type="button"
            aria-label="Back to portal home"
            onClick={() => navigate('/portal')}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-primary" />
            <span className="font-semibold text-foreground">My Work</span>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Your inbox</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Assigned actions, pending reading, and profile link state — from the server, not a local
            guess.
          </p>
          {!actions.loading && !actions.error && (
            <p
              data-testid="portal-work-actions-filter-label"
              className="text-xs text-muted-foreground mt-2"
            >
              Showing actions assigned to you (server filter: assigned_to=me)
              {overdueCount > 0 ? ` · ${overdueCount} overdue on this page` : ''}.
            </p>
          )}
        </div>

        {/* Assigned actions */}
        <section data-testid="portal-work-actions" aria-labelledby="portal-work-actions-heading">
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList className="w-5 h-5 text-primary" />
            <h2 id="portal-work-actions-heading" className="font-semibold text-foreground">
              Assigned actions
            </h2>
          </div>

          {actions.loading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="w-7 h-7 text-primary animate-spin" />
            </div>
          ) : actions.error ? (
            <div
              data-testid="portal-work-actions-error"
              className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {actions.error}
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={() => void loadActions()}>
                  Retry
                </Button>
              </div>
            </div>
          ) : actions.items.length === 0 ? (
            <EmptyState
              className="py-10"
              icon={<ClipboardList className="w-8 h-8 text-muted-foreground" />}
              title="No actions assigned to you"
              description="When a supervisor assigns you a CAPA or corrective action, it will appear here."
            />
          ) : (
            <div className="space-y-3">
              {actions.items.map((action) => {
                const overdue = isOverdue(action.due_date, action.display_status || action.status)
                const dueLabel = formatDue(action.due_date)
                return (
                  <Card key={action.action_key || action.id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <Badge variant="submitted">
                            {action.display_status || action.status}
                          </Badge>
                          {overdue && <Badge variant="destructive">Overdue</Badge>}
                          {action.reference_number && (
                            <span className="text-xs text-muted-foreground">
                              {action.reference_number}
                            </span>
                          )}
                        </div>
                        <p className="font-medium text-foreground truncate">{action.title}</p>
                        {dueLabel && (
                          <p className="text-sm text-muted-foreground mt-0.5">Due {dueLabel}</p>
                        )}
                      </div>
                      <Button variant="outline" size="sm" asChild>
                        <a
                          href={`/actions/${encodeURIComponent(action.action_key)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Open ${action.title} in full app`}
                        >
                          <ExternalLink className="w-4 h-4 mr-1" />
                          Full app
                        </a>
                      </Button>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </section>

        {/* Pending reading */}
        <section data-testid="portal-work-reading" aria-labelledby="portal-work-reading-heading">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-5 h-5 text-primary" />
            <h2 id="portal-work-reading-heading" className="font-semibold text-foreground">
              Pending reading
            </h2>
            {pendingReadingCount > 0 && (
              <span
                data-testid="portal-work-reading-count"
                className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold"
                aria-label={`${pendingReadingCount} pending reads`}
              >
                {pendingReadingCount}
              </span>
            )}
          </div>

          {reading.loading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="w-7 h-7 text-primary animate-spin" />
            </div>
          ) : reading.error ? (
            <div
              data-testid="portal-work-reading-error"
              className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {reading.error}
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={() => void loadReading()}>
                  Retry
                </Button>
              </div>
            </div>
          ) : reading.items.length === 0 && !campaigns.loading && campaigns.items.length === 0 ? (
            <EmptyState
              className="py-10"
              icon={<BookOpen className="w-8 h-8 text-muted-foreground" />}
              title="No pending reads"
              description="You have no policy acknowledgments or document campaigns waiting."
            />
          ) : (
            <div className="space-y-3">
              {campaigns.loading ? (
                <div className="flex justify-center py-6">
                  <Loader2 className="w-6 h-6 text-primary animate-spin" />
                </div>
              ) : campaigns.error ? (
                <div
                  data-testid="portal-work-campaigns-error"
                  className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                >
                  {campaigns.error}
                  <div className="mt-2">
                    <Button variant="outline" size="sm" onClick={() => void loadCampaigns()}>
                      Retry
                    </Button>
                  </div>
                </div>
              ) : campaigns.items.length > 0 ? (
                <div data-testid="portal-work-campaigns" className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground">Campaign assignments</span>
                    {campaigns.items.length > 0 && (
                      <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                        {campaigns.items.length}
                      </span>
                    )}
                  </div>
                  {campaigns.items.slice(0, 3).map((item) => (
                    <Card key={item.id} className="p-4">
                      <div className="space-y-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="submitted">{item.status}</Badge>
                            <Badge variant="outline">Campaign</Badge>
                          </div>
                          <p className="font-medium text-foreground">
                            {item.document_title ?? `Document #${item.document_id}`}
                          </p>
                          {item.campaign_title && (
                            <p className="text-sm text-muted-foreground">{item.campaign_title}</p>
                          )}
                          <p className="text-sm text-muted-foreground">
                            Due {formatDue(item.due_date ?? item.due_at) ?? '—'}
                          </p>
                        </div>
                        <Button
                          size="lg"
                          className="w-full min-h-12"
                          onClick={() =>
                            navigate(`/portal/reading?assignment=${item.id}`)
                          }
                        >
                          Continue reading
                        </Button>
                      </div>
                    </Card>
                  ))}
                  {campaigns.items.length > 3 && (
                    <Button
                      variant="outline"
                      size="lg"
                      className="w-full min-h-12"
                      onClick={() => navigate('/portal/reading')}
                    >
                      View all {campaigns.items.length} campaigns
                    </Button>
                  )}
                </div>
              ) : null}
              {reading.items.map((item) => (
                <Card key={item.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="submitted">{item.status}</Badge>
                        {item.policy_version && (
                          <span className="text-xs text-muted-foreground">
                            v{item.policy_version}
                          </span>
                        )}
                      </div>
                      <p className="font-medium text-foreground">Policy #{item.policy_id}</p>
                      <p className="text-sm text-muted-foreground">
                        Due {formatDue(item.due_date) ?? '—'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Open the document to read — no one-tap acknowledge on mobile.
                      </p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => void handleOpenReading(item)}>
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Open
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>

        {/* Passport / profile link */}
        <section
          data-testid="portal-work-passport-link"
          aria-labelledby="portal-work-passport-heading"
        >
          <div className="flex items-center gap-2 mb-3">
            <IdCard className="w-5 h-5 text-primary" />
            <h2 id="portal-work-passport-heading" className="font-semibold text-foreground">
              Workforce profile
            </h2>
          </div>

          {passport.status === 'loading' ? (
            <div className="flex justify-center py-10">
              <Loader2 className="w-7 h-7 text-primary animate-spin" />
            </div>
          ) : passport.status === 'error' ? (
            <div
              data-testid="portal-work-passport-error"
              className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {passport.message}
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={() => void loadPassport()}>
                  Retry
                </Button>
              </div>
            </div>
          ) : passport.status === 'unlinked' ? (
            <div data-testid="portal-work-passport-unlinked">
              <EmptyState
                className="py-10"
                icon={<IdCard className="w-8 h-8 text-muted-foreground" />}
                title="Profile not linked"
                description="Contact your supervisor to link your workforce engineer profile. Competency passport details will appear here once linked — we will not show fake green ticks."
              />
            </div>
          ) : (
            <Card className="p-4" data-testid="portal-work-passport-linked">
              <p className="font-medium text-foreground">
                {passport.engineer.job_title || 'Engineer profile linked'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {[passport.engineer.employee_number, passport.engineer.department, passport.engineer.site]
                  .filter(Boolean)
                  .join(' · ') || `Engineer #${passport.engineer.id ?? '—'}`}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Competency matrix and training tickets live in the full workforce passport (separate
                CUJ) — this inbox only confirms your identity link.
              </p>
              <div className="mt-3">
                <Button variant="outline" size="sm" asChild>
                  <a
                    href={`/workforce/engineers/${passport.engineer.id ?? ''}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink className="w-4 h-4 mr-1" />
                    Open in full app
                  </a>
                </Button>
              </div>
            </Card>
          )}
        </section>
      </main>
    </div>
  )
}
