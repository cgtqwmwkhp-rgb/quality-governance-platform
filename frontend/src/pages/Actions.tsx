import { useEffect, useState, useCallback, useDeferredValue, useMemo, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Search,
  ListTodo,
  Plus,
  Calendar,
  User,
  Flag,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowUpRight,
  Filter,
  Loader2,
  ChevronDown,
  ChevronUp,
  Info,
  ArrowRight,
  MailWarning,
  MoreHorizontal,
} from 'lucide-react'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { EmptyState } from '../components/ui/EmptyState'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/DropdownMenu'
import { cn } from '../helpers/utils'
import {
  actionsApi,
  Action as ApiAction,
  ActionCreate,
  ActionsSummary,
  ActionsViewCounts,
  notificationsApi,
} from '../api/client'
import { decodeTokenPayload, getPlatformToken } from '../utils/auth'
import { toast } from '../contexts/ToastContext'
import {
  actionsViewRequiresIdentity,
  actionsViewUsesServerFilter,
  buildActionsListScope,
  parseActionsViewParam,
  type ActionsViewMode,
} from './actionsViewScope'
import { getActionSourceLink } from '../components/investigations/handoffLinks'
import { buildActionDetailPath } from './actionLinks'

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

/** Human-readable due date vs today (calendar days). */
function formatDueRelative(dueDate: string): string {
  const due = new Date(dueDate)
  if (Number.isNaN(due.getTime())) return ''
  const diff = Math.round((startOfDay(due) - startOfDay(new Date())) / 86400000)
  if (diff < 0) return `${Math.abs(diff)}d overdue`
  if (diff === 0) return 'Due today'
  if (diff === 1) return 'Due tomorrow'
  return `Due in ${diff}d`
}

// Bounded error taxonomy for deterministic error handling
type ErrorClass =
  | 'VALIDATION_ERROR'
  | 'AUTH_ERROR'
  | 'NOT_FOUND'
  | 'NETWORK_ERROR'
  | 'SERVER_ERROR'
  | 'UNKNOWN'

interface ApiError {
  error_class: ErrorClass
  message: string
}

function classifyError(error: unknown): ApiError {
  if (error instanceof Error) {
    const message = error.message.toLowerCase()
    if (message.includes('401') || message.includes('unauthorized')) {
      return { error_class: 'AUTH_ERROR', message: 'Authentication required. Please log in.' }
    }
    if (message.includes('404') || message.includes('not found')) {
      return { error_class: 'NOT_FOUND', message: 'Action not found.' }
    }
    if (message.includes('400') || message.includes('validation')) {
      return { error_class: 'VALIDATION_ERROR', message: 'Invalid data provided.' }
    }
    if (message.includes('network') || message.includes('fetch')) {
      return {
        error_class: 'NETWORK_ERROR',
        message: 'Network error. Please check your connection.',
      }
    }
    if (message.includes('500') || message.includes('server')) {
      return { error_class: 'SERVER_ERROR', message: 'Server error. Please try again later.' }
    }
  }
  return { error_class: 'UNKNOWN', message: 'An unexpected error occurred.' }
}

// Local UI type extending API type with computed fields
interface Action extends Omit<ApiAction, 'owner_email'> {
  source_ref: string
  assignee?: string
}

function isTerminalActionStatus(status: string | undefined): boolean {
  return ['completed', 'closed', 'verified'].includes(String(status || '').toLowerCase())
}

function getComplaintSourceLink(sourceType: string, sourceId: number) {
  if (!Number.isFinite(sourceId) || sourceId <= 0) return null
  const kind = sourceType.toLowerCase()
  if (kind === 'complaint' || kind === 'capa_complaint') {
    return {
      href: `/complaints/${sourceId}`,
      labelKey: 'actions.view_complaint',
      labelFallback: 'View complaint',
    }
  }
  return null
}

type ViewMode = ActionsViewMode
type FilterStatus = 'all' | 'open' | 'in_progress' | 'pending_verification' | 'completed'
type SourceTypeFilter =
  | 'all'
  | 'audit_finding'
  | 'incident'
  | 'complaint'
  | 'investigation'
  | 'rta'
  | 'ncr'
  | 'capa_incident'
  | 'capa_complaint'
  | 'regulatory_watch'
type SortMode = 'newest' | 'due_first'

// Form state type for creating actions
interface CreateActionForm {
  title: string
  description: string
  priority: string
  action_type: string
  due_date: string
  source_type: string
  source_id: string
}

const INITIAL_FORM: CreateActionForm = {
  title: '',
  description: '',
  priority: 'medium',
  action_type: 'corrective',
  due_date: '',
  source_type: 'incident',
  source_id: '',
}

function isSafeActionsReturnTo(path: string | null | undefined): path is string {
  if (!path) return false
  if (!path.startsWith('/')) return false
  if (path.startsWith('//')) return false
  if (path.includes('://')) return false
  return true
}

const FILTER_STATUS_VALUES: FilterStatus[] = [
  'all',
  'open',
  'in_progress',
  'pending_verification',
  'completed',
]

function parseActionsStatusParam(raw: string | null | undefined): FilterStatus {
  if (raw && FILTER_STATUS_VALUES.includes(raw as FilterStatus)) {
    return raw as FilterStatus
  }
  return 'all'
}

type HeroKey = 'total' | 'open' | 'in_progress' | 'overdue' | 'completed'

