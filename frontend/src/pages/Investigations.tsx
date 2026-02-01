import { useEffect, useState, useCallback } from 'react'
import { Plus, Search, FlaskConical, ArrowRight, FileQuestion, GitBranch, CheckCircle, Clock, AlertTriangle, Car, MessageSquare, Loader2, ExternalLink, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { investigationsApi, actionsApi, Investigation, getApiErrorMessage, SourceRecordItem, CreateFromRecordError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/Select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/Dialog'
import { cn } from "../helpers/utils"
import { UserEmailSearch } from '../components/UserEmailSearch'

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

// Action type for display
interface ActionItem {
  id: number
  title: string
  description: string
  priority: string
  status: string
  due_date?: string
  owner_email?: string
  reference_number?: string
  created_at?: string
  completed_at?: string
  completion_notes?: string
  source_type?: string
  source_id?: number
}

// Status options for action update
const ACTION_STATUS_OPTIONS = [
  { value: 'open', label: 'Open', className: 'bg-warning/10 text-warning' },
  { value: 'in_progress', label: 'In Progress', className: 'bg-info/10 text-info' },
  { value: 'pending_verification', label: 'Pending Verification', className: 'bg-purple-100 text-purple-800' },
  { value: 'completed', label: 'Completed', className: 'bg-success/10 text-success' },
  { value: 'cancelled', label: 'Cancelled', className: 'bg-muted text-muted-foreground' },
]

// Source type options for investigation creation
const SOURCE_TYPES = [
  { value: 'near_miss', label: 'Near Miss', icon: AlertTriangle },
  { value: 'road_traffic_collision', label: 'Road Traffic Collision', icon: Car },
  { value: 'complaint', label: 'Complaint', icon: MessageSquare },
  { value: 'reporting_incident', label: 'Incident', icon: AlertTriangle },
]

// Investigation level badges - will be used in future level indicator UI
// Exported to satisfy noUnusedLocals while preserving scaffolding
export const LEVEL_BADGES: Record<string, { label: string; className: string }> = {
  low: { label: 'LOW', className: 'bg-green-100 text-green-800' },
  medium: { label: 'MEDIUM', className: 'bg-yellow-100 text-yellow-800' },
  high: { label: 'HIGH', className: 'bg-red-100 text-red-800' },
}

// Create Investigation Modal Component with Dropdown Selector
function CreateInvestigationModal({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const navigate = useNavigate()
  const [sourceType, setSourceType] = useState('')
  const [selectedRecord, setSelectedRecord] = useState<SourceRecordItem | null>(null)
  const [title, setTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{ id: number; reference: string } | null>(null)

  // Source records state
  const [sourceRecords, setSourceRecords] = useState<SourceRecordItem[]>([])
  const [loadingRecords, setLoadingRecords] = useState(false)
  const [recordsError, setRecordsError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchDebounce, setSearchDebounce] = useState<ReturnType<typeof setTimeout> | null>(null)

  const resetForm = () => {
    setSourceType('')
    setSelectedRecord(null)
    setTitle('')
    setError('')
    setExistingInvestigation(null)
    setSourceRecords([])
    setSearchQuery('')
    setRecordsError('')
  }

  // Load source records when type changes
  const loadSourceRecords = useCallback(async (type: string, query?: string) => {
    if (!type) {
      setSourceRecords([])
      return
    }

    setLoadingRecords(true)
    setRecordsError('')

    try {
      const response = await investigationsApi.listSourceRecords(type, {
        q: query,
        page: 1,
        size: 50,
      })
      setSourceRecords(response.data.items)
    } catch (err) {
      console.error('Failed to load source records:', err)
      setRecordsError('Failed to load records. Please try again.')
      setSourceRecords([])
    } finally {
      setLoadingRecords(false)
    }
  }, [])

  // Handle source type change
  const handleSourceTypeChange = (type: string) => {
    setSourceType(type)
    setSelectedRecord(null)
    setSearchQuery('')
    setError('')
    setExistingInvestigation(null)
    loadSourceRecords(type)
  }

  // Handle search with debounce
  const handleSearchChange = (query: string) => {
    setSearchQuery(query)
    if (searchDebounce) clearTimeout(searchDebounce)
    setSearchDebounce(
      setTimeout(() => {
        loadSourceRecords(sourceType, query)
      }, 300)
    )
  }

  // Handle record selection
  const handleRecordSelect = (record: SourceRecordItem) => {
    if (record.investigation_id) {
      // Already investigated - show link to existing
      setExistingInvestigation({
        id: record.investigation_id,
        reference: record.investigation_reference || `INV-${record.investigation_id}`,
      })
      setSelectedRecord(null)
      return
    }
    setExistingInvestigation(null)
    setSelectedRecord(record)
    // Auto-generate title from record
    if (!title) {
      setTitle(`Investigation - ${record.reference_number}`)
    }
  }

  const handleCreate = async () => {
    if (!sourceType || !selectedRecord || !title.trim()) {
      setError('Please select a source record and provide a title')
      return
    }

    setCreating(true)
    setError('')
    setExistingInvestigation(null)

    try {
      await investigationsApi.createFromRecord({
        source_type: sourceType as any,
        source_id: selectedRecord.source_id,
        title: title.trim(),
      })
      onCreated()
      resetForm()
    } catch (err: any) {
      // Safe error handling - check for 409 Conflict (already exists)
      if (err.response?.status === 409) {
        const errorData = err.response?.data?.detail as CreateFromRecordError | undefined
        if (errorData?.error_code === 'INV_ALREADY_EXISTS' && errorData.details?.existing_investigation_id) {
          setExistingInvestigation({
            id: errorData.details.existing_investigation_id,
            reference: errorData.details.existing_reference_number || `INV-${errorData.details.existing_investigation_id}`,
          })
          setError('An investigation already exists for this record.')
          return
        }
      }
      // Generic error handling
      setError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const handleOpenExisting = () => {
    if (existingInvestigation) {
      onOpenChange(false)
      navigate(`/investigations/${existingInvestigation.id}`)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => {
      if (!isOpen) resetForm()
      onOpenChange(isOpen)
    }}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="w-5 h-5" />
            Create Investigation from Record
          </DialogTitle>
          <DialogDescription>
            Create a new investigation by selecting an existing record. Records that already have an investigation are marked.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4 overflow-y-auto max-h-[60vh]">
          {/* Source Type Selection */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Source Record Type *
            </label>
            <div className="grid grid-cols-2 gap-2">
              {SOURCE_TYPES.map((type) => {
                const Icon = type.icon
                return (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => handleSourceTypeChange(type.value)}
                    className={cn(
                      'flex items-center gap-2 p-3 rounded-lg border text-left transition-colors',
                      sourceType === type.value
                        ? 'border-primary bg-primary/5 text-primary'
                        : 'border-border hover:border-primary/50'
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm font-medium">{type.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Source Record Selector (replaces free-text ID) */}
          {sourceType && (
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Select Source Record *
              </label>
              <div className="relative mb-2">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder="Search by reference or title..."
                  className="pl-9"
                />
                {loadingRecords && (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground animate-spin" />
                )}
              </div>

              {/* Records list */}
              <div className="border rounded-lg max-h-48 overflow-y-auto">
                {recordsError ? (
                  <div className="p-4 text-center text-destructive text-sm">
                    {recordsError}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => loadSourceRecords(sourceType, searchQuery)}
                      className="ml-2"
                    >
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Retry
                    </Button>
                  </div>
                ) : loadingRecords ? (
                  <div className="p-4 text-center text-muted-foreground">
                    <Loader2 className="w-5 h-5 mx-auto animate-spin" />
                  </div>
                ) : sourceRecords.length === 0 ? (
                  <div className="p-4 text-center text-muted-foreground text-sm">
                    No records found
                  </div>
                ) : (
                  sourceRecords.map((record) => {
                    const isAlreadyInvestigated = !!record.investigation_id
                    const isSelected = selectedRecord?.source_id === record.source_id
                    return (
                      <button
                        key={record.source_id}
                        type="button"
                        onClick={() => handleRecordSelect(record)}
                        className={cn(
                          'w-full flex items-center justify-between p-3 border-b last:border-b-0 text-left transition-colors',
                          isSelected && 'bg-primary/5 border-primary',
                          isAlreadyInvestigated
                            ? 'bg-muted/50 cursor-not-allowed opacity-70'
                            : 'hover:bg-surface'
                        )}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-primary">
                              {record.reference_number}
                            </span>
                            <span className={cn(
                              'px-1.5 py-0.5 text-xs rounded',
                              record.status === 'closed' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                            )}>
                              {record.status}
                            </span>
                          </div>
                          <p className="text-sm text-foreground truncate mt-0.5">
                            {record.display_label}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Created: {new Date(record.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        {isAlreadyInvestigated && (
                          <div className="flex items-center gap-1 ml-2 text-warning">
                            <CheckCircle className="w-4 h-4" />
                            <span className="text-xs whitespace-nowrap">Investigated</span>
                          </div>
                        )}
                        {isSelected && !isAlreadyInvestigated && (
                          <CheckCircle className="w-4 h-4 text-primary ml-2" />
                        )}
                      </button>
                    )
                  })
                )}
              </div>

              {selectedRecord && (
                <p className="text-xs text-primary mt-1">
                  Selected: {selectedRecord.reference_number}
                </p>
              )}
            </div>
          )}

          {/* Investigation Title */}
          {selectedRecord && (
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Investigation Title *
              </label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Investigation into vehicle collision on A1"
              />
            </div>
          )}

          {/* Info Banner */}
          {selectedRecord && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <h4 className="text-sm font-medium text-blue-900 mb-1">Deterministic Prefill</h4>
              <p className="text-xs text-blue-700">
                The investigation will be pre-populated with data from the source record using Mapping Contract v1.
                The investigation level (LOW/MEDIUM/HIGH) will be determined by the source severity.
              </p>
            </div>
          )}

          {/* Error Message with existing investigation link */}
          {error && (
            <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3">
              <p className="text-sm text-destructive">{error}</p>
              {existingInvestigation && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={handleOpenExisting}
                  className="mt-2 p-0 h-auto text-primary"
                >
                  <ExternalLink className="w-3 h-3 mr-1" />
                  Open existing investigation ({existingInvestigation.reference})
                </Button>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={creating}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={creating || !sourceType || !selectedRecord || !title.trim()}
          >
            {creating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Create Investigation
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function Investigations() {
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedInvestigation, setSelectedInvestigation] = useState<Investigation | null>(null)
  
  // Actions for selected investigation
  const [investigationActions, setInvestigationActions] = useState<ActionItem[]>([])
  const [loadingActions, setLoadingActions] = useState(false)
  
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
  
  // Action detail modal state
  const [selectedAction, setSelectedAction] = useState<ActionItem | null>(null)
  const [showActionDetailModal, setShowActionDetailModal] = useState(false)
  const [updatingAction, setUpdatingAction] = useState(false)
  const [actionUpdateError, setActionUpdateError] = useState<string | null>(null)

  useEffect(() => {
    loadInvestigations()
  }, [])

  // Load actions when investigation is selected
  useEffect(() => {
    if (selectedInvestigation) {
      loadActionsForInvestigation(selectedInvestigation)
    } else {
      setInvestigationActions([])
    }
  }, [selectedInvestigation])

  const loadActionsForInvestigation = async (investigation: Investigation) => {
    setLoadingActions(true)
    try {
      // Load actions with source_type=investigation filter
      const response = await actionsApi.list(1, 50, undefined, 'investigation', investigation.id)
      setInvestigationActions(response.data.items || [])
    } catch (err) {
      console.error('Failed to load actions:', err)
      setInvestigationActions([])
    } finally {
      setLoadingActions(false)
    }
  }

  const loadInvestigations = async () => {
    try {
      const response = await investigationsApi.list(1, 100)
      setInvestigations(response.data.items || [])
    } catch (err) {
      console.error('Failed to load investigations:', err)
      setInvestigations([])
    } finally {
      setLoading(false)
    }
  }

  const getStatusIndex = (status: string) => {
    return STATUS_STEPS.findIndex(s => s.id === status)
  }

  const handleCreateAction = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedInvestigation) return
    
    // Use 'investigation' as source_type and investigation.id as source_id
    // This creates actions directly on the investigation (InvestigationAction),
    // not on the underlying entity (IncidentAction/RTAAction/ComplaintAction)
    setCreatingAction(true)
    setActionError(null)
    try {
      await actionsApi.create({
        title: actionForm.title,
        description: actionForm.description || `Corrective action from investigation ${selectedInvestigation.reference_number}`,
        priority: actionForm.priority,
        due_date: actionForm.due_date || undefined,
        action_type: 'corrective',
        source_type: 'investigation',
        source_id: selectedInvestigation.id,
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
      // Reload actions to show the new one
      loadActionsForInvestigation(selectedInvestigation)
    } catch (err: any) {
      console.error('Failed to create action:', err)
      const errorMessage = getApiErrorMessage(err)
      setActionError(errorMessage)
      // Don't close modal on error - let user see and fix the issue
    } finally {
      setCreatingAction(false)
    }
  }

  const handleAssigneeChange = (email: string) => {
    setActionForm({ ...actionForm, assigned_to: email })
  }

  // Open action detail modal
  const handleOpenAction = (action: ActionItem) => {
    setSelectedAction(action)
    setShowActionDetailModal(true)
    setActionUpdateError(null)
  }

  // Update action status
  const handleUpdateActionStatus = async (newStatus: string, completionNotes?: string) => {
    if (!selectedAction || !selectedInvestigation) return
    
    setUpdatingAction(true)
    setActionUpdateError(null)
    try {
      await actionsApi.update(selectedAction.id, 'investigation', {
        status: newStatus,
        completion_notes: newStatus === 'completed' ? completionNotes : undefined,
      })
      // Reload actions to show updated status
      await loadActionsForInvestigation(selectedInvestigation)
      // Update selected action locally
      setSelectedAction(prev => prev ? { ...prev, status: newStatus, completion_notes: completionNotes } : null)
    } catch (err: any) {
      console.error('Failed to update action:', err)
      const errorMessage = getApiErrorMessage(err)
      setActionUpdateError(errorMessage)
    } finally {
      setUpdatingAction(false)
    }
  }

  // Mark action as complete
  const handleCompleteAction = async (completionNotes: string) => {
    await handleUpdateActionStatus('completed', completionNotes)
  }

  const getEntityIcon = (type: string) => {
    return ENTITY_ICONS[type] || AlertTriangle
  }

  const filteredInvestigations = investigations.filter(
    i => i.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         i.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const stats = {
    total: investigations.length,
    inProgress: investigations.filter(i => i.status === 'in_progress').length,
    underReview: investigations.filter(i => i.status === 'under_review').length,
    completed: investigations.filter(i => i.status === 'completed').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Root Cause Investigations</h1>
          <p className="text-muted-foreground mt-1">5-Whys analysis, RCA workflows & corrective actions</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Investigation
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total', value: stats.total, variant: 'primary' as const },
          { label: 'In Progress', value: stats.inProgress, variant: 'warning' as const },
          { label: 'Under Review', value: stats.underReview, variant: 'info' as const },
          { label: 'Completed', value: stats.completed, variant: 'success' as const },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center mb-3",
              stat.variant === 'primary' && "bg-primary/10",
              stat.variant === 'warning' && "bg-warning/10",
              stat.variant === 'info' && "bg-info/10",
              stat.variant === 'success' && "bg-success/10",
            )}>
              <span className={cn(
                "text-xl font-bold",
                stat.variant === 'primary' && "text-primary",
                stat.variant === 'warning' && "text-warning",
                stat.variant === 'info' && "text-info",
                stat.variant === 'success' && "text-success",
              )}>
                {stat.value}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
          </Card>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search investigations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Investigation Cards */}
      <div className="space-y-4">
        {filteredInvestigations.length === 0 ? (
          <Card className="p-12 text-center">
            <FlaskConical className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">No Investigations Found</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Start a root cause investigation to analyze incidents, RTAs, or complaints.
            </p>
          </Card>
        ) : (
          filteredInvestigations.map((investigation) => {
            const EntityIcon = getEntityIcon(investigation.assigned_entity_type)
            const statusIndex = getStatusIndex(investigation.status)
            
            return (
              <Card
                key={investigation.id}
                hoverable
                onClick={() => setSelectedInvestigation(investigation)}
                className="p-6 cursor-pointer"
              >
                <div className="flex flex-col lg:flex-row lg:items-center gap-6">
                  {/* Entity Icon */}
                  <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <EntityIcon className="w-8 h-8 text-primary" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-sm text-primary">{investigation.reference_number}</span>
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-surface text-muted-foreground capitalize">
                        {investigation.assigned_entity_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-1">
                      {investigation.title}
                    </h3>
                    {investigation.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2">{investigation.description}</p>
                    )}
                  </div>

                  {/* Status Timeline */}
                  <div className="flex items-center gap-2 lg:w-80">
                    {STATUS_STEPS.map((step, stepIndex) => {
                      const isActive = stepIndex <= statusIndex
                      const isCurrent = stepIndex === statusIndex
                      return (
                        <div key={step.id} className="flex items-center">
                          <div className={cn(
                            "relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-300",
                            isCurrent 
                              ? 'bg-primary shadow-lg' 
                              : isActive 
                                ? 'bg-primary/20' 
                                : 'bg-surface'
                          )}>
                            <step.icon className={cn(
                              "w-5 h-5",
                              isActive ? 'text-primary-foreground' : 'text-muted-foreground'
                            )} />
                            {isCurrent && (
                              <div className="absolute inset-0 rounded-xl animate-pulse bg-primary/30" />
                            )}
                          </div>
                          {stepIndex < STATUS_STEPS.length - 1 && (
                            <ArrowRight className={cn(
                              "w-4 h-4 mx-1",
                              isActive ? 'text-primary' : 'text-muted-foreground/30'
                            )} />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* RCA Preview */}
                {investigation.data && Object.keys(investigation.data).length > 0 && (
                  <div className="mt-6 pt-6 border-t border-border">
                    <div className="flex items-center gap-2 mb-3">
                      <GitBranch className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium text-primary">Root Cause Analysis</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {['Why 1', 'Why 2', 'Why 3'].map((why, i) => (
                        <Card key={i} className="p-3">
                          <span className="text-xs text-muted-foreground">{why}</span>
                          <p className="text-sm text-foreground mt-1">
                            {typeof investigation.data === 'object' && 
                              (investigation.data as Record<string, unknown>)[`why_${i + 1}`] as string || 
                              'Not documented'}
                          </p>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            )
          })
        )}
      </div>

      {/* Detail Modal */}
      <Dialog open={!!selectedInvestigation} onOpenChange={() => setSelectedInvestigation(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
          {selectedInvestigation && (
            <>
              <DialogHeader>
                <span className="font-mono text-sm text-primary">{selectedInvestigation.reference_number}</span>
                <DialogTitle>{selectedInvestigation.title}</DialogTitle>
                <DialogDescription>
                  Root cause investigation for {selectedInvestigation.assigned_entity_type.replace(/_/g, ' ')} record.
                  Status: {selectedInvestigation.status.replace(/_/g, ' ')}.
                </DialogDescription>
              </DialogHeader>
              <div className="overflow-y-auto max-h-[calc(90vh-120px)] space-y-6 py-4">
                {/* 5 Whys Analysis */}
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <GitBranch className="w-5 h-5 text-primary" />
                    5 Whys Analysis
                  </h3>
                  <div className="space-y-4">
                    {[1, 2, 3, 4, 5].map((num) => (
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
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Root Cause */}
                <Card className="p-6 border-primary/20 bg-primary/5">
                  <h3 className="text-lg font-semibold text-foreground mb-4">Root Cause Identified</h3>
                  <Textarea
                    rows={3}
                    placeholder="Document the root cause based on your 5 Whys analysis..."
                  />
                </Card>

                {/* Corrective Actions */}
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-4">Corrective Actions</h3>
                  
                  {/* Existing Actions */}
                  {loadingActions ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                    </div>
                  ) : investigationActions.length > 0 ? (
                    <div className="space-y-3 mb-4">
                      {investigationActions.map((action) => (
                        <Card 
                          key={action.id} 
                          className="p-4 cursor-pointer hover:bg-accent/50 transition-colors"
                          onClick={() => handleOpenAction(action)}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h4 className="font-medium text-foreground">{action.title}</h4>
                                <ArrowRight className="w-4 h-4 text-muted-foreground" />
                              </div>
                              <p className="text-sm text-muted-foreground line-clamp-2">{action.description}</p>
                              {action.owner_email && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  Assigned to: <span className="text-foreground">{action.owner_email}</span>
                                </p>
                              )}
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <span className={cn(
                                "px-2 py-0.5 text-xs font-medium rounded",
                                action.status === 'open' && "bg-warning/10 text-warning",
                                action.status === 'in_progress' && "bg-info/10 text-info",
                                action.status === 'pending_verification' && "bg-purple-100 text-purple-800",
                                action.status === 'completed' && "bg-success/10 text-success",
                                action.status === 'cancelled' && "bg-muted text-muted-foreground",
                              )}>
                                {action.status.replace(/_/g, ' ')}
                              </span>
                              <span className={cn(
                                "px-2 py-0.5 text-xs font-medium rounded",
                                action.priority === 'critical' && "bg-destructive/10 text-destructive",
                                action.priority === 'high' && "bg-warning/10 text-warning",
                                action.priority === 'medium' && "bg-info/10 text-info",
                                action.priority === 'low' && "bg-muted text-muted-foreground",
                              )}>
                                {action.priority}
                              </span>
                              {action.due_date && (
                                <span className="text-xs text-muted-foreground">
                                  Due: {new Date(action.due_date).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4 mb-4">
                      No corrective actions yet
                    </p>
                  )}
                  
                  <Button variant="outline" className="w-full" onClick={() => setShowActionModal(true)}>
                    <Plus className="w-5 h-5" />
                    Add Corrective Action
                  </Button>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Investigation Modal */}
      <CreateInvestigationModal
        open={showModal}
        onOpenChange={setShowModal}
        onCreated={() => {
          loadInvestigations()
          setShowModal(false)
        }}
      />

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
                onChange={(e) => setActionForm({ ...actionForm, title: e.target.value })}
                placeholder="e.g., Implement additional safety controls"
                required
              />
            </div>
            <UserEmailSearch
              label="Assign To"
              value={actionForm.assigned_to}
              onChange={handleAssigneeChange}
              placeholder="Search by email..."
            />
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Priority
              </label>
              <Select
                value={actionForm.priority}
                onValueChange={(value) => setActionForm({ ...actionForm, priority: value })}
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
                onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Description
              </label>
              <Textarea
                value={actionForm.description}
                onChange={(e) => setActionForm({ ...actionForm, description: e.target.value })}
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
              <Button type="button" variant="outline" onClick={() => { setShowActionModal(false); setActionError(null); }}>
                Cancel
              </Button>
              <Button type="submit" disabled={creatingAction || !actionForm.title}>
                {creatingAction ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Action'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Action Detail Modal */}
      <Dialog open={showActionDetailModal} onOpenChange={setShowActionDetailModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Action Details</DialogTitle>
            <DialogDescription>
              {selectedAction?.reference_number || `Action #${selectedAction?.id}`}
            </DialogDescription>
          </DialogHeader>
          
          {selectedAction && (
            <div className="space-y-4">
              {/* Title and Description */}
              <div>
                <h3 className="font-semibold text-lg text-foreground">{selectedAction.title}</h3>
                <p className="text-sm text-muted-foreground mt-1">{selectedAction.description}</p>
              </div>

              {/* Status and Priority */}
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-muted-foreground mb-1">Status</label>
                  <span className={cn(
                    "inline-block px-3 py-1 text-sm font-medium rounded",
                    selectedAction.status === 'open' && "bg-warning/10 text-warning",
                    selectedAction.status === 'in_progress' && "bg-info/10 text-info",
                    selectedAction.status === 'pending_verification' && "bg-purple-100 text-purple-800",
                    selectedAction.status === 'completed' && "bg-success/10 text-success",
                    selectedAction.status === 'cancelled' && "bg-muted text-muted-foreground",
                  )}>
                    {selectedAction.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-muted-foreground mb-1">Priority</label>
                  <span className={cn(
                    "inline-block px-3 py-1 text-sm font-medium rounded",
                    selectedAction.priority === 'critical' && "bg-destructive/10 text-destructive",
                    selectedAction.priority === 'high' && "bg-warning/10 text-warning",
                    selectedAction.priority === 'medium' && "bg-info/10 text-info",
                    selectedAction.priority === 'low' && "bg-muted text-muted-foreground",
                  )}>
                    {selectedAction.priority}
                  </span>
                </div>
              </div>

              {/* Assignee and Due Date */}
              <div className="flex gap-4">
                {selectedAction.owner_email && (
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-muted-foreground mb-1">Assigned To</label>
                    <span className="text-sm text-foreground">{selectedAction.owner_email}</span>
                  </div>
                )}
                {selectedAction.due_date && (
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-muted-foreground mb-1">Due Date</label>
                    <span className="text-sm text-foreground">{new Date(selectedAction.due_date).toLocaleDateString()}</span>
                  </div>
                )}
              </div>

              {/* Completion Notes */}
              {selectedAction.completion_notes && (
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-1">Completion Notes</label>
                  <p className="text-sm text-foreground bg-muted/50 p-2 rounded">{selectedAction.completion_notes}</p>
                </div>
              )}

              {/* Status Update Section */}
              <div className="border-t pt-4">
                <label className="block text-sm font-medium text-foreground mb-2">Update Status</label>
                <div className="flex flex-wrap gap-2">
                  {ACTION_STATUS_OPTIONS.map((option) => (
                    <Button
                      key={option.value}
                      type="button"
                      variant={selectedAction.status === option.value ? "default" : "outline"}
                      size="sm"
                      disabled={updatingAction || selectedAction.status === option.value}
                      onClick={() => {
                        if (option.value === 'completed') {
                          // Prompt for completion notes
                          const notes = window.prompt('Enter completion notes (optional):')
                          handleCompleteAction(notes || '')
                        } else {
                          handleUpdateActionStatus(option.value)
                        }
                      }}
                    >
                      {updatingAction && selectedAction.status !== option.value ? (
                        <Loader2 className="w-3 h-3 animate-spin mr-1" />
                      ) : null}
                      {option.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Error Message */}
              {actionUpdateError && (
                <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-md text-sm text-destructive">
                  <strong>Error:</strong> {actionUpdateError}
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setShowActionDetailModal(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
