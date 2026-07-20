import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  ArrowLeft,
  BookOpen,
  Briefcase,
  ClipboardList,
  ExternalLink,
  GraduationCap,
  IdCard,
  Loader2,
} from 'lucide-react'
import {
  actionsApi,
  documentCampaignApi,
  engineersApi,
  getApiErrorMessage,
  policyAcknowledgmentsApi,
  trainingMatrixApi,
  type Action,
  type DocumentCampaignAssignment,
  type PolicyAcknowledgment,
  type TrainingMatrixComplianceRow,
} from '../api/client'
import { ATLAS_HUB_URL } from '../api/trainingMatrixClient'
import type { EngineerSelfProfile } from '../api/engineersClient'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { toast } from '../contexts/ToastContext'
import {
  partitionReadingQueue,
  portalCampaignReadingHref,
  unifiedReadingQueueCount,
} from './campaignReadingHelpers'
import {
  myTrainingSummary,
  statusLabel,
} from './workforce/trainingMatrix/trainingMatrixBoardHelpers'

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

type TrainingState =
  | { status: 'loading' }
  | { status: 'ready'; rows: TrainingMatrixComplianceRow[]; atlasUrl: string }
  | { status: 'unlinked' }
  | { status: 'error'; message: string }

function trainingBadgeVariant(status: string): BadgeVariant {
  if (status === 'compliant') return 'success'
  if (status === 'overdue' || status === 'failed' || status === 'missing') return 'destructive'
  if (status === 'due_soon') return 'warning'
  return 'submitted'
}