function heroKeyFromFilters(viewMode: ViewMode, filterStatus: FilterStatus): HeroKey {
  if (viewMode === 'overdue' || viewMode === 'my_overdue') return 'overdue'
  if (filterStatus === 'open') return 'open'
  if (filterStatus === 'in_progress') return 'in_progress'
  if (filterStatus === 'completed') return 'completed'
  return 'total'
}

export default function Actions() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [actions, setActions] = useState<Action[]>([])
  const [loading, setLoading] = useState(true)
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(() =>
    parseActionsViewParam(searchParams.get('view')),
  )
  const [filterStatus, setFilterStatus] = useState<FilterStatus>(() =>
    parseActionsStatusParam(searchParams.get('status')),
  )
  const [heroKey, setHeroKey] = useState<HeroKey>(() => {
    const initialView = parseActionsViewParam(searchParams.get('view'))
    const initialStatus = parseActionsStatusParam(searchParams.get('status'))
    return heroKeyFromFilters(initialView, initialStatus)
  })
  const [sourceTypeFilter, setSourceTypeFilter] = useState<SourceTypeFilter>(() => {
    const raw = searchParams.get('sourceType')
    return raw ? (raw as SourceTypeFilter) : 'all'
  })
  const sourceIdFilter = Number(searchParams.get('sourceId') || '')
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [sortMode, setSortMode] = useState<SortMode>('newest')
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [summary, setSummary] = useState<ActionsSummary | null>(null)
  const [summaryUnavailable, setSummaryUnavailable] = useState(false)
  const [viewCounts, setViewCounts] = useState<ActionsViewCounts | null>(null)
  const [viewCountsUnavailable, setViewCountsUnavailable] = useState(false)
  const [emailConfigured, setEmailConfigured] = useState<boolean | null>(null)
  const [serverFilterError, setServerFilterError] = useState<string | null>(null)
  const createReturnTo = useMemo(() => {
    const raw = searchParams.get('returnTo')
    return isSafeActionsReturnTo(raw) ? raw : null
  }, [searchParams])

  const currentUserId = useMemo(() => {
    const token = getPlatformToken()
    if (!token) return null
    const payload = decodeTokenPayload(token)
    const sub = payload?.sub
    if (sub === undefined || sub === null) return null
    const id = parseInt(String(sub), 10)
    return Number.isFinite(id) ? id : null
  }, [])

  // Form state
  const [formData, setFormData] = useState<CreateActionForm>(INITIAL_FORM)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<ApiError | null>(null)
  const [submitSuccess, setSubmitSuccess] = useState(false)
  const createTriggerRef = useRef<HTMLButtonElement>(null)

  // Hydrate shareable filters from URL (back/forward + deep links).
  useEffect(() => {
    const nextView = parseActionsViewParam(searchParams.get('view'))
    const nextStatus = parseActionsStatusParam(searchParams.get('status'))
    const rawSourceType = searchParams.get('sourceType')
    const nextSourceType: SourceTypeFilter = rawSourceType
      ? (rawSourceType as SourceTypeFilter)
      : 'all'
    setViewMode((prev) => (prev === nextView ? prev : nextView))
    setFilterStatus((prev) => (prev === nextStatus ? prev : nextStatus))
    setSourceTypeFilter((prev) => (prev === nextSourceType ? prev : nextSourceType))
    const nextHero = heroKeyFromFilters(nextView, nextStatus)
    setHeroKey((prev) => (prev === nextHero ? prev : nextHero))
  }, [searchParams])

  useEffect(() => {
    if (!showModal || submitSuccess) return
    const id = window.requestAnimationFrame(() => {
      document.getElementById('actions-field-0')?.focus()
    })
    return () => window.cancelAnimationFrame(id)
  }, [showModal, submitSuccess])

  // Running Sheet / case bridge: ?create=1 opens modal with prefills + optional returnTo.
  useEffect(() => {
    if (searchParams.get('create') !== '1') return
    const title = searchParams.get('title') || ''
    const description = searchParams.get('description') || ''
    const sourceType = searchParams.get('sourceType') || 'incident'
    const sourceId = searchParams.get('sourceId') || ''
    setFormData({
      ...INITIAL_FORM,
      title: title.slice(0, 300),
      description,
      source_type: sourceType,
      source_id: sourceId,
    })
    setShowModal(true)
    const next = new URLSearchParams(searchParams)
    next.delete('create')
    next.delete('title')
    next.delete('description')
    // Keep sourceType/sourceId/returnTo for filter + return banner.
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  // Transform API response to UI model
  const transformAction = (apiAction: ApiAction): Action => ({
    ...apiAction,
    source_ref:
      apiAction.source_reference ||
      apiAction.source_title ||
      `${apiAction.source_type.toUpperCase()}-${apiAction.source_id}`,
    assignee: apiAction.assigned_to_email || apiAction.owner_email || undefined,
  })

  // Fetch actions from API with stable ordering (server returns created_at desc).
  // My Work / Overdue / My overdue are server-scoped via assigned_to + overdue.
  const loadActions = useCallback(async () => {
    setLoading(true)
    setError(null)
    setServerFilterError(null)

    if (actionsViewRequiresIdentity(viewMode) && currentUserId == null) {
      const msg = t(
        'actions.filter.identity_required',
        'Cannot load My actions — signed-in user id is unavailable.',
      )
      setServerFilterError(msg)
      toast.error(msg)
      setActions([])
      setLoading(false)
      setHasLoadedOnce(true)
      return
    }

    try {
      const response = await actionsApi.list(
        1,
        100,
        undefined,
        sourceTypeFilter !== 'all' ? sourceTypeFilter : undefined,
        sourceTypeFilter !== 'all' && Number.isFinite(sourceIdFilter) && sourceIdFilter > 0
          ? sourceIdFilter
          : undefined,
        buildActionsListScope(viewMode),
      )
      const transformedActions = (response.data.items ?? []).map(transformAction)
      setActions(transformedActions)
    } catch (err) {
      console.error('Failed to load actions:', err)
      const classified = classifyError(err)
      setActions([])
      if (actionsViewUsesServerFilter(viewMode)) {
        const msg = t(
          'actions.filter.server_failed',
          'Server filter failed — results were not loaded. Try again or switch to All.',
        )
        setServerFilterError(msg)
        toast.error(msg)
        // Keep page chrome (view-mode toggles + alert) — do not collapse to a silent empty state.
        setError(null)
      } else {
        setError(classified)
      }
    } finally {
      setLoading(false)
      setHasLoadedOnce(true)
    }
  }, [currentUserId, sourceIdFilter, sourceTypeFilter, viewMode, t])

  const loadSummary = useCallback(async () => {
    try {
      const res = await actionsApi.summary()
      setSummary(res.data)
      setSummaryUnavailable(false)
    } catch {
      setSummary(null)
      setSummaryUnavailable(true)
      toast.error(
        t(
          'actions.summary_unavailable',
          'Action metrics unavailable — counts are not shown as zero.',
        ),
      )
    }
  }, [t])

  const loadViewCounts = useCallback(async () => {
    try {
      const res = await actionsApi.viewCounts()
      setViewCounts(res.data)
      setViewCountsUnavailable(false)
    } catch {
      setViewCounts(null)
      setViewCountsUnavailable(true)
    }
  }, [])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (sourceTypeFilter === 'all') next.delete('sourceType')
    else next.set('sourceType', sourceTypeFilter)
    if (sourceTypeFilter === 'all' || !Number.isFinite(sourceIdFilter) || sourceIdFilter <= 0) {
      next.delete('sourceId')
    }
    if (viewMode === 'all') next.delete('view')
    else next.set('view', viewMode)
    if (filterStatus === 'all') next.delete('status')
    else next.set('status', filterStatus)
    const nextQuery = next.toString()
    if (nextQuery !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams, sourceIdFilter, sourceTypeFilter, viewMode, filterStatus])

  useEffect(() => {
    loadActions()
    loadSummary()
    loadViewCounts()
  }, [loadActions, loadSummary, loadViewCounts])

  useEffect(() => {
    let cancelled = false
    notificationsApi
      .getDeliveryStatus()
      .then((response) => {
        if (!cancelled) setEmailConfigured(response.data.email_configured)
      })
      .catch(() => {
        // Optional honesty signal: omit the banner when readiness cannot be read.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)
    setIsSubmitting(true)

    try {
      const payload: ActionCreate = {
        title: formData.title,
        description: formData.description,
        action_type: formData.action_type,
        priority: formData.priority,
        source_type: formData.source_type,
        source_id: parseInt(formData.source_id, 10),
        due_date: formData.due_date || undefined,
      }

      const response = await actionsApi.create(payload)
      if (response.data) {
        setActions((prev) => [transformAction(response.data), ...prev])
      }
      setSubmitSuccess(true)

      // STATIC_UI_CONFIG_OK - UX delay to show success state before closing modal
      setTimeout(() => {
        setShowModal(false)
        setFormData(INITIAL_FORM)
        setSubmitSuccess(false)
        if (createReturnTo) {
          navigate(createReturnTo)
        } else if (response.data?.action_key) {
          navigate(buildActionDetailPath(response.data.action_key))
        }
      }, 1500)
    } catch (err) {
      console.error('Failed to create action:', err)
      setSubmitError(classifyError(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  const getPriorityVariant = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'critical'
      case 'high':
        return 'high'
      case 'medium':
        return 'medium'
      case 'low':
        return 'low'
      default:
        return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'resolved'
      case 'open':
        return 'submitted'
      case 'in_progress':
        return 'in-progress'
      case 'pending_verification':
        return 'acknowledged'
      case 'cancelled':
        return 'closed'
      default:
        return 'secondary'
    }
  }

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'incident':
        return '🔥'
      case 'audit_finding':
        return '📋'
      case 'audit':
        return '📋'
      case 'rta':
        return '🚗'
      case 'complaint':
        return '💬'
      case 'risk':
        return '⚠️'
      default:
        return '📌'
    }
  }

  const isOverdue = (dueDate?: string, displayStatus?: string) => {
    if (
      !dueDate ||
      displayStatus === 'completed' ||
      displayStatus === 'cancelled' ||
      displayStatus === 'verified'
    )
      return false
    return new Date(dueDate) < new Date()
  }

  const deferredSearch = useDeferredValue(searchTerm)
  // Search + status remain client-side; My/Overdue are applied server-side in loadActions.
  const filteredActions = actions.filter((action) => {
    if (
      deferredSearch &&
      !action.title.toLowerCase().includes(deferredSearch.toLowerCase()) &&
      !action.reference_number?.toLowerCase().includes(deferredSearch.toLowerCase()) &&
      !action.source_ref.toLowerCase().includes(deferredSearch.toLowerCase()) &&
      !(action.source_scheme || '').toLowerCase().includes(deferredSearch.toLowerCase())
    ) {
      return false
    }
    if (filterStatus !== 'all' && action.display_status !== filterStatus) {
      return false
    }
    return true
  })

  const sortedActions = useMemo(() => {
    const arr = [...filteredActions]
    if (sortMode === 'due_first') {
      const rank = (a: Action) => {
        if (!a.due_date || a.display_status === 'completed' || a.display_status === 'cancelled') {
          return Number.POSITIVE_INFINITY
        }
        const t = new Date(a.due_date).getTime()
        if (Number.isNaN(t)) return Number.POSITIVE_INFINITY
        if (t < Date.now()) {
          return t - 1e15
        }
        return t
      }
      arr.sort((a, b) => rank(a) - rank(b))
    }
    return arr
  }, [filteredActions, sortMode])

  const byD = summary?.by_display_status ?? {}
  const statsReady = summary != null && !summaryUnavailable
  const stats = {
    total: statsReady ? (summary?.total ?? 0) : null,
    open: statsReady ? (byD.open ?? 0) : null,
    inProgress: statsReady ? (byD.in_progress ?? 0) : null,
    overdue: statsReady ? (byD.overdue ?? 0) : null,
    completed: statsReady ? (byD.completed ?? 0) : null,
  }

  const badgeFor = (mode: ViewMode): string | null => {
    if (viewCountsUnavailable) return '—'
    if (!viewCounts) return null
    const n =
      mode === 'all'
        ? viewCounts.all
        : mode === 'my'
          ? viewCounts.my
          : mode === 'overdue'
            ? viewCounts.overdue
            : viewCounts.my_overdue
    return String(n)
  }

  const applyHeroFilter = (key: HeroKey) => {
    setHeroKey(key)
    if (key === 'total') {
      setFilterStatus('all')
      setViewMode('all')
      return
    }
    if (key === 'overdue') {
      setFilterStatus('all')
      setViewMode('overdue')
      return
    }
    setViewMode('all')
    setFilterStatus(key)
  }

  // First paint only — keep view-mode chrome mounted on subsequent filter reloads
  // so Mine/Overdue toggles remain clickable (and unit/e2e tests do not race a full-page skeleton).
  if (loading && !hasLoadedOnce) {
    return <TableSkeleton rows={8} columns={5} />
  }

  if (error && !actionsViewUsesServerFilter(viewMode)) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-destructive" />
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-foreground">{error.error_class}</p>
          <p className="text-muted-foreground">{error.message}</p>
        </div>
        <Button onClick={loadActions} variant="outline">
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            {t('actions.title')}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">{t('actions.subtitle')}</p>
        </div>
        <Button ref={createTriggerRef} onClick={() => setShowModal(true)} size="sm">
          <Plus size={16} />
          {t('actions.new')}
        </Button>
      </div>

      {createReturnTo ? (
        <div
          className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
          data-testid="actions-return-to-case"
        >
          <p className="text-sm text-foreground">
            Creating from a case Running Sheet — after save you return to the case.
          </p>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link to={createReturnTo}>Back to case</Link>
          </Button>
        </div>
      ) : null}

      {emailConfigured === false ? (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid="actions-email-unavailable"
        >
          <div className="flex items-start gap-3">
            <MailWarning className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">{t('actions.email_unavailable.title')}</p>
              <p className="mt-1 text-sm">{t('actions.email_unavailable.body')}</p>
            </div>
          </div>
        </div>
      ) : null}

      {/* Stats */}
      {summaryUnavailable ? (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid="actions-summary-unavailable"
        >
          <p className="font-semibold">
            {t('actions.summary_unavailable_title', 'Metrics unavailable')}
          </p>
          <p className="mt-1 text-sm">
            {t(
              'actions.summary_unavailable_body',
              'Action totals could not be loaded. Counts are not shown as zero.',
            )}
          </p>
        </div>
      ) : (
        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2"
          role="group"
          aria-label={t('actions.hero_filters', 'Filter by status')}
          data-testid="actions-hero-board"
        >
          {(
            [
              {
                key: 'total' as const,
                label: t('actions.total'),
                value: stats.total,
                icon: ListTodo,
                tone: 'primary' as const,
              },
              {
                key: 'open' as const,
                label: t('status.open'),
                value: stats.open,
                icon: AlertCircle,
                tone: 'info' as const,
              },
              {
                key: 'in_progress' as const,
                label: t('status.in_progress'),
                value: stats.inProgress,
                icon: Clock,
                tone: 'warning' as const,
              },
              {
                key: 'overdue' as const,
                label: t('common.overdue'),
                value: stats.overdue,
                icon: Flag,
                tone: 'destructive' as const,
              },
              {
                key: 'completed' as const,
                label: t('actions.completed'),
                value: stats.completed,
                icon: CheckCircle2,
                tone: 'success' as const,
              },
            ] as const
          ).map((stat) => {
            const active = heroKey === stat.key
            return (
              <button
                key={stat.key}
                type="button"
                data-testid={`actions-hero-${stat.key}`}
                aria-pressed={active}
                onClick={() => applyHeroFilter(stat.key)}
                className={cn(
                  'rounded-xl border px-3 py-2.5 text-left transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  active
                    ? 'border-primary/40 bg-primary/5 shadow-sm'
                    : 'border-border bg-card hover:bg-surface',
                  stat.key === 'overdue' &&
                    stats.overdue != null &&
                    stats.overdue > 0 &&
                    !active &&
                    'border-destructive/25',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={cn(
                      'inline-flex h-7 w-7 items-center justify-center rounded-lg',
                      stat.tone === 'primary' && 'bg-primary/10 text-primary',
                      stat.tone === 'info' && 'bg-info/10 text-info',
                      stat.tone === 'warning' && 'bg-warning/10 text-warning',
                      stat.tone === 'destructive' && 'bg-destructive/10 text-destructive',
                      stat.tone === 'success' && 'bg-success/10 text-success',
                    )}
                  >
                    <stat.icon className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                  <span className="text-xl font-semibold tabular-nums text-foreground">
                    {stat.value ?? '—'}
                  </span>
                </div>
                <p className="mt-1.5 text-xs font-medium text-muted-foreground">{stat.label}</p>
              </button>
            )
          })}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('actions.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        <div className="flex flex-wrap bg-surface rounded-xl p-1 border border-border" data-testid="actions-view-mode">
          {(['all', 'my', 'overdue', 'my_overdue'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              data-testid={`actions-view-${mode}`}
              aria-pressed={viewMode === mode}
              onClick={() => {
                setViewMode(mode)
                if (mode === 'overdue' || mode === 'my_overdue') {
                  setHeroKey('overdue')
                  setFilterStatus('all')
                } else if (mode === 'all') {
                  setHeroKey('total')
                }
              }}
              disabled={loading}
              className={cn(
                'px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 inline-flex items-center gap-2',
                viewMode === mode
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
                loading && 'opacity-70',
              )}
            >
              <span>
                {mode === 'all'
                  ? t('actions.view_mode.all')
                  : mode === 'my'
                    ? t('actions.view_mode.my')
                    : mode === 'overdue'
                      ? t('actions.view_mode.overdue')
                      : t('actions.view_mode.my_overdue', 'My overdue')}
              </span>
              {badgeFor(mode) != null ? (
                <span
                  className={cn(
                    'min-w-[1.25rem] rounded-full px-1.5 text-xs font-semibold tabular-nums',
                    viewMode === mode
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : 'bg-muted text-foreground',
                  )}
                  data-testid={`actions-view-badge-${mode}`}
                >
                  {badgeFor(mode)}
                </span>
              ) : null}
            </button>
          ))}
        </div>

        <Select
          value={filterStatus}
          onValueChange={(value) => {
            const next = value as FilterStatus
            setFilterStatus(next)
            if (next === 'all') {
              setHeroKey(viewMode === 'overdue' || viewMode === 'my_overdue' ? 'overdue' : 'total')
            } else if (next === 'open' || next === 'in_progress' || next === 'completed') {
              setHeroKey(next)
            }
          }}
        >
          <SelectTrigger className="w-[180px]">
            <Filter className="w-4 h-4 mr-2" />
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="pending_verification">Pending Verification</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={sourceTypeFilter}
          onValueChange={(value) => setSourceTypeFilter(value as SourceTypeFilter)}
        >
          <SelectTrigger className="w-[220px]">
            <Filter className="w-4 h-4 mr-2" />
            <SelectValue placeholder="All Sources" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Sources</SelectItem>
            <SelectItem value="audit_finding">Audit Findings</SelectItem>
            <SelectItem value="incident">Incidents</SelectItem>
            <SelectItem value="complaint">Complaints</SelectItem>
            <SelectItem value="investigation">Investigations</SelectItem>
            <SelectItem value="rta">RTAs</SelectItem>
            <SelectItem value="ncr">NCR / defects (CAPA)</SelectItem>
            <SelectItem value="capa_incident">CAPA (incident-linked)</SelectItem>
            <SelectItem value="capa_complaint">CAPA (complaint-linked)</SelectItem>
            <SelectItem value="regulatory_watch">Regulatory watch</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortMode} onValueChange={(value) => setSortMode(value as SortMode)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder={t('actions.sort_newest')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="newest">{t('actions.sort_newest')}</SelectItem>
            <SelectItem value="due_first">{t('actions.sort_due')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {actionsViewUsesServerFilter(viewMode) ? (
        <div
          className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
          data-testid="actions-server-filter-label"
          role="status"
        >
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            {viewMode === 'my'
              ? t(
                  'actions.filter.server_my',
                  'Showing actions assigned to you (server filter: assigned_to=me).',
                )
              : viewMode === 'overdue'
                ? t(
                    'actions.filter.server_overdue',
                    'Showing overdue open actions (server filter: overdue=true).',
                  )
                : t(
                    'actions.filter.server_my_overdue',
                    'Showing your overdue open actions (server filter: assigned_to=me&overdue=true).',
                  )}
          </span>
        </div>
      ) : null}

      {serverFilterError ? (
        <div
          className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          data-testid="actions-filter-error"
          role="alert"
        >
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{serverFilterError}</span>
        </div>
      ) : null}

      {loading && hasLoadedOnce ? (
        <div
          className="flex items-center gap-2 text-sm text-muted-foreground"
          data-testid="actions-filter-loading"
          role="status"
        >
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>{t('actions.filter.loading', 'Updating filtered actions…')}</span>
        </div>
      ) : null}

      {sourceTypeFilter === 'audit_finding' ? (
        <Card className="border-info/30 bg-info/5">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-start gap-3">
            <div className="p-2 rounded-lg bg-info/15 text-info shrink-0">
              <Info className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-semibold text-foreground">{t('actions.audit_playbook.title')}</p>
              <p className="text-sm text-muted-foreground">{t('actions.audit_playbook.body')}</p>
              <div>
                <Button variant="outline" size="sm" asChild>
                  <Link to="/risk-register?triage=import">
                    {t('actions.audit_playbook.risk_triage')}
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {sourceTypeFilter === 'incident' &&
      Number.isFinite(sourceIdFilter) &&
      sourceIdFilter > 0 ? (
        <Card className="border-warning/30 bg-warning/5" data-testid="actions-incident-playbook">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-start gap-3">
            <div className="p-2 rounded-lg bg-warning/15 text-warning shrink-0">
              <Info className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-semibold text-foreground">
                {t('actions.incident_playbook.title', 'Incident-sourced corrective actions')}
              </p>
              <p className="text-sm text-muted-foreground">
                {t(
                  'actions.incident_playbook.body',
                  'CAPA items here close the loop on the originating incident. Continue the linked investigation before marking the incident resolved.',
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/incidents/${sourceIdFilter}`}>
                    {t('actions.incident_playbook.open_incident', 'Open incident record')}
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {sourceTypeFilter === 'investigation' &&
      Number.isFinite(sourceIdFilter) &&
      sourceIdFilter > 0 ? (
        <Card className="border-primary/30 bg-primary/5" data-testid="actions-investigation-playbook">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-start gap-3">
            <div className="p-2 rounded-lg bg-primary/15 text-primary shrink-0">
              <Info className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-semibold text-foreground">
                {t(
                  'actions.investigation_playbook.title',
                  'Investigation-sourced corrective actions',
                )}
              </p>
              <p className="text-sm text-muted-foreground">
                {t(
                  'actions.investigation_playbook.body',
                  'Actions here turn investigation findings into tracked CAPA work. Return to the investigation for root-cause context.',
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/investigations/${sourceIdFilter}`}>
                    {t('actions.investigation_playbook.open_investigation', 'Open investigation')}
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {sourceTypeFilter === 'complaint' &&
      Number.isFinite(sourceIdFilter) &&
      sourceIdFilter > 0 ? (
        <Card className="border-info/30 bg-info/5" data-testid="actions-complaint-playbook">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-start gap-3">
            <div className="p-2 rounded-lg bg-info/15 text-info shrink-0">
              <Info className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-semibold text-foreground">
                {t('actions.complaint_playbook.title', 'Complaint-sourced corrective actions')}
              </p>
              <p className="text-sm text-muted-foreground">
                {t(
                  'actions.complaint_playbook.body',
                  'CAPA items here track complaint resolution. Return to the complaint record for intake context and running-sheet history.',
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/complaints/${sourceIdFilter}`}>
                    {t('actions.complaint_playbook.open_complaint', 'Open complaint record')}
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Actions List — dense single-column rows */}
      <div>
        {sortedActions.length === 0 ? (
          <EmptyState
            icon={<ListTodo className="w-8 h-8 text-muted-foreground" />}
            title={t('actions.empty.title')}
            description={
              filterStatus !== 'all' || viewMode !== 'all'
                ? t('actions.empty.filter_hint')
                : t('actions.empty.subtitle')
            }
          />
        ) : (
          <div
            className="overflow-hidden rounded-xl border border-border bg-card divide-y divide-border"
            data-testid="actions-list"
          >
            {sortedActions.map((action) => {
              const overdue = isOverdue(action.due_date, action.display_status)
              const isOpen = expandedKey === action.action_key
              const sourceLink =
                getActionSourceLink(action.source_type, action.source_id) ||
                getComplaintSourceLink(action.source_type, action.source_id)
              const hasAuditLinks =
                action.source_type === 'audit_finding' &&
                action.audit_run_id != null &&
                action.audit_run_id > 0
              const moreCount = hasAuditLinks ? 2 : 0
              const detailPanelId = `actions-detail-${action.action_key}`
              const assigneeLabel =
                action.assignee || t('actions.list.unassigned', 'Unassigned')
              const showFindingLoopCta =
                action.source_type === 'audit_finding' &&
                Number.isFinite(action.source_id) &&
                action.source_id > 0 &&
                isTerminalActionStatus(action.display_status || action.status)

              return (
                <div
                  key={action.action_key}
                  className={cn(
                    'group',
                    overdue && 'bg-destructive/[0.02]',
                    isOpen && 'bg-surface/60',
                  )}
                  data-testid={`actions-row-${action.action_key}`}
                >
                  <div className="flex items-center gap-3 px-3 py-2.5">
                    <span
                      className={cn(
                        'h-8 w-1 shrink-0 rounded-full',
                        action.priority === 'critical' && 'bg-destructive',
                        action.priority === 'high' && 'bg-warning',
                        action.priority === 'medium' && 'bg-warning/70',
                        action.priority === 'low' && 'bg-success',
                        !['critical', 'high', 'medium', 'low'].includes(action.priority) &&
                          'bg-muted',
                      )}
                      aria-hidden="true"
                    />

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 min-w-0">
                        <h3 className="truncate text-sm font-medium text-foreground">
                          {action.title}
                        </h3>
                        {overdue ? (
                          <Badge variant="destructive" className="shrink-0 text-[10px] px-1.5 py-0">
                            OVERDUE
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                        <span className="font-mono text-primary/90">
                          {action.reference_number || `ACT-${action.id}`}
                        </span>
                        <span aria-hidden="true">·</span>
                        <Badge
                          variant={getStatusVariant(action.display_status) as any}
                          className="text-[10px] px-1.5 py-0 font-normal"
                        >
                          {action.display_status.replace('_', ' ')}
                        </Badge>
                        <Badge
                          variant={getPriorityVariant(action.priority) as any}
                          className="text-[10px] px-1.5 py-0 font-normal"
                        >
                          {action.priority}
                        </Badge>
                        {action.source_ref ? (
                          <>
                            <span aria-hidden="true">·</span>
                            <span className="inline-flex items-center gap-1 truncate">
                              <span aria-hidden="true">{getSourceIcon(action.source_type)}</span>
                              <span className="font-mono truncate">{action.source_ref}</span>
                            </span>
                          </>
                        ) : null}
                        <span aria-hidden="true">·</span>
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 truncate',
                            !action.assignee && 'italic opacity-80',
                          )}
                          data-testid={`actions-row-assignee-${action.action_key}`}
                        >
                          <User className="h-3 w-3 shrink-0" aria-hidden="true" />
                          {assigneeLabel}
                        </span>
                        {action.source_scheme ? (
                          <>
                            <span aria-hidden="true">·</span>
                            <span className="truncate">{action.source_scheme}</span>
                          </>
                        ) : null}
                      </div>
                    </div>

                    {action.due_date ? (
                      <div
                        className={cn(
                          'hidden sm:flex w-[7.5rem] shrink-0 flex-col items-end text-right text-xs',
                          overdue ? 'text-destructive' : 'text-muted-foreground',
                        )}
                      >
                        <span className="inline-flex items-center gap-1 font-medium">
                          <Calendar className="h-3 w-3" aria-hidden="true" />
                          {new Date(action.due_date).toLocaleDateString()}
                        </span>
                        <span className="opacity-90">{formatDueRelative(action.due_date)}</span>
                      </div>
                    ) : (
                      <div className="hidden sm:block w-[7.5rem] shrink-0" />
                    )}

                    <div className="flex shrink-0 items-center gap-1.5">
                      {sourceLink ? (
                        <Button variant="ghost" size="sm" className="h-8 px-2 text-xs" asChild>
                          <Link
                            to={sourceLink.href}
                            data-testid={`actions-source-link-${action.action_key}`}
                          >
                            {t(sourceLink.labelKey, sourceLink.labelFallback)}
                            <ArrowUpRight className="ml-1 h-3 w-3" aria-hidden="true" />
                          </Link>
                        </Button>
                      ) : null}

                      {moreCount > 0 ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 px-0"
                              aria-label={t('actions.more_links', 'More links')}
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="min-w-[12rem]">
                            <DropdownMenuItem asChild className="pl-2">
                              <Link to={`/audits/${action.audit_run_id}/execute`}>
                                {t('actions.open_audit_run')}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild className="pl-2">
                              <Link to={`/audits/${action.audit_run_id}/import-review`}>
                                {t('actions.open_import_review')}
                              </Link>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : null}

                      <Button size="sm" className="h-8 px-3 text-xs font-medium" asChild>
                        <Link to={buildActionDetailPath(action.action_key)}>
                          {t('actions.open_profile')}
                        </Link>
                      </Button>

                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 px-0"
                        aria-expanded={isOpen}
                        aria-controls={detailPanelId}
                        aria-label={
                          isOpen ? t('actions.collapse_details') : t('actions.expand_details')
                        }
                        onClick={() => setExpandedKey(isOpen ? null : action.action_key)}
                      >
                        {isOpen ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  {isOpen ? (
                    <div
                      id={detailPanelId}
                      role="region"
                      aria-label={t('actions.detail.panel', 'Action details')}
                      data-testid={`actions-detail-${action.action_key}`}
                      className="border-t border-border bg-surface/40 px-3 py-3 pl-7 space-y-3 text-sm"
                    >
                      {action.due_date ? (
                        <p
                          className={cn(
                            'sm:hidden text-xs',
                            overdue ? 'text-destructive' : 'text-muted-foreground',
                          )}
                        >
                          Due {new Date(action.due_date).toLocaleDateString()} ·{' '}
                          {formatDueRelative(action.due_date)}
                        </p>
                      ) : null}
                      {action.completion_notes ? (
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                            {t('actions.detail.verification')}
                          </p>
                          <p className="mt-1 whitespace-pre-wrap text-foreground">
                            {action.completion_notes}
                          </p>
                        </div>
                      ) : null}
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span>
                          {t('actions.detail.type', 'Type')}:{' '}
                          <span className="font-medium text-foreground">{action.action_type}</span>
                        </span>
                        <span data-testid={`actions-detail-assignee-${action.action_key}`}>
                          {t('actions.detail.assignee', 'Assignee')}:{' '}
                          <span
                            className={cn(
                              'font-medium',
                              action.assignee ? 'text-foreground' : 'italic text-muted-foreground',
                            )}
                          >
                            {assigneeLabel}
                          </span>
                        </span>
                        {action.created_at ? (
                          <span>
                            {t('actions.detail.created', 'Created')}:{' '}
                            <span className="font-medium text-foreground">
                              {new Date(action.created_at).toLocaleDateString()}
                            </span>
                          </span>
                        ) : null}
                        {action.completed_at ? (
                          <span>
                            {t('actions.detail.completed', 'Completed')}:{' '}
                            <span className="font-medium text-foreground">
                              {new Date(action.completed_at).toLocaleDateString()}
                            </span>
                          </span>
                        ) : null}
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          {t('actions.detail.description')}
                        </p>
                        <p className="mt-1 whitespace-pre-wrap text-foreground">
                          {action.description || '—'}
                        </p>
                      </div>
                      {(action.clause_reference || action.source_title) && (
                        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                          {action.clause_reference ? (
                            <Badge variant="outline" className="text-[10px]">
                              {action.clause_reference}
                            </Badge>
                          ) : null}
                          {action.source_title ? <span>{action.source_title}</span> : null}
                        </div>
                      )}
                      {sourceLink ? (
                        <div data-testid={`actions-detail-source-${action.action_key}`}>
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                            {t('actions.detail.source', 'Source record')}
                          </p>
                          <Button variant="outline" size="sm" className="mt-1 h-8" asChild>
                            <Link to={sourceLink.href}>
                              {t(sourceLink.labelKey, sourceLink.labelFallback)}
                              <ArrowUpRight className="ml-1 h-3 w-3" aria-hidden="true" />
                            </Link>
                          </Button>
                        </div>
                      ) : null}
                      {showFindingLoopCta ? (
                        <div
                          className="rounded-lg border border-emerald-300/60 bg-emerald-50/80 p-3 text-sm text-emerald-950 dark:border-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-100"
                          role="status"
                          data-testid={`actions-finding-loop-${action.action_key}`}
                        >
                          <p className="font-medium">{t('actions.finding_loop_cta.title')}</p>
                          <p className="mt-1 text-xs opacity-90">{t('actions.finding_loop_cta.body')}</p>
                          <Button variant="secondary" size="sm" className="mt-2" asChild>
                            <Link to={`/audits?view=findings&findingId=${action.source_id}`}>
                              {t('actions.finding_loop_cta.action')}
                              <ArrowUpRight className="ml-1 h-3 w-3" aria-hidden="true" />
                            </Link>
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <Dialog
        open={showModal}
        onOpenChange={(open) => {
          setShowModal(open)
          if (!open) {
            setFormData(INITIAL_FORM)
            setSubmitError(null)
            setSubmitSuccess(false)
          }
        }}
      >
        <DialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            createTriggerRef.current?.focus()
          }}
        >
          <DialogHeader>
            <DialogTitle>{t('actions.dialog.title')}</DialogTitle>
          </DialogHeader>

          {submitSuccess ? (
            <div className="py-8 text-center">
              <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-success" />
              </div>
              <p className="text-lg font-semibold text-foreground mb-2">{t('actions.created')}</p>
              <p className="text-muted-foreground">{t('actions.created_message')}</p>
              <p className="mt-3 text-sm text-muted-foreground" data-testid="actions-created-next-steps">
                {createReturnTo
                  ? t(
                      'actions.created_return_hint',
                      'Saved — you return to the case shortly. Assign and complete on the action profile anytime.',
                    )
                  : t(
                      'actions.created_next_steps',
                      'Open the action profile to assign an owner and mark completion when work is done.',
                    )}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label
                  htmlFor="actions-field-0"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('common.title')} <span className="text-destructive">*</span>
                </label>
                <Input
                  id="actions-field-0"
                  placeholder="Action title..."
                  value={formData.title}
                  onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                  required
                  maxLength={300}
                />
              </div>

              <div>
                <label
                  htmlFor="actions-field-1"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('common.description')} <span className="text-destructive">*</span>
                </label>
                <Textarea
                  id="actions-field-1"
                  rows={3}
                  placeholder="Describe the action required..."
                  value={formData.description}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, description: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="actions-field-2"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('actions.form.source_type')}
                  </label>
                  <Select
                    value={formData.source_type}
                    onValueChange={(value) =>
                      setFormData((prev) => ({ ...prev, source_type: value }))
                    }
                  >
                    <SelectTrigger id="actions-field-2">
                      <SelectValue placeholder="Select source" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="incident">Incident</SelectItem>
                      <SelectItem value="audit_finding">Audit Finding</SelectItem>
                      <SelectItem value="rta">RTA</SelectItem>
                      <SelectItem value="complaint">Complaint</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label
                    htmlFor="actions-field-3"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Source ID <span className="text-destructive">*</span>
                  </label>
                  <Input
                    id="actions-field-3"
                    type="number"
                    placeholder="e.g., 42"
                    value={formData.source_id}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, source_id: e.target.value }))
                    }
                    required
                    min={1}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="actions-field-4"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('common.priority')}
                  </label>
                  <Select
                    value={formData.priority}
                    onValueChange={(value) => setFormData((prev) => ({ ...prev, priority: value }))}
                  >
                    <SelectTrigger id="actions-field-4">
                      <SelectValue placeholder="Select priority" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label
                    htmlFor="actions-field-5"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('common.due_date')}
                  </label>
                  <Input
                    id="actions-field-5"
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData((prev) => ({ ...prev, due_date: e.target.value }))}
                    min={new Date().toISOString().split('T')[0]}
                  />
                </div>
              </div>

              {/* Error Message */}
              {submitError && (
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-destructive">
                      {submitError.error_class}
                    </p>
                    <p className="text-sm text-destructive/80">{submitError.message}</p>
                  </div>
                </div>
              )}

              <p
                className="text-xs text-muted-foreground"
                data-testid="actions-create-next-steps"
              >
                {t(
                  'actions.create.assign_on_profile',
                  'Assignee and completion are saved on the action profile after create — not in this dialog.',
                )}
              </p>

              <DialogFooter className="gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowModal(false)}
                  disabled={isSubmitting}
                >
                  {t('cancel')}
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {t('actions.creating')}
                    </>
                  ) : (
                    t('actions.create')
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
