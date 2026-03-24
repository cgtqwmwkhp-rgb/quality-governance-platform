import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
import { toast } from '../contexts/ToastContext'
import { Breadcrumbs } from '../components/ui/Breadcrumbs'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { trackError } from '../utils/errorTracker'
import {
  ArrowLeft,
  MessageSquare,
  User,
  Mail,
  Phone,
  Calendar,
  FileText,
  Plus,
  FlaskConical,
  CheckCircle,
  Loader2,
  ClipboardList,
  History,
  Pencil,
  Save,
  X,
  ExternalLink,
} from 'lucide-react'
import {
  complaintsApi,
  Complaint,
  ComplaintUpdate,
  Investigation,
  RunningSheetEntry,
  investigationsApi,
  actionsApi,
  Action,
  UserSearchResult,
  getApiErrorMessage,
  CreateFromRecordError,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Textarea } from '../components/ui/Textarea'
import { Input } from '../components/ui/Input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { CaseSummaryRail } from '../components/case/CaseSummaryRail'
import { SubmissionSections } from '../components/case/SubmissionSections'
import { RunningSheetPanel } from '../components/case/RunningSheetPanel'
import {
  buildComplaintSubmissionSections,
  getSubmissionPhotoSummary,
  getSubmissionSnapshot,
} from '../helpers/caseSubmission'
import { cn } from '../helpers/utils'
import { UserEmailSearch } from '../components/UserEmailSearch'

