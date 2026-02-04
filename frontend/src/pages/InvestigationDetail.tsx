import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft,
  FlaskConical,
  Clock,
  FileQuestion,
  GitBranch,
  CheckCircle,
  AlertTriangle,
  Car,
  MessageSquare,
  Loader2,
  RefreshCw,
  User,
  Calendar,
  FileText,
  ListTodo,
  History,
  Package,
  Plus,
  Send,
  Download,
  CheckCircle2,
  XCircle,
  Filter,
} from 'lucide-react'
import {
  investigationsApi,
  actionsApi,
  Investigation,
  TimelineEvent,
  InvestigationComment,
  CustomerPackSummary,
  ClosureValidation,
  Action,
  getApiErrorMessage,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/Tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/Dialog'
import { cn } from '../helpers/utils'
import { getStatusDisplay } from '../utils/investigationStatusFilter'
import { UserEmailSearch } from '../components/UserEmailSearch'

// Tab definitions
const TABS = [
  { id: 'summary', label: 'Summary', icon: FileText },
  { id: 'timeline', label: 'Timeline', icon: History },
  { id: 'evidence', label: 'Evidence', icon: FileQuestion },
  { id: 'rca', label: 'RCA', icon: GitBranch },
  { id: 'actions', label: 'Actions', icon: ListTodo },
  { id: 'report', label: 'Report', icon: Package },
] as const

type TabId = typeof TABS[number]['id']

// Status steps for progress indicator
const STATUS_STEPS = [
  { id: 'draft', label: 'Draft', icon: FileQuestion },
  { id: 'in_progress', label: 'In Progress', icon: Clock },
  { id: 'under_review', label: 'Under Review', icon: GitBranch },
  { id: 'completed', label: 'Completed', icon: CheckCircle },
]

const ENTITY_ICONS: Record<string, typeof AlertTriangle> = {
  road_traffic_collision: Car,
  reporting_incident: AlertTriangle,
  complaint: MessageSquare,
}

// Action status options
const ACTION_STATUS_OPTIONS = [
  { value: 'open', label: 'Open', className: 'bg-warning/10 text-warning' },
  { value: 'in_progress', label: 'In Progress', className: 'bg-info/10 text-info' },
  { value: 'pending_verification', label: 'Pending Verification', className: 'bg-purple-100 text-purple-800' },
  { value: 'completed', label: 'Completed', className: 'bg-success/10 text-success' },
  { value: 'cancelled', label: 'Cancelled', className: 'bg-muted text-muted-foreground' },
]

export default function InvestigationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const investigationId = parseInt(id || '0', 10)

  // Core state
  const [investigation, setInvestigation] = useState<Investigation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('summary')

  // Tab data states
  const [timeline, setTimeline] = useState<TimelineEvent[]>([])
  const [timelineLoading, setTimelineLoading] = useState(false)
  const [timelineFilter, setTimelineFilter] = useState<string>('all')

  const [comments, setComments] = useState<InvestigationComment[]>([])
  const [commentsLoading, setCommentsLoading] = useState(false)
  const [newComment, setNewComment] = useState('')
  const [addingComment, setAddingComment] = useState(false)

  const [packs, setPacks] = useState<CustomerPackSummary[]>([])
  const [packsLoading, setPacksLoading] = useState(false)
  const [generatingPack, setGeneratingPack] = useState(false)

  const [closureValidation, setClosureValidation] = useState<ClosureValidation | null>(null)
  const [closureLoading, setClosureLoading] = useState(false)

  const [actions, setActions] = useState<Action[]>([])
  const [actionsLoading, setActionsLoading] = useState(false)
  const [actionStatusFilter, setActionStatusFilter] = useState<string>('all')

  // Action modal state
  const [showActionModal, setShowActionModal] = useState(false)
  const [creatingAction, setCreatingAction] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionForm, setActionForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    assigned_to: '',
  })

  // Load investigation
  const loadInvestigation = useCallback(async () => {
    if (!investigationId || investigationId === 0) {
      setError('Invalid investigation ID')
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await investigationsApi.get(investigationId)
      setInvestigation(response.data)
    } catch (err) {
      console.error('Failed to load investigation:', err)
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [investigationId])

  // Load timeline
  const loadTimeline = useCallback(async () => {
    if (!investigationId) return
    setTimelineLoading(true)
    try {
      const response = await investigationsApi.getTimeline(investigationId, {
        page: 1,
        page_size: 50,
        type: timelineFilter !== 'all' ? timelineFilter : undefined,
      })
      setTimeline(response.data.items)
    } catch (err) {
      console.error('Failed to load timeline:', err)
    } finally {
      setTimelineLoading(false)
    }
  }, [investigationId, timelineFilter])

  // Load comments
  const loadComments = useCallback(async () => {
    if (!investigationId) return
    setCommentsLoading(true)
    try {
      const response = await investigationsApi.getComments(investigationId, {
        page: 1,
        page_size: 50,
      })
      setComments(response.data.items)
    } catch (err) {
      console.error('Failed to load comments:', err)
    } finally {
      setCommentsLoading(false)
    }
  }, [investigationId])

  // Load packs
  const loadPacks = useCallback(async () => {
    if (!investigationId) return
    setPacksLoading(true)
    try {
      const response = await investigationsApi.getPacks(investigationId, {
        page: 1,
        page_size: 50,
      })
      setPacks(response.data.items)
    } catch (err) {
      console.error('Failed to load packs:', err)
    } finally {
      setPacksLoading(false)
    }
  }, [investigationId])

  // Load closure validation
  const loadClosureValidation = useCallback(async () => {
    if (!investigationId) return
    setClosureLoading(true)
    try {
      const response = await investigationsApi.getClosureValidation(investigationId)
      setClosureValidation(response.data)
    } catch (err) {
      console.error('Failed to load closure validation:', err)
    } finally {
      setClosureLoading(false)
    }
  }, [investigationId])

  // Load actions
  const loadActions = useCallback(async () => {
    if (!investigationId) return
    setActionsLoading(true)
    try {
      const response = await actionsApi.list(
        1,
        50,
        actionStatusFilter !== 'all' ? actionStatusFilter : undefined,
        'investigation',
        investigationId
      )
      setActions(response.data.items || [])
    } catch (err) {
      console.error('Failed to load actions:', err)
    } finally {
      setActionsLoading(false)
    }
  }, [investigationId, actionStatusFilter])

  // Initial load
  useEffect(() => {
    loadInvestigation()
  }, [loadInvestigation])

  // Load tab data when tab changes
  useEffect(() => {
    if (!investigationId) return

    switch (activeTab) {
      case 'timeline':
        loadTimeline()
        break
      case 'summary':
        loadComments()
        loadClosureValidation()
        break
      case 'actions':
        loadActions()
        break
      case 'report':
        loadPacks()
        break
    }
  }, [activeTab, investigationId, loadTimeline, loadComments, loadClosureValidation, loadActions, loadPacks])

  // Reload timeline when filter changes
  useEffect(() => {
    if (activeTab === 'timeline') {
      loadTimeline()
    }
  }, [timelineFilter, activeTab, loadTimeline])

  // Reload actions when filter changes
  useEffect(() => {
    if (activeTab === 'actions') {
      loadActions()
    }
  }, [actionStatusFilter, activeTab, loadActions])

  // Add comment handler
  const handleAddComment = async () => {
    if (!newComment.trim() || !investigationId) return

    setAddingComment(true)
    try {
      await investigationsApi.addComment(investigationId, newComment.trim())
      setNewComment('')
      await loadComments()
    } catch (err) {
      console.error('Failed to add comment:', err)
    } finally {
      setAddingComment(false)
    }
  }

  // Generate pack handler
  const handleGeneratePack = async (audience: string) => {
    if (!investigationId) return

    setGeneratingPack(true)
    try {
      await investigationsApi.generatePack(investigationId, audience)
      await loadPacks()
    } catch (err) {
      console.error('Failed to generate pack:', err)
    } finally {
      setGeneratingPack(false)
    }
  }

  // Create action handler
  const handleCreateAction = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!investigationId) return

    setCreatingAction(true)
    setActionError(null)
    try {
      await actionsApi.create({
        title: actionForm.title,
        description: actionForm.description || `Action from investigation`,
        priority: actionForm.priority,
        due_date: actionForm.due_date || undefined,
        action_type: 'corrective',
        source_type: 'investigation',
        source_id: investigationId,
        assigned_to_email: actionForm.assigned_to || undefined,
      })
      setShowActionModal(false)
      setActionForm({
        title: '',
        description: '',
        priority: 'medium',
        due_date: '',
        assigned_to: '',
      })
      await loadActions()
    } catch (err) {
      setActionError(getApiErrorMessage(err))
    } finally {
      setCreatingAction(false)
    }
  }

  // Update action status
  const handleUpdateActionStatus = async (actionId: number, newStatus: string, completionNotes?: string) => {
    try {
      await actionsApi.update(actionId, 'investigation', {
        status: newStatus,
        completion_notes: newStatus === 'completed' ? completionNotes : undefined,
      })
      await loadActions()
    } catch (err) {
      console.error('Failed to update action:', err)
    }
  }

  // Get status index for progress indicator
  const getStatusIndex = (status: string) => {
    return STATUS_STEPS.findIndex(s => s.id === status)
  }

  // Get entity icon
  const getEntityIcon = (type: string) => {
    return ENTITY_ICONS[type] || AlertTriangle
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  // Error state
  if (error || !investigation) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-16 h-16 text-destructive" />
        <h2 className="text-xl font-semibold text-foreground">
          {error || 'Investigation not found'}
        </h2>
        <p className="text-muted-foreground">
          HTTP Status: {error?.includes('404') ? '404' : 'Error'}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/investigations')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Investigations
          </Button>
          <Button onClick={loadInvestigation}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  const EntityIcon = getEntityIcon(investigation.assigned_entity_type)
  const statusIndex = getStatusIndex(investigation.status)
  const statusDisplay = getStatusDisplay(investigation.status)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex-1">
          {/* Back button */}
          <Link
            to="/investigations"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Investigations
          </Link>

          {/* Title section */}
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center flex-shrink-0">
              <FlaskConical className="w-8 h-8 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2 flex-wrap">
                <span className="font-mono text-sm text-primary">
                  {investigation.reference_number}
                </span>
                <Badge className={statusDisplay.className}>
                  {statusDisplay.label}
                </Badge>
                <span className="px-2 py-0.5 text-xs font-medium rounded bg-surface text-muted-foreground capitalize flex items-center gap-1">
                  <EntityIcon className="w-3 h-3" />
                  {investigation.assigned_entity_type.replace(/_/g, ' ')}
                </span>
              </div>
              <h1 className="text-2xl font-bold text-foreground">
                {investigation.title}
              </h1>
              {investigation.description && (
                <p className="text-muted-foreground mt-2 line-clamp-2">
                  {investigation.description}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Status Progress */}
        <div className="flex items-center gap-2 lg:w-80">
          {STATUS_STEPS.map((step, stepIndex) => {
            const isActive = stepIndex <= statusIndex
            const isCurrent = stepIndex === statusIndex
            return (
              <div key={step.id} className="flex items-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        className={cn(
                          'relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-300',
                          isCurrent
                            ? 'bg-primary shadow-lg'
                            : isActive
                            ? 'bg-primary/20'
                            : 'bg-surface'
                        )}
                      >
                        <step.icon
                          className={cn(
                            'w-5 h-5',
                            isActive ? 'text-primary-foreground' : 'text-muted-foreground'
                          )}
                        />
                        {isCurrent && (
                          <div className="absolute inset-0 rounded-xl animate-pulse bg-primary/30" />
                        )}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>{step.label}</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {stepIndex < STATUS_STEPS.length - 1 && (
                  <div
                    className={cn(
                      'w-4 h-0.5 mx-1',
                      isActive ? 'bg-primary' : 'bg-muted'
                    )}
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="flex gap-1 overflow-x-auto pb-px">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors',
                'border-b-2 -mb-px',
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {/* Summary Tab */}
        {activeTab === 'summary' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main content */}
            <div className="lg:col-span-2 space-y-6">
              {/* Description */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Description</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">
                  {investigation.description || 'No description provided.'}
                </p>
              </Card>

              {/* Findings & Conclusion */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">
                  Findings & Conclusion
                </h3>
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-1">Findings</h4>
                    <p className="text-foreground">
                      {(investigation.data as any)?.findings || 'Not yet documented.'}
                    </p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-1">Conclusion</h4>
                    <p className="text-foreground">
                      {(investigation.data as any)?.conclusion || 'Not yet documented.'}
                    </p>
                  </div>
                </div>
              </Card>

              {/* Recent Notes Preview */}
              <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-foreground">Recent Notes</h3>
                  <span className="text-sm text-muted-foreground">
                    {comments.length} total
                  </span>
                </div>
                {commentsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                  </div>
                ) : comments.length === 0 ? (
                  <p className="text-muted-foreground text-center py-4">No notes yet.</p>
                ) : (
                  <div className="space-y-3">
                    {comments.slice(0, 3).map(comment => (
                      <div key={comment.id} className="p-3 bg-surface rounded-lg">
                        <p className="text-sm text-foreground">{comment.body}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {new Date(comment.created_at).toLocaleString()}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Details */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Details</h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <User className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Lead Investigator</p>
                      <p className="text-sm text-foreground">
                        {(investigation.data as any)?.lead_investigator || 'Not assigned'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Calendar className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Started</p>
                      <p className="text-sm text-foreground">
                        {investigation.started_at
                          ? new Date(investigation.started_at).toLocaleDateString()
                          : 'Not started'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Completed</p>
                      <p className="text-sm text-foreground">
                        {investigation.completed_at
                          ? new Date(investigation.completed_at).toLocaleDateString()
                          : 'In progress'}
                      </p>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Closure Checklist */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">
                  Closure Checklist
                </h3>
                {closureLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                  </div>
                ) : closureValidation ? (
                  <div className="space-y-3">
                    <div
                      className={cn(
                        'flex items-center gap-2 p-3 rounded-lg',
                        closureValidation.status === 'OK'
                          ? 'bg-success/10 text-success'
                          : 'bg-warning/10 text-warning'
                      )}
                    >
                      {closureValidation.status === 'OK' ? (
                        <CheckCircle2 className="w-5 h-5" />
                      ) : (
                        <XCircle className="w-5 h-5" />
                      )}
                      <span className="font-medium">
                        {closureValidation.status === 'OK'
                          ? 'Ready for Closure'
                          : 'Cannot Close Yet'}
                      </span>
                    </div>
                    {closureValidation.reason_codes.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">Issues:</p>
                        {closureValidation.reason_codes.map((code, i) => (
                          <p key={i} className="text-xs text-destructive">
                            • {code.replace(/_/g, ' ')}
                          </p>
                        ))}
                      </div>
                    )}
                    {closureValidation.missing_fields.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">
                          Missing Fields:
                        </p>
                        {closureValidation.missing_fields.map((field, i) => (
                          <p key={i} className="text-xs text-muted-foreground">
                            • {field}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">
                    Unable to load closure validation.
                  </p>
                )}
              </Card>
            </div>
          </div>
        )}

        {/* Timeline Tab */}
        {activeTab === 'timeline' && (
          <div className="space-y-4">
            {/* Filter */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <Select value={timelineFilter} onValueChange={setTimelineFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Events</SelectItem>
                    <SelectItem value="status_change">Status Changes</SelectItem>
                    <SelectItem value="field_update">Field Updates</SelectItem>
                    <SelectItem value="comment">Comments</SelectItem>
                    <SelectItem value="action">Actions</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button variant="outline" size="sm" onClick={loadTimeline}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>

            {/* Timeline list */}
            {timelineLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : timeline.length === 0 ? (
              <Card className="p-12 text-center">
                <History className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-semibold text-foreground mb-2">No Timeline Events</h3>
                <p className="text-muted-foreground">
                  Events will appear here as the investigation progresses.
                </p>
              </Card>
            ) : (
              <div className="space-y-4">
                {timeline.map(event => (
                  <Card key={event.id} className="p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <History className="w-5 h-5 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-foreground">
                            {event.event_type.replace(/_/g, ' ')}
                          </span>
                          <Badge variant="outline" className="text-xs">
                            {event.field_path || 'System'}
                          </Badge>
                        </div>
                        {event.old_value && event.new_value && (
                          <p className="text-sm text-muted-foreground">
                            Changed from "{event.old_value}" to "{event.new_value}"
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          {new Date(event.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Evidence Tab */}
        {activeTab === 'evidence' && (
          <Card className="p-12 text-center">
            <FileQuestion className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">Evidence Register</h3>
            <p className="text-muted-foreground max-w-md mx-auto mb-4">
              Evidence assets linked to this investigation will appear here.
              Use the Evidence Assets module to upload and link documents.
            </p>
            <Button variant="outline" disabled>
              <Plus className="w-4 h-4 mr-2" />
              Link Evidence (Coming Soon)
            </Button>
          </Card>
        )}

        {/* RCA Tab */}
        {activeTab === 'rca' && (
          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-primary" />
                5 Whys Analysis
              </h3>
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map(num => (
                  <div key={num} className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0 font-bold text-primary-foreground">
                      {num}
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-foreground mb-2">
                        Why {num}?
                      </label>
                      <Textarea
                        rows={2}
                        placeholder={`Enter the ${num === 1 ? 'initial' : 'deeper'} cause...`}
                        defaultValue={
                          (investigation.data as any)?.[`why_${num}`] || ''
                        }
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-6 border-primary/20 bg-primary/5">
              <h3 className="text-lg font-semibold text-foreground mb-4">Root Cause Identified</h3>
              <Textarea
                rows={3}
                placeholder="Document the root cause based on your 5 Whys analysis..."
                defaultValue={(investigation.data as any)?.root_cause || ''}
              />
            </Card>

            <div className="flex justify-end">
              <Button>Save RCA Analysis</Button>
            </div>
          </div>
        )}

        {/* Actions Tab */}
        {activeTab === 'actions' && (
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Select value={actionStatusFilter} onValueChange={setActionStatusFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    {ACTION_STATUS_OPTIONS.map(opt => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add Action
              </Button>
            </div>

            {/* Actions list */}
            {actionsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : actions.length === 0 ? (
              <Card className="p-12 text-center">
                <ListTodo className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-semibold text-foreground mb-2">No Actions</h3>
                <p className="text-muted-foreground max-w-md mx-auto">
                  Corrective actions for this investigation will appear here.
                </p>
              </Card>
            ) : (
              <div className="space-y-3">
                {actions.map(action => (
                  <Card key={action.id} className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-foreground">{action.title}</h4>
                          <Badge className={ACTION_STATUS_OPTIONS.find(o => o.value === action.status)?.className}>
                            {action.status.replace(/_/g, ' ')}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {action.description}
                        </p>
                        {action.owner_email && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Assigned to: {action.owner_email}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            action.priority === 'critical' && 'border-destructive text-destructive',
                            action.priority === 'high' && 'border-warning text-warning',
                            action.priority === 'medium' && 'border-info text-info'
                          )}
                        >
                          {action.priority}
                        </Badge>
                        {action.due_date && (
                          <span className="text-xs text-muted-foreground">
                            Due: {new Date(action.due_date).toLocaleDateString()}
                          </span>
                        )}
                        <Select
                          value={action.status}
                          onValueChange={(newStatus) => {
                            if (newStatus === 'completed') {
                              const notes = window.prompt('Enter completion notes (optional):')
                              handleUpdateActionStatus(action.id, newStatus, notes || undefined)
                            } else {
                              handleUpdateActionStatus(action.id, newStatus)
                            }
                          }}
                        >
                          <SelectTrigger className="w-36 h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ACTION_STATUS_OPTIONS.map(opt => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Report Tab */}
        {activeTab === 'report' && (
          <div className="space-y-6">
            {/* Generate Pack */}
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Generate Report</h3>
              <div className="flex items-center gap-4">
                <Button
                  onClick={() => handleGeneratePack('internal_customer')}
                  disabled={generatingPack}
                >
                  {generatingPack ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  Internal Report
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleGeneratePack('external_customer')}
                  disabled={generatingPack}
                >
                  {generatingPack ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  External Report
                </Button>
              </div>
            </Card>

            {/* Packs History */}
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Report History</h3>
              {packsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : packs.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                  No reports generated yet.
                </p>
              ) : (
                <div className="space-y-3">
                  {packs.map(pack => (
                    <div
                      key={pack.id}
                      className="flex items-center justify-between p-3 bg-surface rounded-lg"
                    >
                      <div>
                        <p className="font-medium text-foreground">
                          {pack.audience.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(pack.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-muted-foreground">
                          {pack.pack_uuid.slice(0, 8)}...
                        </span>
                        <Button variant="ghost" size="sm">
                          <Download className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}
      </div>

      {/* Add Comment Section (always visible at bottom of summary) */}
      {activeTab === 'summary' && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Add Note</h3>
          <div className="flex gap-4">
            <Textarea
              value={newComment}
              onChange={e => setNewComment(e.target.value)}
              placeholder="Add a note to this investigation..."
              rows={2}
              className="flex-1"
            />
            <Button
              onClick={handleAddComment}
              disabled={addingComment || !newComment.trim()}
            >
              {addingComment ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </Card>
      )}

      {/* Add Action Modal */}
      <Dialog open={showActionModal} onOpenChange={setShowActionModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Corrective Action</DialogTitle>
            <DialogDescription>
              Create a corrective action for this investigation
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Action Title *
              </label>
              <Input
                value={actionForm.title}
                onChange={e => setActionForm({ ...actionForm, title: e.target.value })}
                placeholder="e.g., Implement additional safety controls"
                required
              />
            </div>
            <UserEmailSearch
              label="Assign To"
              value={actionForm.assigned_to}
              onChange={email => setActionForm({ ...actionForm, assigned_to: email })}
              placeholder="Search by email..."
            />
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Priority
              </label>
              <Select
                value={actionForm.priority}
                onValueChange={value => setActionForm({ ...actionForm, priority: value })}
              >
                <SelectTrigger>
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
              <label className="block text-sm font-medium text-foreground mb-1">
                Due Date
              </label>
              <Input
                type="date"
                value={actionForm.due_date}
                onChange={e => setActionForm({ ...actionForm, due_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Description
              </label>
              <Textarea
                value={actionForm.description}
                onChange={e => setActionForm({ ...actionForm, description: e.target.value })}
                placeholder="Describe the corrective action to be taken..."
                rows={3}
              />
            </div>
            {actionError && (
              <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-md text-sm text-destructive">
                <strong>Error:</strong> {actionError}
              </div>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowActionModal(false)
                  setActionError(null)
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={creatingAction || !actionForm.title}>
                {creatingAction ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Create Action'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