function openAtlas(url?: string | null) {
  window.open(url || ATLAS_HUB_URL, '_blank', 'noopener,noreferrer')
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
  const [training, setTraining] = useState<TrainingState>({ status: 'loading' })
  const [showCompliant, setShowCompliant] = useState(false)

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

  const loadTraining = useCallback(async () => {
    setTraining({ status: 'loading' })
    try {
      const res = await trainingMatrixApi.myTraining()
      setTraining({
        status: 'ready',
        rows: res.items || [],
        atlasUrl: res.atlas_hub_url || ATLAS_HUB_URL,
      })
    } catch (err) {
      if (isNotFound(err)) {
        setTraining({ status: 'unlinked' })
        return
      }
      setTraining({ status: 'error', message: reportFailure(err) })
    }
  }, [])

  useEffect(() => {
    announce('My Work inbox loaded')
    void loadActions()
    void loadReading()
    void loadCampaigns()
    void loadPassport()
    void loadTraining()
  }, [announce, loadActions, loadReading, loadCampaigns, loadPassport, loadTraining])

  const readingQueue = useMemo(
    () => partitionReadingQueue(reading.items, campaigns.items),
    [reading.items, campaigns.items],
  )
  const pendingReadingCount = unifiedReadingQueueCount(
    readingQueue.activeCampaigns,
    readingQueue.visiblePolicyAcks,
  )

  const trainingSummary = useMemo(
    () => (training.status === 'ready' ? myTrainingSummary(training.rows) : null),
    [training],
  )
  const trainingNeedsAttention = useMemo(
    () =>
      training.status === 'ready'
        ? training.rows
            .filter((row) => row.status !== 'compliant')
            .sort((a, b) => (a.qgp_due_on || '9999').localeCompare(b.qgp_due_on || '9999'))
        : [],
    [training],
  )
  const trainingCompliant = useMemo(
    () =>
      training.status === 'ready' ? training.rows.filter((row) => row.status === 'compliant') : [],
    [training],
  )

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
            Assigned actions, pending reading, training compliance, and profile link — from the
            server, not a local guess.
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

        {/* Training compliance (Atlas + QGP frequency) */}
        <section
          data-testid="portal-work-training"
          aria-labelledby="portal-work-training-heading"
        >
          <div className="flex items-center gap-2 mb-3">
            <GraduationCap className="w-5 h-5 text-primary" />
            <h2 id="portal-work-training-heading" className="font-semibold text-foreground">
              Training compliance
            </h2>
            {trainingNeedsAttention.length > 0 ? (
              <span
                data-testid="portal-work-training-gap-count"
                className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-destructive/10 text-destructive text-xs font-semibold"
                aria-label={`${trainingNeedsAttention.length} modules need attention`}
              >
                {trainingNeedsAttention.length}
              </span>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground mb-3">
            Due dates use Atlas Passed dates plus Plantexpand frequency rules. Complete training in
            Atlas — QGP is not an LMS.
          </p>

          {training.status === 'loading' ? (
            <div className="flex justify-center py-10">
              <Loader2 className="w-7 h-7 text-primary animate-spin" />
            </div>
          ) : training.status === 'error' ? (
            <div
              data-testid="portal-work-training-error"
              className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {training.message}
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={() => void loadTraining()}>
                  Retry
                </Button>
              </div>
            </div>
          ) : training.status === 'unlinked' ? (
            <div data-testid="portal-work-training-unlinked">
              <EmptyState
                className="py-10"
                icon={<GraduationCap className="w-8 h-8 text-muted-foreground" />}
                title="Training not linked yet"
                description="Your login must be linked to a workforce profile and mapped to your Atlas name before personal compliance appears. Ask your supervisor if this is missing."
              />
            </div>
          ) : training.rows.length === 0 ? (
            <EmptyState
              className="py-10"
              icon={<GraduationCap className="w-8 h-8 text-muted-foreground" />}
              title="No required modules on file"
              description="Once the weekly Atlas matrix is uploaded and your name is mapped, your modules will show here."
            />
          ) : (
            <div className="space-y-3">
              <Card className="p-4" data-testid="portal-work-training-summary">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">
                      {trainingSummary?.okCount}/{trainingSummary?.total} modules OK
                    </p>
                    {trainingSummary?.nextDue ? (
                      <p className="text-sm text-muted-foreground mt-0.5">
                        Next due: {trainingSummary.nextDue.course_display_name} on{' '}
                        {formatDue(trainingSummary.nextDue.qgp_due_on) ??
                          trainingSummary.nextDue.qgp_due_on}
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground mt-0.5">
                        Nothing outstanding right now.
                      </p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    data-testid="portal-work-training-atlas"
                    onClick={() => openAtlas(training.atlasUrl)}
                  >
                    <ExternalLink className="w-4 h-4 mr-1" />
                    Open Atlas
                  </Button>
                </div>
              </Card>

              {trainingNeedsAttention.length > 0 ? (
                <div className="space-y-2" data-testid="portal-work-training-gaps">
                  <p className="text-sm font-medium text-muted-foreground">Needs attention</p>
                  {trainingNeedsAttention.map((row) => (
                    <Card key={`${row.course_key}-${row.atlas_name}`} className="p-4">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={trainingBadgeVariant(row.status)}>
                            {statusLabel(row)}
                          </Badge>
                          {row.expires_on ? (
                            <span className="text-xs text-muted-foreground">
                              Atlas expiry {formatDue(row.expires_on) ?? row.expires_on}
                            </span>
                          ) : null}
                        </div>
                        <p className="font-medium text-foreground">{row.course_display_name}</p>
                        <p className="text-sm text-muted-foreground">
                          QGP due{' '}
                          {formatDue(row.qgp_due_on) ?? row.qgp_due_on ?? 'not set'}
                          {row.passed_on
                            ? ` · last passed ${formatDue(row.passed_on) ?? row.passed_on}`
                            : ' · no Passed date in Atlas'}
                        </p>
                        <Button
                          size="lg"
                          className="w-full min-h-12"
                          onClick={() => openAtlas(row.atlas_hub_url || training.atlasUrl)}
                        >
                          <ExternalLink className="w-4 h-4 mr-2" />
                          Complete in Atlas
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : null}

              {trainingCompliant.length > 0 ? (
                <div data-testid="portal-work-training-ok">
                  <button
                    type="button"
                    className="text-sm font-medium text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() => setShowCompliant((v) => !v)}
                    aria-expanded={showCompliant}
                  >
                    {showCompliant ? 'Hide' : 'Show'} {trainingCompliant.length} compliant module
                    {trainingCompliant.length === 1 ? '' : 's'}
                  </button>
                  {showCompliant ? (
                    <div className="mt-2 space-y-2">
                      {trainingCompliant.map((row) => (
                        <Card key={`${row.course_key}-ok`} className="p-3">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex flex-wrap items-center gap-2 mb-1">
                                <Badge variant="success">{statusLabel(row)}</Badge>
                              </div>
                              <p className="font-medium text-foreground text-sm">
                                {row.course_display_name}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                QGP due {formatDue(row.qgp_due_on) ?? row.qgp_due_on ?? '—'}
                                {row.expires_on
                                  ? ` · Atlas expiry ${formatDue(row.expires_on) ?? row.expires_on}`
                                  : ''}
                              </p>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
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
          ) : readingQueue.visiblePolicyAcks.length === 0 &&
            readingQueue.activeCampaigns.length === 0 &&
            !campaigns.loading ? (
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
              ) : readingQueue.activeCampaigns.length > 0 ? (
                <div data-testid="portal-work-campaigns" className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground">Campaign assignments</span>
                    {readingQueue.activeCampaigns.length > 0 && (
                      <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                        {readingQueue.activeCampaigns.length}
                      </span>
                    )}
                  </div>
                  {readingQueue.activeCampaigns.slice(0, 3).map((item) => (
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
                          onClick={() => navigate(portalCampaignReadingHref(item.id))}
                        >
                          Continue reading
                        </Button>
                      </div>
                    </Card>
                  ))}
                  {readingQueue.activeCampaigns.length > 3 && (
                    <Button
                      variant="outline"
                      size="lg"
                      className="w-full min-h-12"
                      onClick={() => navigate('/portal/reading')}
                    >
                      View all {readingQueue.activeCampaigns.length} campaigns
                    </Button>
                  )}
                </div>
              ) : null}
              {readingQueue.visiblePolicyAcks.map((item) => (
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
                Your Atlas training compliance is listed in Training compliance above. Competency
                matrix detail remains in the full workforce passport.
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