export default function ComplaintDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [complaint, setComplaint] = useState<Complaint | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState<ComplaintUpdate>({})

  const [selectedAction, setSelectedAction] = useState<Action | null>(null)
  const [showActionDetailModal, setShowActionDetailModal] = useState(false)
  const [updatingAction, setUpdatingAction] = useState(false)
  const [actionUpdateError, setActionUpdateError] = useState('')
  const [runningSheet, setRunningSheet] = useState<RunningSheetEntry[]>([])
  const [newEntry, setNewEntry] = useState('')
  const [addingEntry, setAddingEntry] = useState(false)

  // Investigation form
  const [investigationForm, setInvestigationForm] = useState({
    title: '',
    description: '',
    investigation_type: 'root_cause_analysis',
    lead_investigator: '',
  })

  // Action form
  const [actionForm, setActionForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    assigned_to: '',
  })

  useEffect(() => {
    if (id) {
      loadComplaint(parseInt(id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isEditing) navigate('/complaints')
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate, isEditing])

  const loadComplaint = async (complaintId: number) => {
    setError(null)
    try {
      const response = await complaintsApi.get(complaintId)
      setComplaint(response.data)
      setEditForm({
        title: response.data.title,
        description: response.data.description,
        complaint_type: response.data.complaint_type,
        priority: response.data.priority,
        status: response.data.status,
        complainant_name: response.data.complainant_name,
        complainant_email: response.data.complainant_email,
        complainant_phone: response.data.complainant_phone,
        resolution_summary: response.data.resolution_summary,
      })
      loadActions()
      loadInvestigations(complaintId)
      loadRunningSheet(complaintId)
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'loadComplaint' })
      setError(t('complaints.detail.load_error'))
    } finally {
      setLoading(false)
    }
  }

  const loadActions = async () => {
    if (!id) return
    try {
      // Load actions filtered by this specific Complaint
      const response = await actionsApi.list(1, 50, undefined, 'complaint', parseInt(id))
      setActions(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'loadActions' })
      setError(t('complaints.detail.load_error'))
    }
  }

  const loadInvestigations = async (complaintId: number) => {
    try {
      const response = await complaintsApi.listInvestigations(complaintId, 1, 10)
      setInvestigations(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'loadInvestigations' })
    }
  }

  const loadRunningSheet = async (complaintId: number) => {
    try {
      const response = await complaintsApi.listRunningSheet(complaintId)
      setRunningSheet(response.data)
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'loadRunningSheet' })
    }
  }

  const handleSaveEdit = async () => {
    if (!complaint) return
    setSaving(true)
    try {
      const response = await complaintsApi.update(complaint.id, editForm)
      setComplaint(response.data)
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to update complaint:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    if (complaint) {
      setEditForm({
        title: complaint.title,
        description: complaint.description,
        complaint_type: complaint.complaint_type,
        priority: complaint.priority,
        status: complaint.status,
        complainant_name: complaint.complainant_name,
        complainant_email: complaint.complainant_email,
        complainant_phone: complaint.complainant_phone,
        resolution_summary: complaint.resolution_summary,
      })
    }
    setIsEditing(false)
  }

  const handleAddEntry = async () => {
    if (!complaint || !newEntry.trim()) return
    setAddingEntry(true)
    try {
      await complaintsApi.addRunningSheetEntry(complaint.id, { content: newEntry.trim() })
      setNewEntry('')
      loadRunningSheet(complaint.id)
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'addRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setAddingEntry(false)
    }
  }

  const handleDeleteEntry = async (entryId: number) => {
    if (!complaint) return
    try {
      await complaintsApi.deleteRunningSheetEntry(complaint.id, entryId)
      loadRunningSheet(complaint.id)
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'deleteRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    }
  }

  const [investigationError, setInvestigationError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{
    id: number
    reference: string
  } | null>(null)

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!complaint) return
    setCreating(true)
    setInvestigationError('')
    setExistingInvestigation(null)

    try {
      // Use from-record endpoint with proper JSON body
      await investigationsApi.createFromRecord({
        source_type: 'complaint',
        source_id: complaint.id,
        title: investigationForm.title || `Investigation - ${complaint.reference_number}`,
      })
      setShowInvestigationModal(false)
      setInvestigationForm({
        title: '',
        description: '',
        investigation_type: 'root_cause_analysis',
        lead_investigator: '',
      })
      navigate('/investigations')
    } catch (err: any) {
      trackError(err, { component: 'ComplaintDetail', action: 'createInvestigation' })

      // Check for 409 Conflict (already exists)
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
          setInvestigationError(t('complaints.detail.investigation_exists'))
          return
        }
      }
      setInvestigationError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const handleCreateAction = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!complaint) return
    setCreating(true)
    try {
      await actionsApi.create({
        title: actionForm.title,
        description: actionForm.description || `Action for ${complaint.reference_number}`,
        priority: actionForm.priority,
        due_date: actionForm.due_date || undefined,
        action_type: 'corrective',
        source_type: 'complaint',
        source_id: complaint.id,
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
      loadActions()
    } catch (err: unknown) {
      trackError(err, { component: 'ComplaintDetail', action: 'createAction' })
      toast.error(`Failed to create action: ${getApiErrorMessage(err)}`)
    } finally {
      setCreating(false)
    }
  }

  const handleAssigneeChange = (email: string, _user?: UserSearchResult) => {
    setActionForm({ ...actionForm, assigned_to: email })
  }

  const handleInvestigatorChange = (email: string, _user?: UserSearchResult) => {
    setInvestigationForm({ ...investigationForm, lead_investigator: email })
  }

  const ACTION_STATUS_OPTIONS = [
    { value: 'open', label: 'Open', className: 'bg-blue-100 text-blue-800 hover:bg-blue-200' },
    {
      value: 'in_progress',
      label: 'In Progress',
      className: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200',
    },
    {
      value: 'pending_verification',
      label: 'Pending Verification',
      className: 'bg-purple-100 text-purple-800 hover:bg-purple-200',
    },
    {
      value: 'completed',
      label: 'Completed',
      className: 'bg-green-100 text-green-800 hover:bg-green-200',
    },
    {
      value: 'cancelled',
      label: 'Cancelled',
      className: 'bg-gray-100 text-gray-800 hover:bg-gray-200',
    },
  ]

  const handleOpenAction = (action: Action) => {
    setSelectedAction(action)
    setActionUpdateError('')
    setShowActionDetailModal(true)
  }

  const handleUpdateActionStatus = async (newStatus: string, completionNotes?: string) => {
    if (!selectedAction) return
    setUpdatingAction(true)
    setActionUpdateError('')
    try {
      const updatePayload: { status: string; completion_notes?: string } = { status: newStatus }
      if (completionNotes) updatePayload.completion_notes = completionNotes
      const response = await actionsApi.update(selectedAction.id, 'complaint', updatePayload)
      setSelectedAction(response.data)
      setActions((prev) => prev.map((a) => (a.id === selectedAction.id ? response.data : a)))
    } catch (err) {
      trackError(err, { component: 'ComplaintDetail', action: 'updateActionStatus' })
      setActionUpdateError(getApiErrorMessage(err))
    } finally {
      setUpdatingAction(false)
    }
  }

  const handleCompleteAction = () => {
    const notes = window.prompt('Enter completion notes (optional):')
    if (notes === null) return
    handleUpdateActionStatus('completed', notes.trim() || undefined)
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
      case 'closed':
      case 'resolved':
        return 'resolved'
      case 'received':
        return 'submitted'
      case 'acknowledged':
        return 'acknowledged'
      case 'under_investigation':
        return 'in-progress'
      case 'pending_response':
        return 'awaiting-user'
      case 'awaiting_customer':
        return 'awaiting-user'
      case 'escalated':
        return 'critical'
      default:
        return 'secondary'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'product':
        return '📦'
      case 'service':
        return '🛠️'
      case 'delivery':
        return '🚚'
      case 'communication':
        return '📞'
      case 'billing':
        return '💳'
      case 'staff':
        return '👤'
      case 'environmental':
        return '🌿'
      case 'safety':
        return '⚠️'
      default:
        return '📋'
    }
  }

  if (loading) {
    return <CardSkeleton count={3} />
  }

  if (error && !complaint) {
    return (
      <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
        <p className="text-sm text-destructive">{error}</p>
        <button
          onClick={() => {
            setError(null)
            loadComplaint(parseInt(id!))
          }}
          className="text-sm font-medium text-destructive hover:underline"
        >
          {t('complaints.detail.try_again')}
        </button>
      </div>
    )
  }

  if (!complaint) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <MessageSquare className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">{t('complaints.detail.not_found')}</p>
        <Button variant="outline" onClick={() => navigate('/complaints')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('complaints.back')}
        </Button>
      </div>
    )
  }

  const complaintSubmission = getSubmissionSnapshot(complaint.reporter_submission)
  const complaintSubmissionSections = buildComplaintSubmissionSections(complaintSubmission)
  const contractLabel =
    complaint.department ||
    (typeof complaintSubmission?.contract === 'string' ? complaintSubmission.contract : 'Not provided')
  const complainantRole =
    (typeof complaintSubmission?.complainant_role === 'string' &&
      complaintSubmission.complainant_role) ||
    'Not provided'
  const locationLabel =
    (typeof complaintSubmission?.location === 'string' && complaintSubmission.location) ||
    'Not provided'
  const evidenceSummary = getSubmissionPhotoSummary(complaintSubmission)
  const latestInvestigation = investigations[0]
  const investigationSummary = latestInvestigation
    ? `${latestInvestigation.reference_number || latestInvestigation.title || 'Linked investigation'}`
    : 'Not started'
  const openActions = actions.filter((action) => action.status !== 'completed' && action.status !== 'cancelled')

  return (
    <div className="space-y-6 animate-fade-in">
      <Breadcrumbs
        items={[
          { label: t('complaints.title', 'Complaints'), href: '/complaints' },
          { label: complaint?.reference_number || `#${id}` },
        ]}
      />

      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => {
              setError(null)
              loadComplaint(parseInt(id!))
            }}
            className="text-sm font-medium text-destructive hover:underline"
          >
            {t('complaints.detail.try_again')}
          </button>
        </div>
      )}
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate('/complaints')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{complaint.reference_number}</span>
              <Badge variant={getPriorityVariant(complaint.priority) as any}>
                {complaint.priority}
              </Badge>
              <Badge variant={getStatusVariant(complaint.status) as any}>
                {complaint.status.replace('_', ' ')}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">{complaint.title}</h1>
            <p className="text-muted-foreground mt-1">
              {t('complaints.detail.received_on')}{' '}
              {new Date(complaint.received_date).toLocaleDateString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={handleCancelEdit} disabled={saving}>
                <X className="w-4 h-4 mr-2" />
                {t('cancel')}
              </Button>
              <Button onClick={handleSaveEdit} disabled={saving}>
                {saving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                {t('complaints.detail.save_changes')}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                <Pencil className="w-4 h-4 mr-2" />
                {t('edit')}
              </Button>
              <Button variant="outline" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                {t('complaints.detail.add_action')}
              </Button>
              <Button onClick={() => setShowInvestigationModal(true)}>
                <FlaskConical className="w-4 h-4 mr-2" />
                {t('complaints.detail.start_investigation')}
              </Button>
            </>
          )}
        </div>
      </div>

      <CaseSummaryRail
        items={[
          { label: 'Complainant', value: complaint.complainant_name || 'Not provided', icon: <User className="w-4 h-4" /> },
          { label: 'Role', value: complainantRole, icon: <User className="w-4 h-4" /> },
          { label: 'Contract', value: contractLabel, icon: <MessageSquare className="w-4 h-4" /> },
          { label: 'Location', value: locationLabel, icon: <MessageSquare className="w-4 h-4" /> },
          {
            label: 'Received',
            value: new Date(complaint.received_date).toLocaleString(),
            icon: <Calendar className="w-4 h-4" />,
          },
          { label: 'Investigation', value: investigationSummary, icon: <FlaskConical className="w-4 h-4" /> },
          { label: 'Open actions', value: `${openActions.length} open`, icon: <ClipboardList className="w-4 h-4" /> },
          { label: 'Evidence', value: evidenceSummary, icon: <FileText className="w-4 h-4" /> },
        ]}
      />

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="w-full justify-start flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="submission">Reporter Submission</TabsTrigger>
          <TabsTrigger value="running-sheet">Running Sheet</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                {t('complaints.detail.complaint_details')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  <div>
                    <label
                      htmlFor="complaintdetail-field-0"
                      className="text-sm font-medium text-muted-foreground"
                    >
                      {t('complaints.detail.title_label')}
                    </label>
                    <Input
                      id="complaintdetail-field-0"
                      value={editForm.title || ''}
                      onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="complaintdetail-field-1"
                      className="text-sm font-medium text-muted-foreground"
                    >
                      {t('common.description')}
                    </label>
                    <Textarea
                      id="complaintdetail-field-1"
                      value={editForm.description || ''}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                      rows={4}
                      className="mt-1"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label
                        htmlFor="complaintdetail-field-2"
                        className="text-sm font-medium text-muted-foreground"
                      >
                        {t('common.type')}
                      </label>
                      <Select
                        value={editForm.complaint_type}
                        onValueChange={(value) =>
                          setEditForm({ ...editForm, complaint_type: value })
                        }
                      >
                        <SelectTrigger id="complaintdetail-field-2" className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="product">{t('complaints.type.product')}</SelectItem>
                          <SelectItem value="service">{t('complaints.type.service')}</SelectItem>
                          <SelectItem value="delivery">{t('complaints.type.delivery')}</SelectItem>
                          <SelectItem value="communication">
                            {t('complaints.type.communication')}
                          </SelectItem>
                          <SelectItem value="billing">{t('complaints.type.billing')}</SelectItem>
                          <SelectItem value="staff">{t('complaints.type.staff')}</SelectItem>
                          <SelectItem value="environmental">
                            {t('complaints.type.environmental')}
                          </SelectItem>
                          <SelectItem value="safety">{t('complaints.type.safety')}</SelectItem>
                          <SelectItem value="other">{t('complaints.type.other')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label
                        htmlFor="complaintdetail-field-3"
                        className="text-sm font-medium text-muted-foreground"
                      >
                        {t('common.priority')}
                      </label>
                      <Select
                        value={editForm.priority}
                        onValueChange={(value) => setEditForm({ ...editForm, priority: value })}
                      >
                        <SelectTrigger id="complaintdetail-field-3" className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="critical">
                            {t('complaints.priority.critical')}
                          </SelectItem>
                          <SelectItem value="high">{t('complaints.priority.high')}</SelectItem>
                          <SelectItem value="medium">{t('complaints.priority.medium')}</SelectItem>
                          <SelectItem value="low">{t('complaints.priority.low')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="col-span-2">
                      <label
                        htmlFor="complaintdetail-field-4"
                        className="text-sm font-medium text-muted-foreground"
                      >
                        {t('common.status')}
                      </label>
                      <Select
                        value={editForm.status}
                        onValueChange={(value) => setEditForm({ ...editForm, status: value })}
                      >
                        <SelectTrigger id="complaintdetail-field-4" className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="received">
                            {t('complaints.status.received')}
                          </SelectItem>
                          <SelectItem value="acknowledged">
                            {t('complaints.status.acknowledged')}
                          </SelectItem>
                          <SelectItem value="under_investigation">
                            {t('complaints.status.under_investigation')}
                          </SelectItem>
                          <SelectItem value="pending_response">
                            {t('complaints.status.pending_response')}
                          </SelectItem>
                          <SelectItem value="awaiting_customer">
                            {t('complaints.status.awaiting_customer')}
                          </SelectItem>
                          <SelectItem value="escalated">
                            {t('complaints.status.escalated')}
                          </SelectItem>
                          <SelectItem value="resolved">
                            {t('complaints.status.resolved')}
                          </SelectItem>
                          <SelectItem value="closed">{t('complaints.status.closed')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('common.description')}
                    </span>
                    <p className="mt-1 text-foreground whitespace-pre-wrap">
                      {complaint.description || t('complaints.detail.no_description')}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">
                        {t('common.type')}
                      </span>
                      <p className="mt-1 text-foreground capitalize flex items-center gap-2">
                        <span>{getTypeIcon(complaint.complaint_type)}</span>
                        {complaint.complaint_type.replace('_', ' ')}
                      </p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">
                        {t('common.priority')}
                      </span>
                      <p className="mt-1 text-foreground capitalize">{complaint.priority}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">
                        {t('common.status')}
                      </span>
                      <p className="mt-1 text-foreground capitalize">
                        {complaint.status.replace('_', ' ')}
                      </p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">
                        {t('complaints.detail.received_date')}
                      </span>
                      <p className="mt-1 text-foreground">
                        {new Date(complaint.received_date).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Complainant Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5 text-primary" />
                {t('complaints.detail.complainant_info')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label
                      htmlFor="complaintdetail-field-5"
                      className="text-sm font-medium text-muted-foreground"
                    >
                      {t('complaints.detail.name')}
                    </label>
                    <Input
                      id="complaintdetail-field-5"
                      value={editForm.complainant_name || ''}
                      onChange={(e) =>
                        setEditForm({ ...editForm, complainant_name: e.target.value })
                      }
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="complaintdetail-field-6"
                      className="text-sm font-medium text-muted-foreground"
                    >
                      {t('complaints.detail.email')}
                    </label>
                    <Input
                      id="complaintdetail-field-6"
                      type="email"
                      value={editForm.complainant_email || ''}
                      onChange={(e) =>
                        setEditForm({ ...editForm, complainant_email: e.target.value })
                      }
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="complaintdetail-field-7"
                      className="text-sm font-medium text-muted-foreground"
                    >
                      {t('complaints.detail.phone')}
                    </label>
                    <Input
                      id="complaintdetail-field-7"
                      type="tel"
                      value={editForm.complainant_phone || ''}
                      onChange={(e) =>
                        setEditForm({ ...editForm, complainant_phone: e.target.value })
                      }
                      className="mt-1"
                    />
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('complaints.detail.name')}
                    </span>
                    <p className="mt-1 text-foreground">
                      {complaint.complainant_name || t('complaints.detail.not_specified')}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('complaints.detail.email')}
                    </span>
                    <p className="mt-1 text-foreground">
                      {complaint.complainant_email || t('complaints.detail.not_specified')}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('complaints.detail.phone')}
                    </span>
                    <p className="mt-1 text-foreground">
                      {complaint.complainant_phone || t('complaints.detail.not_specified')}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Resolution */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-success" />
                {t('complaints.detail.resolution')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isEditing ? (
                <Textarea
                  value={editForm.resolution_summary || ''}
                  onChange={(e) => setEditForm({ ...editForm, resolution_summary: e.target.value })}
                  rows={4}
                  placeholder={t('complaints.detail.resolution_placeholder')}
                />
              ) : (
                <p className="text-foreground whitespace-pre-wrap">
                  {complaint.resolution_summary || t('complaints.detail.no_resolution')}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Actions Card */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-primary" />
                {t('complaints.detail.actions')} ({actions.length})
              </CardTitle>
              <Button variant="outline" size="sm" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-1" />
                {t('complaints.detail.add')}
              </Button>
            </CardHeader>
            <CardContent>
              {actions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>{t('complaints.detail.no_actions')}</p>
                  <p className="text-sm">{t('complaints.detail.no_actions_hint')}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {actions.slice(0, 5).map((action) => (
                    <div
                      key={action.id}
                      className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border cursor-pointer hover:bg-accent/50 transition-colors"
                      onClick={() => handleOpenAction(action)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          handleOpenAction(action)
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            'w-8 h-8 rounded-lg flex items-center justify-center',
                            action.status === 'completed'
                              ? 'bg-success/10 text-success'
                              : action.status === 'cancelled'
                                ? 'bg-destructive/10 text-destructive'
                                : 'bg-warning/10 text-warning',
                          )}
                        >
                          <CheckCircle className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{action.title}</p>
                          <p className="text-sm text-muted-foreground">
                            {t('complaints.detail.due')}:{' '}
                            {action.due_date
                              ? new Date(action.due_date).toLocaleDateString()
                              : t('complaints.detail.no_due_date')}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            action.status === 'completed'
                              ? 'resolved'
                              : action.status === 'cancelled'
                                ? 'destructive'
                                : action.status === 'in_progress'
                                  ? 'in-progress'
                                  : ('secondary' as any)
                          }
                        >
                          {action.status.replace(/_/g, ' ')}
                        </Badge>
                        <ExternalLink className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Quick Info */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('complaints.detail.quick_info')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Calendar className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('complaints.detail.created')}</p>
                  <p className="font-medium text-foreground">
                    {new Date(complaint.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
                  <Mail className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('complaints.detail.email')}</p>
                  <p className="font-medium text-foreground truncate">
                    {complaint.complainant_email || t('complaints.detail.not_specified')}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <Phone className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('complaints.detail.phone')}</p>
                  <p className="font-medium text-foreground">
                    {complaint.complainant_phone || t('complaints.detail.not_specified')}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
                  <User className="w-5 h-5 text-success" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Contract / Department</p>
                  <p className="font-medium text-foreground">{contractLabel}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-secondary/80 flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-foreground" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Location / Site</p>
                  <p className="font-medium text-foreground">{locationLabel}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Investigation Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-sm text-muted-foreground">Linked investigation</p>
                <p className="font-medium text-foreground">{investigationSummary}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Open actions</p>
                <p className="font-medium text-foreground">{openActions.length}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Resolution summary</p>
                <p className="font-medium text-foreground">
                  {complaint.resolution_summary || 'No resolution recorded yet'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Evidence captured</p>
                <p className="font-medium text-foreground">{evidenceSummary}</p>
              </div>
            </CardContent>
          </Card>

          {/* Timeline Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="w-4 h-4" />
                {t('complaints.detail.activity_timeline')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {t('complaints.detail.complaint_received')}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(complaint.received_date).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {t('complaints.detail.record_created')}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(complaint.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

        </TabsContent>

        <TabsContent value="submission" className="mt-6">
          <SubmissionSections
            sections={complaintSubmissionSections}
            emptyMessage="No preserved reporter submission is available for this complaint yet."
          />
        </TabsContent>

        <TabsContent value="running-sheet" className="mt-6">
          <RunningSheetPanel
            entries={runningSheet}
            newEntry={newEntry}
            addingEntry={addingEntry}
            title={t('common.running_sheet', 'Running Sheet')}
            placeholder={t('common.running_sheet_placeholder', 'Add to the story... (auto-timestamped)')}
            emptyTitle={t('common.running_sheet_empty_title', 'No entries yet')}
            emptyDescription={t(
              'complaints.detail.running_sheet_empty_description',
              'Add notes to build the complaint narrative over time',
            )}
            onNewEntryChange={setNewEntry}
            onAddEntry={handleAddEntry}
            onDeleteEntry={handleDeleteEntry}
          />
        </TabsContent>
      </Tabs>

      {/* Create Investigation Modal */}
      <Dialog
        open={showInvestigationModal}
        onOpenChange={(open) => {
          setShowInvestigationModal(open)
          if (!open) {
            setInvestigationError('')
            setExistingInvestigation(null)
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-primary" />
              {t('complaints.detail.start_investigation')}
            </DialogTitle>
            <DialogDescription>
              {t('complaints.detail.investigation_description', {
                reference: complaint.reference_number,
              })}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateInvestigation} className="space-y-4">
            <div>
              <label
                htmlFor="complaintdetail-field-8"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('complaints.detail.investigation_title')}
              </label>
              <Input
                id="complaintdetail-field-8"
                value={investigationForm.title}
                onChange={(e) =>
                  setInvestigationForm({ ...investigationForm, title: e.target.value })
                }
                placeholder={`Investigation - ${complaint.reference_number}`}
              />
            </div>
            <div>
              <label
                htmlFor="complaintdetail-field-9"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('complaints.detail.investigation_type')}
              </label>
              <Select
                value={investigationForm.investigation_type}
                onValueChange={(value) =>
                  setInvestigationForm({ ...investigationForm, investigation_type: value })
                }
              >
                <SelectTrigger id="complaintdetail-field-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="root_cause_analysis">
                    {t('complaints.investigation_type.root_cause_analysis')}
                  </SelectItem>
                  <SelectItem value="5_whys">
                    {t('complaints.investigation_type.5_whys')}
                  </SelectItem>
                  <SelectItem value="fishbone">
                    {t('complaints.investigation_type.fishbone')}
                  </SelectItem>
                  <SelectItem value="incident_review">
                    {t('complaints.investigation_type.incident_review')}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <UserEmailSearch
              label={t('complaints.detail.lead_investigator')}
              value={investigationForm.lead_investigator}
              onChange={handleInvestigatorChange}
              placeholder={t('complaints.detail.search_by_email')}
            />
            <div>
              <label
                htmlFor="complaintdetail-field-10"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('complaints.detail.initial_notes')}
              </label>
              <Textarea
                id="complaintdetail-field-10"
                value={investigationForm.description}
                onChange={(e) =>
                  setInvestigationForm({ ...investigationForm, description: e.target.value })
                }
                placeholder={t('complaints.detail.initial_notes_placeholder')}
                rows={4}
              />
            </div>

            {/* Error Message with existing investigation link */}
            {investigationError && (
              <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3">
                <p className="text-sm text-destructive">{investigationError}</p>
                {existingInvestigation && (
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    onClick={() => {
                      setShowInvestigationModal(false)
                      navigate(`/investigations/${existingInvestigation.id}`)
                    }}
                    className="mt-2 p-0 h-auto text-primary"
                  >
                    <ExternalLink className="w-3 h-3 mr-1" />
                    {t('complaints.detail.open_existing_investigation', {
                      reference: existingInvestigation.reference,
                    })}
                  </Button>
                )}
              </div>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowInvestigationModal(false)}
              >
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  t('complaints.detail.create_investigation')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Create Action Modal */}
      <Dialog open={showActionModal} onOpenChange={setShowActionModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-primary" />
              {t('complaints.detail.add_action')}
            </DialogTitle>
            <DialogDescription>{t('complaints.detail.action_description')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label
                htmlFor="complaintdetail-field-11"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('complaints.detail.action_title')}
              </label>
              <Input
                id="complaintdetail-field-11"
                value={actionForm.title}
                onChange={(e) => setActionForm({ ...actionForm, title: e.target.value })}
                placeholder={t('complaints.detail.action_title_placeholder')}
                required
              />
            </div>
            <UserEmailSearch
              label={t('complaints.detail.assign_to')}
              value={actionForm.assigned_to}
              onChange={handleAssigneeChange}
              placeholder={t('complaints.detail.search_by_email')}
              required
            />
            <div>
              <label
                htmlFor="complaintdetail-field-12"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('common.priority')}
              </label>
              <Select
                value={actionForm.priority}
                onValueChange={(value) => setActionForm({ ...actionForm, priority: value })}
              >
                <SelectTrigger id="complaintdetail-field-12">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">{t('complaints.priority.critical')}</SelectItem>
                  <SelectItem value="high">{t('complaints.priority.high')}</SelectItem>
                  <SelectItem value="medium">{t('complaints.priority.medium')}</SelectItem>
                  <SelectItem value="low">{t('complaints.priority.low')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label
                htmlFor="complaintdetail-field-13"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('common.due_date')}
              </label>
              <Input
                id="complaintdetail-field-13"
                type="date"
                value={actionForm.due_date}
                onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })}
              />
            </div>
            <div>
              <label
                htmlFor="complaintdetail-field-14"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('common.description')}
              </label>
              <Textarea
                id="complaintdetail-field-14"
                value={actionForm.description}
                onChange={(e) => setActionForm({ ...actionForm, description: e.target.value })}
                placeholder={t('complaints.detail.action_description_placeholder')}
                rows={3}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowActionModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating || !actionForm.title}>
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  t('complaints.detail.create_action')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Action Detail Modal */}
      <Dialog
        open={showActionDetailModal}
        onOpenChange={(open) => {
          setShowActionDetailModal(open)
          if (!open) {
            setSelectedAction(null)
            setActionUpdateError('')
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-primary" />
              Action Details
            </DialogTitle>
            <DialogDescription>View / Update Status</DialogDescription>
          </DialogHeader>

          {selectedAction && (
            <div className="space-y-4">
              <div className="space-y-3">
                <div>
                  <span className="text-sm font-medium text-muted-foreground">Title</span>
                  <p className="font-medium text-foreground">{selectedAction.title}</p>
                </div>

                {selectedAction.description && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('common.description')}
                    </span>
                    <p className="text-foreground">{selectedAction.description}</p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('common.status')}
                    </span>
                    <Badge
                      variant={
                        selectedAction.status === 'completed'
                          ? 'resolved'
                          : selectedAction.status === 'cancelled'
                            ? 'destructive'
                            : selectedAction.status === 'in_progress'
                              ? 'in-progress'
                              : ('secondary' as any)
                      }
                      className="mt-1"
                    >
                      {selectedAction.status.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Priority</span>
                    <p className="text-foreground capitalize">{selectedAction.priority}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Due Date</span>
                    <p className="text-foreground">
                      {selectedAction.due_date
                        ? new Date(selectedAction.due_date).toLocaleDateString()
                        : 'Not set'}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Assigned to</span>
                    <p className="text-foreground">
                      {selectedAction.assigned_to_email || 'Unassigned'}
                    </p>
                  </div>
                </div>

                {selectedAction.completed_at && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Completed at</span>
                    <p className="text-foreground">
                      {new Date(selectedAction.completed_at).toLocaleString()}
                    </p>
                  </div>
                )}

                {selectedAction.completion_notes && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      Completion Notes
                    </span>
                    <p className="text-foreground">{selectedAction.completion_notes}</p>
                  </div>
                )}
              </div>

              <div className="border-t pt-4">
                <span className="text-sm font-medium text-muted-foreground mb-2 block">
                  Update Status
                </span>
                <div className="flex flex-wrap gap-2">
                  {ACTION_STATUS_OPTIONS.map((option) => (
                    <Button
                      key={option.value}
                      size="sm"
                      variant="outline"
                      className={cn(
                        option.className,
                        selectedAction.status === option.value && 'ring-2 ring-primary',
                      )}
                      disabled={updatingAction || selectedAction.status === option.value}
                      onClick={() => {
                        if (option.value === 'completed') {
                          handleCompleteAction()
                        } else {
                          handleUpdateActionStatus(option.value)
                        }
                      }}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>

                {actionUpdateError && (
                  <p className="text-sm text-destructive mt-2">{actionUpdateError}</p>
                )}

                {updatingAction && (
                  <div className="flex items-center gap-2 mt-2 text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Updating...</span>
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setShowActionDetailModal(false)}>
                  Close
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
