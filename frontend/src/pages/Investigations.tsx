import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import {
  Plus,
  Search,
  FlaskConical,
  ArrowRight,
  GitBranch,
  CheckCircle,
  AlertTriangle,
  Car,
  MessageSquare,
  Loader2,
  ExternalLink,
  RefreshCw,
  Save,
  Layers,
  ListTodo,
  Clock,
  Eye,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  investigationsApi,
  actionsApi,
  Investigation,
  getApiErrorMessage,
  SourceRecordItem,
  CreateFromRecordError,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
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
import { UserEmailSearch } from '../components/UserEmailSearch'
import {
  getEnabledFilterOptions,
  getStatusValuesForFilter,
  statusMatchesFilter,
  type InvestigationStatusValue,
} from '../utils/investigationStatusFilter'

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
  {
    value: 'pending_verification',
    label: 'Pending Verification',
    className: 'bg-purple-100 text-purple-800',
  },
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

export const LEVEL_BADGES: Record<string, { label: string; className: string }> = {
  minimal: {
    label: 'MINIMAL',
    className: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200',
  },
  low: { label: 'LOW', className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
  medium: {
    label: 'MEDIUM',
    className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  },
  high: { label: 'HIGH', className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
}

const STATUS_BADGES: Record<string, { label: string; className: string }> = {
  draft: { label: 'Draft', className: 'bg-muted text-muted-foreground' },
  in_progress: { label: 'In progress', className: 'bg-warning/10 text-warning' },
  under_review: { label: 'Under review', className: 'bg-info/10 text-info' },
  completed: { label: 'Completed', className: 'bg-success/10 text-success' },
  closed: { label: 'Closed', className: 'bg-muted text-muted-foreground' },
}

function countSeededSections(data: Record<string, unknown> | undefined): number {
  const sections = data?.sections
  if (!sections || typeof sections !== 'object' || Array.isArray(sections)) return 0
  return Object.keys(sections as Record<string, unknown>).length
}

type HeroKey = 'total' | 'in_progress' | 'under_review' | 'completed'

const HERO_TO_STATUS_FILTER: Record<HeroKey, string> = {
  total: 'all',
  in_progress: 'in_progress',
  under_review: 'pending_review',
  completed: 'completed',
}

const ENTITY_TYPE_FILTERS = [
  { value: 'all', label: 'All sources' },
  { value: 'reporting_incident', label: 'Reporting incident' },
  { value: 'near_miss', label: 'Near miss' },
  { value: 'road_traffic_collision', label: 'Road traffic collision' },
  { value: 'complaint', label: 'Complaint' },
] as const

type EntityTypeFilter = (typeof ENTITY_TYPE_FILTERS)[number]['value']

const STATUS_FILTER_IDS = new Set(getEnabledFilterOptions().map((o) => o.id))

function parseStatusFilterParam(raw: string | null): string {
  if (raw && STATUS_FILTER_IDS.has(raw)) return raw
  return 'all'
}

function parseEntityTypeParam(raw: string | null): EntityTypeFilter {
  if (raw && ENTITY_TYPE_FILTERS.some((e) => e.value === raw)) {
    return raw as EntityTypeFilter
  }
  return 'all'
}

function heroKeyFromStatusFilter(statusFilter: string): HeroKey {
  if (statusFilter === 'in_progress') return 'in_progress'
  if (statusFilter === 'pending_review') return 'under_review'
  if (statusFilter === 'completed') return 'completed'
  return 'total'
}

/** Single backend status for API; multi-value filters (e.g. Open) omit status. */
function apiStatusForFilter(statusFilter: string): string | undefined {
  const values = getStatusValuesForFilter(statusFilter)
  if (values.length === 1) return values[0]
  return undefined
}

function collectPeopleHaystack(inv: Investigation): string {
  const data = (inv.data || {}) as Record<string, unknown>
  const keys = [
    'lead_investigator',
    'assignee_email',
    'assigned_to_email',
    'assigned_to',
    'investigator',
    'reviewer',
    'owner_email',
    'people_involved',
  ]
  const parts: string[] = []
  for (const key of keys) {
    const val = data[key]
    if (typeof val === 'string' && val.trim()) parts.push(val)
  }
  return parts.join(' ')
}

/** Local smart-search fallback (title/ref/description/people) until BE honors q for actions/comments. */
function matchesLocalSmartSearch(inv: Investigation, needle: string): boolean {
  if (!needle) return true
  const haystacks = [
    inv.title,
    inv.reference_number,
    inv.description,
    collectPeopleHaystack(inv),
  ]
  return haystacks.some((h) => (h || '').toLowerCase().includes(needle))
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
  const [existingInvestigation, setExistingInvestigation] = useState<{
    id: number
    reference: string
  } | null>(null)

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
      setSourceRecords(response.data.items ?? [])
    } catch (err) {
      trackError(err, { component: 'Investigations', action: 'loadSourceRecords' })
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
      }, 300),
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
        if (
          errorData?.error_code === 'INV_ALREADY_EXISTS' &&
          errorData.details?.existing_investigation_id
        ) {
          setExistingInvestigation({
            id: errorData.details.existing_investigation_id,
            reference:
              errorData.details.existing_reference_number ||
              `INV-${errorData.details.existing_investigation_id}`,
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
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) resetForm()
        onOpenChange(isOpen)
      }}
    >
      <DialogContent className="max-w-lg max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="w-5 h-5" />
            Create Investigation from Record
          </DialogTitle>
          <DialogDescription>
            Create a new investigation by selecting an existing record. Records that already have an
            investigation are marked.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4 overflow-y-auto max-h-[60vh]">
          {/* Source Type Selection */}
          <div>
            <span className="block text-sm font-medium text-foreground mb-2">
              Source Record Type *
            </span>
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
                        : 'border-border hover:border-primary/50',
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
              <label
                htmlFor="investigations-field-0"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Select Source Record *
              </label>
              <div className="relative mb-2">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="investigations-field-0"
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
                            : 'hover:bg-surface',
                        )}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-primary">
                              {record.reference_number}
                            </span>
                            <span
                              className={cn(
                                'px-1.5 py-0.5 text-xs rounded',
                                record.status === 'closed'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-blue-100 text-blue-800',
                              )}
                            >
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
              <label
                htmlFor="investigations-field-1"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Investigation Title *
              </label>
              <Input
                id="investigations-field-1"
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
                The investigation will be pre-populated with data from the source record using
                Mapping Contract v1. The investigation level (LOW/MEDIUM/HIGH) will be determined by
                the source severity.
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
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  /** Unfiltered catalog for hero KPI counts (not narrowed by status/q). */
  const [catalog, setCatalog] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState(() =>
    parseStatusFilterParam(searchParams.get('status')),
  )
  const [entityTypeFilter, setEntityTypeFilter] = useState<EntityTypeFilter>(() =>
    parseEntityTypeParam(searchParams.get('entityType')),
  )
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '')
  const [debouncedQ, setDebouncedQ] = useState(() => (searchParams.get('q') || '').trim())
  const [showModal, setShowModal] = useState(false)
  const [selectedInvestigation, setSelectedInvestigation] = useState<Investigation | null>(null)
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  // RCA inline editing state
  const [rcaData, setRcaData] = useState<Record<string, string>>({})
  const [rcaUnsaved, setRcaUnsaved] = useState(false)
  const [savingRca, setSavingRca] = useState(false)

  // Action detail modal state
  const [selectedAction, setSelectedAction] = useState<ActionItem | null>(null)
  const [showActionDetailModal, setShowActionDetailModal] = useState(false)
  const [updatingAction, setUpdatingAction] = useState(false)
  const [actionUpdateError, setActionUpdateError] = useState<string | null>(null)

  const heroKey = heroKeyFromStatusFilter(statusFilter)
  const statusFilterOptions = useMemo(() => getEnabledFilterOptions(), [])

  // Hydrate shareable filters from URL (back/forward + deep links).
  useEffect(() => {
    const nextStatus = parseStatusFilterParam(searchParams.get('status'))
    const nextEntity = parseEntityTypeParam(searchParams.get('entityType'))
    const nextQ = searchParams.get('q') || ''
    setStatusFilter((prev) => (prev === nextStatus ? prev : nextStatus))
    setEntityTypeFilter((prev) => (prev === nextEntity ? prev : nextEntity))
    setSearchTerm((prev) => (prev === nextQ ? prev : nextQ))
    setDebouncedQ((prev) => {
      const trimmed = nextQ.trim()
      return prev === trimmed ? prev : trimmed
    })
  }, [searchParams])

  // Write filters to URL.
  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (statusFilter === 'all') next.delete('status')
    else next.set('status', statusFilter)
    if (entityTypeFilter === 'all') next.delete('entityType')
    else next.set('entityType', entityTypeFilter)
    const q = debouncedQ.trim()
    if (!q) next.delete('q')
    else next.set('q', q)
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [statusFilter, entityTypeFilter, debouncedQ, searchParams, setSearchParams])

  // Debounce search → q (API + URL).
  useEffect(() => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    searchDebounceRef.current = setTimeout(() => {
      setDebouncedQ(searchTerm.trim())
    }, 300)
    return () => {
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    }
  }, [searchTerm])

  const loadCatalog = useCallback(async () => {
    try {
      const response = await investigationsApi.list(1, 100)
      setCatalog(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'Investigations', action: 'loadCatalog' })
      setCatalog([])
    }
  }, [])

  const loadInvestigations = useCallback(async () => {
    setLoading(true)
    try {
      const apiStatus = apiStatusForFilter(statusFilter)
      const response = await investigationsApi.list(1, 100, {
        status: apiStatus,
        entity_type: entityTypeFilter === 'all' ? undefined : entityTypeFilter,
        q: debouncedQ || undefined,
      })
      setInvestigations(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'Investigations', action: 'load' })
      setInvestigations([])
    } finally {
      setLoading(false)
    }
  }, [statusFilter, entityTypeFilter, debouncedQ])

  useEffect(() => {
    loadCatalog()
  }, [loadCatalog])

  useEffect(() => {
    loadInvestigations()
  }, [loadInvestigations])

  // Load actions and initialize RCA when investigation is selected
  useEffect(() => {
    if (selectedInvestigation) {
      loadActionsForInvestigation(selectedInvestigation)
      const data = (selectedInvestigation.data as Record<string, unknown>) || {}
      const fields: Record<string, string> = {}
      for (let i = 1; i <= 5; i++) {
        fields[`why_${i}`] = String(data[`why_${i}`] || '')
      }
      fields['root_cause'] = String(data['root_cause'] || '')
      setRcaData(fields)
      setRcaUnsaved(false)
    } else {
      setInvestigationActions([])
      setRcaData({})
      setRcaUnsaved(false)
    }
  }, [selectedInvestigation])

  const loadActionsForInvestigation = async (investigation: Investigation) => {
    setLoadingActions(true)
    try {
      // Load actions with source_type=investigation filter
      const response = await actionsApi.list(1, 50, undefined, 'investigation', investigation.id)
      setInvestigationActions(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'Investigations', action: 'loadActions' })
      setInvestigationActions([])
    } finally {
      setLoadingActions(false)
    }
  }

  const applyHeroFilter = (key: HeroKey) => {
    const next = HERO_TO_STATUS_FILTER[key]
    setStatusFilter((prev) => (prev === next && key !== 'total' ? 'all' : next))
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
        description:
          actionForm.description ||
          `Corrective action from investigation ${selectedInvestigation.reference_number}`,
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
      trackError(err, { component: 'Investigations', action: 'createAction' })
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
      setSelectedAction((prev) =>
        prev ? { ...prev, status: newStatus, completion_notes: completionNotes } : null,
      )
    } catch (err: any) {
      trackError(err, { component: 'Investigations', action: 'updateAction' })
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

  const handleRcaFieldChange = (field: string, value: string) => {
    setRcaData((prev) => ({ ...prev, [field]: value }))
    setRcaUnsaved(true)
  }

  const handleSaveRca = async () => {
    if (!selectedInvestigation) return
    setSavingRca(true)
    try {
      const existingData = (selectedInvestigation.data as Record<string, unknown>) || {}
      const mergedData = { ...existingData, ...rcaData }
      const response = await investigationsApi.update(selectedInvestigation.id, {
        data: mergedData,
      })
      setSelectedInvestigation(response.data)
      await Promise.all([loadInvestigations(), loadCatalog()])
      setRcaUnsaved(false)
    } catch (err) {
      trackError(err, { component: 'Investigations', action: 'saveRCA' })
    } finally {
      setSavingRca(false)
    }
  }

  const getEntityIcon = (type: string) => {
    return ENTITY_ICONS[type] || AlertTriangle
  }

  const filteredInvestigations = useMemo(() => {
    // Instant local UX on keystrokes; debouncedQ drives API/URL for PR-5 server search.
    const needle = searchTerm.trim().toLowerCase()
    const statusValues = getStatusValuesForFilter(statusFilter)
    const needsClientStatus =
      statusFilter !== 'all' && (statusValues.length !== 1 || !apiStatusForFilter(statusFilter))

    let rows = investigations.filter((inv) => {
      if (entityTypeFilter !== 'all' && inv.assigned_entity_type !== entityTypeFilter) {
        return false
      }
      if (needsClientStatus || statusValues.length > 1) {
        if (!statusMatchesFilter(inv.status as InvestigationStatusValue, statusFilter)) {
          return false
        }
      } else if (statusFilter !== 'all' && statusValues.length === 1) {
        // API already filtered single status; keep as safety net
        if (inv.status !== statusValues[0]) return false
      }
      return true
    })

    if (!needle) return rows

    const localFiltered = rows.filter((inv) => matchesLocalSmartSearch(inv, needle))
    if (localFiltered.length > 0) return localFiltered
    // Server narrowed via q (PR-5) with action/comment-only hits — trust API results.
    if (debouncedQ && rows.length > 0 && rows.length < catalog.length) return rows
    return []
  }, [
    investigations,
    catalog.length,
    statusFilter,
    entityTypeFilter,
    searchTerm,
    debouncedQ,
  ])

  const stats = useMemo(() => {
    const source = catalog.length > 0 ? catalog : investigations
    return {
      total: source.length,
      inProgress: source.filter((i) => i.status === 'in_progress').length,
      underReview: source.filter((i) => i.status === 'under_review').length,
      completed: source.filter((i) => i.status === 'completed').length,
    }
  }, [catalog, investigations])

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
          <h1 className="text-3xl font-bold text-foreground">{t('investigations.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('investigations.subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => navigate('/investigations/templates/builder')}
            title="Investigation report template builder"
          >
            <Layers size={20} aria-hidden="true" />
            Template Builder
          </Button>
          <Button onClick={() => setShowModal(true)}>
            <Plus size={20} aria-hidden="true" />
            {t('investigations.new')}
          </Button>
        </div>
      </div>

      {/* Interactive hero filters */}
      <div
        className="grid grid-cols-2 lg:grid-cols-4 gap-2"
        role="group"
        aria-label={t('investigations.hero_filters', 'Filter by status')}
        data-testid="investigations-hero-board"
      >
        {(
          [
            {
              key: 'total' as const,
              label: t('investigations.stats.total'),
              value: stats.total,
              icon: ListTodo,
              tone: 'primary' as const,
            },
            {
              key: 'in_progress' as const,
              label: t('status.in_progress'),
              value: stats.inProgress,
              icon: Clock,
              tone: 'warning' as const,
            },
            {
              key: 'under_review' as const,
              label: t('status.under_review'),
              value: stats.underReview,
              icon: Eye,
              tone: 'info' as const,
            },
            {
              key: 'completed' as const,
              label: t('investigations.stats.completed'),
              value: stats.completed,
              icon: CheckCircle,
              tone: 'success' as const,
            },
          ] as const
        ).map((stat) => {
          const active = heroKey === stat.key
          return (
            <button
              key={stat.key}
              type="button"
              data-testid={`investigations-hero-${stat.key}`}
              aria-pressed={active}
              onClick={() => applyHeroFilter(stat.key)}
              className={cn(
                'rounded-xl border px-3 py-2.5 text-left transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                active
                  ? 'border-primary/40 bg-primary/5 shadow-sm'
                  : 'border-border bg-card hover:bg-surface',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    'inline-flex h-7 w-7 items-center justify-center rounded-lg',
                    stat.tone === 'primary' && 'bg-primary/10 text-primary',
                    stat.tone === 'warning' && 'bg-warning/10 text-warning',
                    stat.tone === 'info' && 'bg-info/10 text-info',
                    stat.tone === 'success' && 'bg-success/10 text-success',
                  )}
                >
                  <stat.icon className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
                <span className="text-xl font-semibold tabular-nums text-foreground">
                  {stat.value}
                </span>
              </div>
              <p className="mt-1.5 text-xs font-medium text-muted-foreground">{stat.label}</p>
            </button>
          )
        })}
      </div>

      {/* Secondary filters + smart search */}
      <div className="flex flex-col lg:flex-row gap-3 lg:items-center">
        <div className="flex flex-wrap gap-2">
          <Select
            value={statusFilter}
            onValueChange={(value) => setStatusFilter(parseStatusFilterParam(value))}
          >
            <SelectTrigger
              className="w-[180px]"
              data-testid="investigations-status-filter"
              aria-label={t('investigations.filter_status', 'Status')}
            >
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {statusFilterOptions.map((opt) => (
                <SelectItem key={opt.id} value={opt.id}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={entityTypeFilter}
            onValueChange={(value) => setEntityTypeFilter(parseEntityTypeParam(value))}
          >
            <SelectTrigger
              className="w-[200px]"
              data-testid="investigations-entity-filter"
              aria-label={t('investigations.filter_source', 'Source type')}
            >
              <SelectValue placeholder="Source type" />
            </SelectTrigger>
            <SelectContent>
              {ENTITY_TYPE_FILTERS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t(
              'investigations.search_placeholder',
              'Search investigations, actions, people…',
            )}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            data-testid="investigations-smart-search"
            aria-label={t(
              'investigations.smart_search',
              'Search investigations, actions, people',
            )}
          />
        </div>
      </div>

      {/* Compact investigation work queue — report opens on the detail route */}
      <div className="space-y-2" data-testid="investigations-list">
        {filteredInvestigations.length === 0 ? (
          <EmptyState
            icon={<FlaskConical className="w-8 h-8 text-muted-foreground" />}
            title={t('investigations.empty.title')}
            description="Start an investigation report from an incident, RTA, near miss, or complaint."
          />
        ) : (
          filteredInvestigations.map((investigation) => {
            const EntityIcon = getEntityIcon(investigation.assigned_entity_type)
            const levelKey = String(investigation.level || '').toLowerCase()
            const levelBadge = LEVEL_BADGES[levelKey]
            const statusBadge =
              STATUS_BADGES[investigation.status] || STATUS_BADGES.draft
            const sectionCount = countSeededSections(
              investigation.data as Record<string, unknown> | undefined,
            )

            return (
              <Card
                key={investigation.id}
                hoverable
                data-testid="investigation-row"
                onClick={() => navigate(`/investigations/${investigation.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/investigations/${investigation.id}`)
                  }
                }}
                className="px-4 py-3 cursor-pointer"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <EntityIcon className="w-4 h-4 text-primary" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-0.5">
                      <span className="font-mono text-xs text-primary">
                        {investigation.reference_number}
                      </span>
                      <span className="px-1.5 py-0.5 text-[11px] font-medium rounded bg-surface text-muted-foreground capitalize">
                        {investigation.assigned_entity_type.replace(/_/g, ' ')}
                      </span>
                      {levelBadge ? (
                        <span
                          className={cn(
                            'px-1.5 py-0.5 text-[11px] font-semibold rounded',
                            levelBadge.className,
                          )}
                          data-testid="investigation-level-badge"
                        >
                          {levelBadge.label}
                        </span>
                      ) : null}
                      <span
                        className={cn(
                          'px-1.5 py-0.5 text-[11px] font-medium rounded',
                          statusBadge.className,
                        )}
                      >
                        {statusBadge.label}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-foreground truncate">
                      {investigation.title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {sectionCount > 0
                        ? `${sectionCount} report section${sectionCount === 1 ? '' : 's'} seeded`
                        : 'Open report to continue investigation'}
                    </p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground flex-shrink-0" aria-hidden="true" />
                </div>
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
                <span className="font-mono text-sm text-primary">
                  {selectedInvestigation.reference_number}
                </span>
                <DialogTitle>{selectedInvestigation.title}</DialogTitle>
                <DialogDescription>
                  Root cause investigation for{' '}
                  {selectedInvestigation.assigned_entity_type.replace(/_/g, ' ')} record. Status:{' '}
                  {selectedInvestigation.status.replace(/_/g, ' ')}.
                </DialogDescription>
              </DialogHeader>
              <div className="overflow-y-auto max-h-[calc(90vh-120px)] space-y-6 py-4">
                {/* 5 Whys Analysis */}
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <GitBranch className="w-5 h-5 text-primary" />
                      {t('investigations.five_whys')}
                    </h3>
                    <Button
                      size="sm"
                      onClick={handleSaveRca}
                      disabled={savingRca || !rcaUnsaved}
                      className={cn(!rcaUnsaved && 'opacity-50')}
                    >
                      {savingRca ? (
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4 mr-1" />
                      )}
                      {rcaUnsaved ? 'Save RCA' : 'Saved'}
                    </Button>
                  </div>
                  <div className="space-y-4">
                    {[1, 2, 3, 4, 5].map((num) => (
                      <div key={num} className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0 font-bold text-primary-foreground">
                          {num}
                        </div>
                        <div className="flex-1">
                          <label
                            htmlFor={`investigations-why-${num}`}
                            className="block text-sm font-medium text-foreground mb-2"
                          >
                            Why {num}?
                          </label>
                          <Textarea
                            id={`investigations-why-${num}`}
                            rows={2}
                            placeholder={`Enter the ${num === 1 ? 'initial' : 'deeper'} cause...`}
                            value={rcaData[`why_${num}`] || ''}
                            onChange={(e) => handleRcaFieldChange(`why_${num}`, e.target.value)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Root Cause */}
                <Card className="p-6 border-primary/20 bg-primary/5">
                  <h3 className="text-lg font-semibold text-foreground mb-4">
                    {t('investigations.root_cause')}
                  </h3>
                  <Textarea
                    rows={3}
                    placeholder="Document the root cause based on your 5 Whys analysis..."
                    value={rcaData['root_cause'] || ''}
                    onChange={(e) => handleRcaFieldChange('root_cause', e.target.value)}
                  />
                </Card>

                {/* Corrective Actions */}
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-4">
                    {t('investigations.corrective_actions')}
                  </h3>

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
                              <p className="text-sm text-muted-foreground line-clamp-2">
                                {action.description}
                              </p>
                              {action.owner_email && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  Assigned to:{' '}
                                  <span className="text-foreground">{action.owner_email}</span>
                                </p>
                              )}
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <span
                                className={cn(
                                  'px-2 py-0.5 text-xs font-medium rounded',
                                  action.status === 'open' && 'bg-warning/10 text-warning',
                                  action.status === 'in_progress' && 'bg-info/10 text-info',
                                  action.status === 'pending_verification' &&
                                    'bg-purple-100 text-purple-800',
                                  action.status === 'completed' && 'bg-success/10 text-success',
                                  action.status === 'cancelled' && 'bg-muted text-muted-foreground',
                                )}
                              >
                                {action.status.replace(/_/g, ' ')}
                              </span>
                              <span
                                className={cn(
                                  'px-2 py-0.5 text-xs font-medium rounded',
                                  action.priority === 'critical' &&
                                    'bg-destructive/10 text-destructive',
                                  action.priority === 'high' && 'bg-warning/10 text-warning',
                                  action.priority === 'medium' && 'bg-info/10 text-info',
                                  action.priority === 'low' && 'bg-muted text-muted-foreground',
                                )}
                              >
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

                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => setShowActionModal(true)}
                  >
                    <Plus className="w-5 h-5" />
                    {t('investigations.add_action')}
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
          void loadInvestigations()
          void loadCatalog()
          setShowModal(false)
        }}
      />

      {/* Add Action Modal */}
      <Dialog open={showActionModal} onOpenChange={setShowActionModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('investigations.add_action')}</DialogTitle>
            <DialogDescription>{t('investigations.add_action_desc')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label
                htmlFor="investigations-field-3"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Action Title *
              </label>
              <Input
                id="investigations-field-3"
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
              <label
                htmlFor="investigations-field-4"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Priority
              </label>
              <Select
                value={actionForm.priority}
                onValueChange={(value) => setActionForm({ ...actionForm, priority: value })}
              >
                <SelectTrigger id="investigations-field-4">
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
                htmlFor="investigations-field-5"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Due Date
              </label>
              <Input
                id="investigations-field-5"
                type="date"
                value={actionForm.due_date}
                onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })}
              />
            </div>
            <div>
              <label
                htmlFor="investigations-field-6"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Description
              </label>
              <Textarea
                id="investigations-field-6"
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
                  <span className="block text-sm font-medium text-muted-foreground mb-1">
                    Status
                  </span>
                  <span
                    className={cn(
                      'inline-block px-3 py-1 text-sm font-medium rounded',
                      selectedAction.status === 'open' && 'bg-warning/10 text-warning',
                      selectedAction.status === 'in_progress' && 'bg-info/10 text-info',
                      selectedAction.status === 'pending_verification' &&
                        'bg-purple-100 text-purple-800',
                      selectedAction.status === 'completed' && 'bg-success/10 text-success',
                      selectedAction.status === 'cancelled' && 'bg-muted text-muted-foreground',
                    )}
                  >
                    {selectedAction.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="flex-1">
                  <span className="block text-sm font-medium text-muted-foreground mb-1">
                    Priority
                  </span>
                  <span
                    className={cn(
                      'inline-block px-3 py-1 text-sm font-medium rounded',
                      selectedAction.priority === 'critical' &&
                        'bg-destructive/10 text-destructive',
                      selectedAction.priority === 'high' && 'bg-warning/10 text-warning',
                      selectedAction.priority === 'medium' && 'bg-info/10 text-info',
                      selectedAction.priority === 'low' && 'bg-muted text-muted-foreground',
                    )}
                  >
                    {selectedAction.priority}
                  </span>
                </div>
              </div>

              {/* Assignee and Due Date */}
              <div className="flex gap-4">
                {selectedAction.owner_email && (
                  <div className="flex-1">
                    <span className="block text-sm font-medium text-muted-foreground mb-1">
                      Assigned To
                    </span>
                    <span className="text-sm text-foreground">{selectedAction.owner_email}</span>
                  </div>
                )}
                {selectedAction.due_date && (
                  <div className="flex-1">
                    <span className="block text-sm font-medium text-muted-foreground mb-1">
                      Due Date
                    </span>
                    <span className="text-sm text-foreground">
                      {new Date(selectedAction.due_date).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              {/* Completion Notes */}
              {selectedAction.completion_notes && (
                <div>
                  <span className="block text-sm font-medium text-muted-foreground mb-1">
                    Completion Notes
                  </span>
                  <p className="text-sm text-foreground bg-muted/50 p-2 rounded">
                    {selectedAction.completion_notes}
                  </p>
                </div>
              )}

              {/* Status Update Section */}
              <div className="border-t pt-4">
                <span className="block text-sm font-medium text-foreground mb-2">
                  Update Status
                </span>
                <div className="flex flex-wrap gap-2">
                  {ACTION_STATUS_OPTIONS.map((option) => (
                    <Button
                      key={option.value}
                      type="button"
                      variant={selectedAction.status === option.value ? 'default' : 'outline'}
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
