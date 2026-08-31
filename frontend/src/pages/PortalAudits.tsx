import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ClipboardCheck, Loader2 } from 'lucide-react'
import {
  auditsApi,
  getApiErrorMessage,
  type AuditRun,
  type AuditTemplate,
} from '../api/client'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { toast } from '../contexts/ToastContext'
import { getCurrentUserId } from '../utils/auth'
import { isPortalAuditSenior } from './portalAuditSenior'
import {
  isShowableAssignedAudit,
  isShowableCompletedAudit,
} from './portalAssignedAuditsHonesty'

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; items: AuditRun[]; total: number }
  | { status: 'error'; message: string }

type CatalogueState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; runs: AuditRun[]; templates: AuditTemplate[] }
  | { status: 'error'; message: string }

type RunProgress = 'open' | 'completed'

function formatWhen(value?: string): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString()
}

export default function PortalAudits() {
  const navigate = useNavigate()
  const { announce } = useLiveAnnouncer()
  const senior = isPortalAuditSenior()
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [catalogue, setCatalogue] = useState<CatalogueState>({ status: senior ? 'loading' : 'idle' })
  const [progress, setProgress] = useState<RunProgress>('open')
  const [auditType, setAuditType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [employee, setEmployee] = useState('')
  const [applied, setApplied] = useState({
    auditType: '',
    dateFrom: '',
    dateTo: '',
    employee: '',
  })
  const [startingId, setStartingId] = useState<number | null>(null)

  const loadAssigned = useCallback(async () => {
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

  const loadCatalogue = useCallback(async () => {
    if (!senior) {
      setCatalogue({ status: 'idle' })
      return
    }
    setCatalogue({ status: 'loading' })
    try {
      const [runsRes, templatesRes] = await Promise.all([
        auditsApi.listRuns(1, 100, {
          progress,
          audit_type: applied.auditType || undefined,
          date_from: applied.dateFrom || undefined,
          date_to: applied.dateTo || undefined,
          employee: applied.employee || undefined,
        }),
        auditsApi.listTemplates(1, 100, { is_published: true }),
      ])
      const showRun = progress === 'completed' ? isShowableCompletedAudit : isShowableAssignedAudit
      const runs = (runsRes.data.items ?? []).filter(showRun)
      const templates = (templatesRes.data.items ?? []).filter((t) => t.is_published)
      setCatalogue({ status: 'ready', runs, templates })
    } catch (err) {
      const message = getApiErrorMessage(err)
      toast.error(message)
      setCatalogue({ status: 'error', message })
    }
  }, [senior, progress, applied])

  useEffect(() => {
    announce('Assigned audits loaded')
  }, [announce])

  useEffect(() => {
    void loadAssigned()
  }, [loadAssigned])

  useEffect(() => {
    void loadCatalogue()
  }, [loadCatalogue])

  const typeOptions = useMemo(() => {
    if (catalogue.status !== 'ready') return []
    const values = new Set(catalogue.templates.map((t) => t.audit_type).filter(Boolean))
    return [...values].sort()
  }, [catalogue])

  const startTemplate = async (template: AuditTemplate) => {
    const me = getCurrentUserId()
    if (me == null) {
      toast.error('Could not start this audit because your user id is missing from the session.')
      return
    }
    setStartingId(template.id)
    try {
      const response = await auditsApi.createRun({
        template_id: template.id,
        title: template.name,
        assigned_to_id: me,
      })
      navigate(`/audits/${response.data.id}/execute`)
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setStartingId(null)
    }
  }

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

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12 space-y-10">
        <section>
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Assigned to you</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Opening an audit uses the staff audit workspace. You will leave the Employee Portal.
            </p>
          </div>

          {state.status === 'loading' ? (
            <div className="flex items-center gap-2 text-muted-foreground mt-4" data-testid="portal-audits-loading">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading assigned audits
            </div>
          ) : null}

          {state.status === 'error' ? (
            <Card className="p-4 border-amber-500/30 bg-amber-500/5 mt-4" data-testid="portal-audits-error">
              <p className="font-medium text-foreground">Couldn’t load assigned audits</p>
              <p className="text-sm text-muted-foreground mt-1">{state.message}</p>
              <Button type="button" className="mt-3 min-h-11" onClick={() => void loadAssigned()}>
                Try again
              </Button>
            </Card>
          ) : null}

          {state.status === 'ready' && state.items.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                icon={<ClipboardCheck className="w-8 h-8 text-muted-foreground" />}
                title="No audits assigned to you"
                description="When a manager assigns you an inspection, it will show here. This is not a fake zero from a failed request."
              />
            </div>
          ) : null}

          {state.status === 'ready'
            ? state.items.map((run) => {
                const when = formatWhen(run.scheduled_date)
                return (
                  <Card key={run.id} className="p-4 mt-4" data-testid={`portal-audit-row-${run.id}`}>
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
        </section>

        {senior ? (
          <section data-testid="portal-audits-catalogue">
            <h2 className="text-xl font-semibold text-foreground">Organisation catalogue</h2>
            <p className="text-muted-foreground text-sm mt-1">
              Supervisors, managers, and admins can filter previous runs and start a published
              template. Review and complete still use the staff audit workspace.
            </p>

            <div className="mt-4 flex gap-2">
              <Button
                type="button"
                variant={progress === 'open' ? 'default' : 'outline'}
                className="min-h-11 flex-1"
                data-testid="portal-catalogue-progress-open"
                aria-pressed={progress === 'open'}
                onClick={() => setProgress('open')}
              >
                In progress
              </Button>
              <Button
                type="button"
                variant={progress === 'completed' ? 'default' : 'outline'}
                className="min-h-11 flex-1"
                data-testid="portal-catalogue-progress-completed"
                aria-pressed={progress === 'completed'}
                onClick={() => setProgress('completed')}
              >
                Completed
              </Button>
            </div>

            <form
              className="mt-4 space-y-3"
              onSubmit={(e) => {
                e.preventDefault()
                setApplied({ auditType, dateFrom, dateTo, employee })
              }}
            >
              <label className="block text-sm font-medium text-foreground" htmlFor="portal-audit-type">
                Audit type
              </label>
              <select
                id="portal-audit-type"
                data-testid="portal-catalogue-type"
                className="flex h-11 w-full rounded-lg border border-input bg-background px-3 text-sm"
                value={auditType}
                onChange={(e) => setAuditType(e.target.value)}
              >
                <option value="">All types</option>
                {typeOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              <label className="block text-sm font-medium text-foreground" htmlFor="portal-audit-date-from">
                Date from
              </label>
              <Input
                id="portal-audit-date-from"
                data-testid="portal-catalogue-date-from"
                type="date"
                className="h-11"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
              <label className="block text-sm font-medium text-foreground" htmlFor="portal-audit-date-to">
                Date to
              </label>
              <Input
                id="portal-audit-date-to"
                data-testid="portal-catalogue-date-to"
                type="date"
                className="h-11"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
              <label className="block text-sm font-medium text-foreground" htmlFor="portal-audit-employee">
                Employee
              </label>
              <Input
                id="portal-audit-employee"
                data-testid="portal-catalogue-employee"
                type="search"
                className="h-11"
                placeholder="Name or email"
                value={employee}
                onChange={(e) => setEmployee(e.target.value)}
              />
              <Button type="submit" className="min-h-11 w-full" data-testid="portal-catalogue-apply">
                Apply filters
              </Button>
            </form>

            {catalogue.status === 'loading' ? (
              <div className="flex items-center gap-2 text-muted-foreground mt-4" data-testid="portal-catalogue-loading">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading catalogue
              </div>
            ) : null}

            {catalogue.status === 'error' ? (
              <Card className="p-4 border-amber-500/30 bg-amber-500/5 mt-4" data-testid="portal-catalogue-error">
                <p className="font-medium text-foreground">Couldn’t load the audit catalogue</p>
                <p className="text-sm text-muted-foreground mt-1">{catalogue.message}</p>
                <Button type="button" className="mt-3 min-h-11" onClick={() => void loadCatalogue()}>
                  Try again
                </Button>
              </Card>
            ) : null}

            {catalogue.status === 'ready' && catalogue.runs.length === 0 ? (
              <div className="mt-4">
                <EmptyState
                  icon={<ClipboardCheck className="w-8 h-8 text-muted-foreground" />}
                  title={progress === 'completed' ? 'No completed audits' : 'No in-progress audits'}
                  description="Nothing matches these filters. This is not a fake zero from a failed request."
                />
              </div>
            ) : null}

            {catalogue.status === 'ready'
              ? catalogue.runs.map((run) => {
                  const when = formatWhen(run.scheduled_date || run.completed_at || run.created_at)
                  const review = progress === 'completed'
                  return (
                    <Card key={run.id} className="p-4 mt-4" data-testid={`portal-catalogue-run-${run.id}`}>
                      <p className="text-xs text-muted-foreground">{run.reference_number}</p>
                      <h3 className="font-semibold text-foreground mt-1">
                        {run.title || run.reference_number}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {[run.location, when, run.status].filter(Boolean).join(' · ')}
                      </p>
                      <Button
                        type="button"
                        className="mt-4 min-h-11 w-full"
                        data-testid={`portal-catalogue-open-${run.id}`}
                        onClick={() => navigate(`/audits/${run.id}/execute`)}
                      >
                        {review ? 'Review output' : 'Open in audit workspace'}
                      </Button>
                    </Card>
                  )
                })
              : null}

            {catalogue.status === 'ready' ? (
              <div className="mt-10" data-testid="portal-audits-published">
                <h2 className="text-xl font-semibold text-foreground">Published audits</h2>
                <p className="text-muted-foreground text-sm mt-1">
                  Start a published template. The run is assigned to you. Completing it uses the
                  staff workspace.
                </p>
                {catalogue.templates.length === 0 ? (
                  <div className="mt-4">
                    <EmptyState
                      icon={<ClipboardCheck className="w-8 h-8 text-muted-foreground" />}
                      title="No published audits"
                      description="Nothing is published in this organisation yet. This is not a fake zero from a failed request."
                    />
                  </div>
                ) : (
                  catalogue.templates.map((template) => (
                    <Card
                      key={template.id}
                      className="p-4 mt-4"
                      data-testid={`portal-catalogue-template-${template.id}`}
                    >
                      <p className="text-xs text-muted-foreground">{template.audit_type}</p>
                      <h3 className="font-semibold text-foreground mt-1">{template.name}</h3>
                      {template.description ? (
                        <p className="text-sm text-muted-foreground mt-1">{template.description}</p>
                      ) : null}
                      <Button
                        type="button"
                        className="mt-4 min-h-11 w-full"
                        data-testid={`portal-catalogue-start-${template.id}`}
                        disabled={startingId === template.id}
                        onClick={() => void startTemplate(template)}
                      >
                        {startingId === template.id ? 'Starting…' : 'Start audit'}
                      </Button>
                    </Card>
                  ))
                )}
              </div>
            ) : null}
          </section>
        ) : null}
      </main>
    </div>
  )
}
