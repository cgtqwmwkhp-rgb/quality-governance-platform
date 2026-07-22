import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from '../contexts/ToastContext'
import { Breadcrumbs } from '../components/ui/Breadcrumbs'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { StandardsAssessmentPanel } from '../components/StandardsAssessmentPanel'
import { resolveIncidentDetailTab } from './incidentStandardsTab'
import { displayIncidentText } from './incidentTextDisplay'
import {
  ArrowLeft,
  AlertTriangle,
  User,
  MapPin,
  Calendar,
  FileText,
  Plus,
  FlaskConical,
  CheckCircle,
  Loader2,
  ClipboardList,
  Pencil,
  Save,
  X,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react'
import {
  incidentsApi,
  Incident,
  IncidentUpdate,
  Investigation,
  RunningSheetEntry,
  investigationsApi,
  actionsApi,
  Action,
  EvidenceAsset,
  evidenceAssetsApi,
  getApiErrorMessage,
  CreateFromRecordError,
  lookupsApi,
} from '../api/client'
import { trackError } from '../utils/errorTracker'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
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
import { EvidenceGallery } from '../components/EvidenceGallery'
import { SubmissionSections } from '../components/case/SubmissionSections'
import {
  RunningSheetPanel,
  buildRunningSheetCreateActionHref,
} from '../components/case/RunningSheetPanel'
import {
  buildIncidentSubmissionSections,
  getSubmissionPhotoSummary,
  getSubmissionSnapshot,
} from '../helpers/caseSubmission'
import { cn } from '../helpers/utils'
import { EngineerPeoplePicker } from '../components/EngineerPeoplePicker'
import { AssetPicker } from '../components/AssetPicker'
import { getCapaHandoffLabelKey, getCapaLink } from '../components/investigations/handoffLinks'
import { parseLinkedRiskIds, riskRegisterHref, severityAllowsRaiseRisk } from './incidentRiskLinks'
import { mergeLookupSelectOptions } from './admin/lookupSelectOptions'

// Status options for action updates
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

export default function IncidentDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const defaultTab = resolveIncidentDetailTab(searchParams.get('tab'))
  const [incident, setIncident] = useState<Incident | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [actionsLoading, setActionsLoading] = useState(false)
  const [actionsLoadFailed, setActionsLoadFailed] = useState(false)
  const [evidenceAssets, setEvidenceAssets] = useState<EvidenceAsset[]>([])
  const [evidenceLoading, setEvidenceLoading] = useState(false)
  const [evidenceLoadFailed, setEvidenceLoadFailed] = useState(false)
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState<IncidentUpdate>({})
  const defaultTypeOptions = [
    { value: 'injury', label: t('incidents.type.injury') },
    { value: 'near_miss', label: t('incidents.type.near_miss') },
    { value: 'hazard', label: t('incidents.type.hazard') },
    { value: 'property_damage', label: t('incidents.type.property_damage') },
    { value: 'environmental', label: t('incidents.type.environmental') },
    { value: 'security', label: t('incidents.type.security') },
    { value: 'quality', label: t('incidents.type.quality') },
    { value: 'other', label: t('incidents.type.other') },
  ]
  const defaultSeverityOptions = [
    { value: 'critical', label: t('severity.critical') },
    { value: 'high', label: t('severity.high') },
    { value: 'medium', label: t('severity.medium') },
    { value: 'low', label: t('severity.low') },
    { value: 'negligible', label: t('severity.negligible') },
  ]
  const [typeOptions, setTypeOptions] = useState(defaultTypeOptions)
  const [severityOptions, setSeverityOptions] = useState(defaultSeverityOptions)

  // Action detail modal state
  const [selectedAction, setSelectedAction] = useState<Action | null>(null)
  const [showActionDetailModal, setShowActionDetailModal] = useState(false)
  const [updatingAction, setUpdatingAction] = useState(false)
  const [actionUpdateError, setActionUpdateError] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [runningSheet, setRunningSheet] = useState<RunningSheetEntry[]>([])
  const [newEntry, setNewEntry] = useState('')
  const [addingEntry, setAddingEntry] = useState(false)
  const [raisingRisk, setRaisingRisk] = useState(false)

  // Completion dialog state
  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completionNotes, setCompletionNotes] = useState('')

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
      loadIncident(parseInt(id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isEditing) navigate('/incidents')
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate, isEditing])

  useEffect(() => {
    if (!isEditing) return
    let cancelled = false
    setTypeOptions(defaultTypeOptions)
    setSeverityOptions(defaultSeverityOptions)
    void Promise.all([
      lookupsApi.list('incident_types', true).catch(() => ({ items: [], total: 0 })),
      lookupsApi.list('severity_levels', true).catch(() => ({ items: [], total: 0 })),
    ]).then(([typesRes, severityRes]) => {
      if (!cancelled) {
        setTypeOptions(mergeLookupSelectOptions(defaultTypeOptions, typesRes.items))
        setSeverityOptions(mergeLookupSelectOptions(defaultSeverityOptions, severityRes.items))
      }
    })
    return () => {
      cancelled = true
    }
    // Intentional: lookup labels load when editing opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing])

  const loadIncident = async (incidentId: number) => {
    setError(null)
    try {
      const response = await incidentsApi.get(incidentId)
      setIncident(response.data)
      setEditForm({
        title: displayIncidentText(response.data.title),
        description: displayIncidentText(response.data.description),
        incident_type: response.data.incident_type,
        severity: response.data.severity,
        status: response.data.status,
        location: response.data.location,
        department: response.data.department,
        asset_id: response.data.asset_id ?? null,
      })
      loadActions()
      loadEvidence(incidentId)
      loadInvestigations(incidentId)
      loadRunningSheet(incidentId)
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'loadIncident' })
      setError(t('incidents.detail.failed_to_load'))
    } finally {
      setLoading(false)
    }
  }

  const loadActions = async () => {
    if (!id) return
    setActionsLoading(true)
    setActionsLoadFailed(false)
    try {
      const response = await actionsApi.list(1, 50, undefined, 'incident', parseInt(id))
      setActions(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'loadActions' })
      setActions([])
      setActionsLoadFailed(true)
      toast.error(
        t(
          'incidents.detail.actions_unavailable',
          'CAPA actions could not be loaded — counts may be incomplete.',
        ),
      )
    } finally {
      setActionsLoading(false)
    }
  }

  const loadEvidence = async (incidentId: number) => {
    setEvidenceLoading(true)
    setEvidenceLoadFailed(false)
    try {
      const response = await evidenceAssetsApi.list({
        source_module: 'incident',
        source_id: incidentId,
        page_size: 50,
      })
      setEvidenceAssets(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'loadEvidence' })
      setEvidenceAssets([])
      setEvidenceLoadFailed(true)
    } finally {
      setEvidenceLoading(false)
    }
  }

  const loadInvestigations = async (incidentId: number) => {
    try {
      const response = await incidentsApi.listInvestigations(incidentId, 1, 10)
      setInvestigations(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'loadInvestigations' })
    }
  }

  const loadRunningSheet = async (incidentId: number) => {
    try {
      const response = await incidentsApi.listRunningSheet(incidentId)
      setRunningSheet(response.data)
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'loadRunningSheet' })
    }
  }

  const handleSaveEdit = async () => {
    if (!incident) return
    setSaving(true)
    try {
      // Omit unchanged status so no-op edits never hit transition validation.
      const payload: IncidentUpdate = { ...editForm }
      if (payload.status === incident.status) {
        delete payload.status
      }
      const response = await incidentsApi.update(incident.id, payload)
      setIncident(response.data)
      setEditForm({
        title: displayIncidentText(response.data.title),
        description: displayIncidentText(response.data.description),
        incident_type: response.data.incident_type,
        severity: response.data.severity,
        status: response.data.status,
        location: response.data.location,
        department: response.data.department,
        asset_id: response.data.asset_id ?? null,
      })
      setIsEditing(false)
      toast.success(t('incidents.detail.save_success', 'Incident updated'))
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'updateIncident' })
      toast.error(
        getApiErrorMessage(err, t('incidents.detail.save_failed', 'Could not save incident')),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    if (incident) {
      setEditForm({
        title: displayIncidentText(incident.title),
        description: displayIncidentText(incident.description),
        incident_type: incident.incident_type,
        severity: incident.severity,
        status: incident.status,
        location: incident.location,
        department: incident.department,
        asset_id: incident.asset_id ?? null,
      })
    }
    setIsEditing(false)
  }

  const handleAddEntry = async () => {
    if (!incident || !newEntry.trim()) return
    setAddingEntry(true)
    try {
      await incidentsApi.addRunningSheetEntry(incident.id, { content: newEntry.trim() })
      setNewEntry('')
      loadRunningSheet(incident.id)
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'addRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setAddingEntry(false)
    }
  }

  const handleDeleteEntry = async (entryId: number) => {
    if (!incident) return
    try {
      await incidentsApi.deleteRunningSheetEntry(incident.id, entryId)
      loadRunningSheet(incident.id)
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'deleteRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    }
  }

  const handleRaiseRisk = async () => {
    if (!incident) return
    setRaisingRisk(true)
    try {
      const response = await incidentsApi.raiseRisk(incident.id)
      setIncident({
        ...incident,
        linked_risk_ids: response.data.linked_risk_ids,
      })
      toast.success(`Risk ${response.data.risk.reference_number} raised and linked`)
      navigate(response.data.risk_register_href)
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'raiseRisk' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setRaisingRisk(false)
    }
  }

  const [investigationError, setInvestigationError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{
    id: number
    reference: string
  } | null>(null)

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!incident) return
    setCreating(true)
    setInvestigationError('')
    setExistingInvestigation(null)

    try {
      // Use from-record endpoint with proper JSON body
      const response = await investigationsApi.createFromRecord({
        source_type: 'reporting_incident',
        source_id: incident.id,
        title: investigationForm.title || `Investigation - ${incident.reference_number}`,
      })
      setShowInvestigationModal(false)
      setInvestigationForm({
        title: '',
        description: '',
        investigation_type: 'root_cause_analysis',
        lead_investigator: '',
      })
      navigate(`/investigations/${response.data.id}`)
    } catch (err: any) {
      trackError(err, { component: 'IncidentDetail', action: 'createInvestigation' })

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
          setInvestigationError(t('incidents.detail.existing_investigation'))
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
    if (!incident) return
    setCreating(true)
    try {
      await actionsApi.create({
        title: actionForm.title,
        description: actionForm.description || `Action for ${incident.reference_number}`,
        priority: actionForm.priority,
        due_date: actionForm.due_date || undefined,
        action_type: 'corrective',
        source_type: 'incident',
        source_id: incident.id,
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
      trackError(err, { component: 'IncidentDetail', action: 'createAction' })
      toast.error(t('incidents.detail.failed_to_create_action', { error: getApiErrorMessage(err) }))
    } finally {
      setCreating(false)
    }
  }

  // Action detail handlers
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
      if (completionNotes) {
        updatePayload.completion_notes = completionNotes
      }

      const response = await actionsApi.update(selectedAction.id, 'incident', updatePayload)

      // Update local state
      setSelectedAction(response.data)
      setActions((prev) => prev.map((a) => (a.id === selectedAction.id ? response.data : a)))
    } catch (err) {
      trackError(err, { component: 'IncidentDetail', action: 'updateActionStatus' })
      setActionUpdateError(getApiErrorMessage(err))
    } finally {
      setUpdatingAction(false)
    }
  }

  const handleCompleteAction = () => {
    setCompletionNotes('')
    setShowCompletionDialog(true)
  }

  const confirmCompleteAction = () => {
    handleUpdateActionStatus('completed', completionNotes || undefined)
    setShowCompletionDialog(false)
    setCompletionNotes('')
  }

  const getSeverityVariant = (severity: string): BadgeVariant => {
    switch (severity) {
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

  const getStatusVariant = (status: string): BadgeVariant => {
    switch (status) {
      case 'open':
        return 'destructive'
      case 'under_investigation':
        return 'in-progress'
      case 'pending_actions':
        return 'acknowledged'
      case 'closed':
        return 'resolved'
      default:
        return 'secondary'
    }
  }

  if (loading) {
    return <CardSkeleton count={3} />
  }

  if (!incident) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">{t('incidents.detail.not_found')}</p>
        <Button variant="outline" onClick={() => navigate('/incidents')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('incidents.back')}
        </Button>
      </div>
    )
  }

  const incidentSubmission = getSubmissionSnapshot(incident.reporter_submission)
  const incidentSubmissionSections = buildIncidentSubmissionSections(incidentSubmission)
  const affectedPerson =
    (typeof incidentSubmission?.person_name === 'string' && incidentSubmission.person_name) ||
    incident.people_involved ||
    'Not provided'
  const contractLabel =
    incident.department ||
    (typeof incidentSubmission?.contract === 'string'
      ? incidentSubmission.contract
      : 'Not provided')
  const personRole =
    (typeof incidentSubmission?.person_role === 'string' && incidentSubmission.person_role) ||
    'Not provided'
  const medicalAssistance =
    (typeof incidentSubmission?.medical_assistance === 'string' &&
      incidentSubmission.medical_assistance) ||
    (incident.emergency_services_called
      ? 'Emergency services called'
      : incident.first_aid_given
        ? 'First aid provided'
        : 'Not provided')
  const evidenceSummary = getSubmissionPhotoSummary(incidentSubmission)
  const surfacedEvidenceSummary = evidenceLoading
    ? 'Loading evidence…'
    : evidenceLoadFailed
      ? `${evidenceSummary} (evidence assets unavailable)`
      : evidenceAssets.length > 0
        ? `${evidenceAssets.length} evidence asset${evidenceAssets.length === 1 ? '' : 's'}`
        : evidenceSummary
  const latestInvestigation = investigations[0]
  const investigationSummary = latestInvestigation
    ? `${latestInvestigation.reference_number || latestInvestigation.title || 'Linked investigation'}`
    : 'Not started'
  const openActions = actions.filter(
    (action) => action.status !== 'completed' && action.status !== 'cancelled',
  )
  const investigationHref = latestInvestigation ? `/investigations/${latestInvestigation.id}` : null
  const capaHref = getCapaLink('incident', incident.id)
  const capaCountLabel = actionsLoading ? '…' : actionsLoadFailed ? '—' : String(actions.length)
  const openActionsLabel = actionsLoading
    ? '…'
    : actionsLoadFailed
      ? '—'
      : `${openActions.length} open`
  const canRaiseRisk = severityAllowsRaiseRisk(incident.severity)

  return (
    <div className="space-y-6 animate-fade-in">
      <Breadcrumbs
        items={[
          { label: t('incidents.title', 'Incidents'), href: '/incidents' },
          { label: incident?.reference_number || `#${id}` },
        ]}
      />

      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => {
              setError(null)
              if (id) loadIncident(parseInt(id))
            }}
            className="text-sm font-medium text-destructive hover:underline"
          >
            {t('incidents.detail.try_again')}
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate('/incidents')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{incident.reference_number}</span>
              <Badge variant={getSeverityVariant(incident.severity)}>{incident.severity}</Badge>
              <Badge variant={getStatusVariant(incident.status)}>
                {incident.status.replace('_', ' ')}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              {displayIncidentText(incident.title)}
            </h1>
            <p className="text-muted-foreground mt-1">
              {t('incidents.detail.reported_on', {
                date: new Date(incident.reported_date).toLocaleDateString(),
              })}
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
                {t('incidents.detail.save_changes')}
              </Button>
            </>
          ) : (
            <>
              {canRaiseRisk && (
                <Button
                  variant="outline"
                  onClick={() => void handleRaiseRisk()}
                  disabled={raisingRisk}
                  data-testid="incident-raise-risk"
                >
                  <ShieldAlert className="w-4 h-4 mr-2" />
                  {raisingRisk ? 'Raising…' : 'Raise risk'}
                </Button>
              )}
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                <Pencil className="w-4 h-4 mr-2" />
                {t('edit')}
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate(capaHref)}
                disabled={actionsLoading}
              >
                <ClipboardList className="w-4 h-4 mr-2" />
                {t(getCapaHandoffLabelKey('incident', actionsLoadFailed ? 0 : actions.length), {
                  count: actions.length,
                })}
              </Button>
              <Button
                onClick={() =>
                  investigationHref ? navigate(investigationHref) : setShowInvestigationModal(true)
                }
              >
                <FlaskConical className="w-4 h-4 mr-2" />
                {investigationHref
                  ? t('incidents.detail.open_investigation')
                  : t('incidents.detail.start_investigation')}
              </Button>
            </>
          )}
        </div>
      </div>

      <CaseSummaryRail
        items={[
          {
            label: 'Reporter',
            value: incident.reporter_name || 'Not provided',
            icon: <User className="w-4 h-4" />,
          },
          { label: 'Affected person', value: affectedPerson, icon: <User className="w-4 h-4" /> },
          {
            label: 'Occurred at',
            value: new Date(incident.incident_date).toLocaleString(),
            icon: <Calendar className="w-4 h-4" />,
          },
          {
            label: 'Location',
            value: incident.location || 'Not specified',
            icon: <MapPin className="w-4 h-4" />,
          },
          {
            label: 'Evidence',
            value: surfacedEvidenceSummary,
            icon: <FileText className="w-4 h-4" />,
          },
          {
            label: 'Investigation',
            value: investigationSummary,
            icon: <FlaskConical className="w-4 h-4" />,
          },
          {
            label: 'Open actions',
            value: openActionsLabel,
            icon: <ClipboardList className="w-4 h-4" />,
          },
          {
            label: 'Medical response',
            value: medicalAssistance,
            icon: <AlertTriangle className="w-4 h-4" />,
          },
          {
            label: 'Linked risks',
            value: `${parseLinkedRiskIds(incident.linked_risk_ids).length}`,
            icon: <ShieldAlert className="w-4 h-4" />,
          },
        ]}
      />

      <Tabs defaultValue={defaultTab} key={defaultTab} className="w-full">
        <TabsList className="w-full justify-start flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="standards">Standards</TabsTrigger>
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
                    {t('incidents.detail.incident_details')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {isEditing ? (
                    <>
                      <div>
                        <label
                          htmlFor="incidentdetail-field-0"
                          className="text-sm font-medium text-muted-foreground"
                        >
                          {t('incidents.detail.title')}
                        </label>
                        <Input
                          id="incidentdetail-field-0"
                          value={editForm.title || ''}
                          onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <label
                          htmlFor="incidentdetail-field-1"
                          className="text-sm font-medium text-muted-foreground"
                        >
                          {t('common.description')}
                        </label>
                        <Textarea
                          id="incidentdetail-field-1"
                          value={editForm.description || ''}
                          onChange={(e) =>
                            setEditForm({ ...editForm, description: e.target.value })
                          }
                          rows={4}
                          className="mt-1"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label
                            htmlFor="incidentdetail-field-2"
                            className="text-sm font-medium text-muted-foreground"
                          >
                            {t('incidents.detail.incident_type')}
                          </label>
                          <Select
                            value={editForm.incident_type}
                            onValueChange={(value) =>
                              setEditForm({ ...editForm, incident_type: value })
                            }
                          >
                            <SelectTrigger id="incidentdetail-field-2" className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {typeOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label
                            htmlFor="incidentdetail-field-3"
                            className="text-sm font-medium text-muted-foreground"
                          >
                            {t('incidents.detail.severity')}
                          </label>
                          <Select
                            value={editForm.severity}
                            onValueChange={(value) => setEditForm({ ...editForm, severity: value })}
                          >
                            <SelectTrigger id="incidentdetail-field-3" className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {severityOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label
                            htmlFor="incidentdetail-field-4"
                            className="text-sm font-medium text-muted-foreground"
                          >
                            {t('common.status')}
                          </label>
                          <Select
                            value={editForm.status}
                            onValueChange={(value) => setEditForm({ ...editForm, status: value })}
                          >
                            <SelectTrigger id="incidentdetail-field-4" className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="reported">
                                {t('incidents.detail.status_reported', 'Reported')}
                              </SelectItem>
                              <SelectItem value="under_investigation">
                                {t('incidents.detail.status_under_investigation')}
                              </SelectItem>
                              <SelectItem value="pending_actions">
                                {t('incidents.detail.status_pending_actions')}
                              </SelectItem>
                              <SelectItem value="actions_in_progress">
                                {t(
                                  'incidents.detail.status_actions_in_progress',
                                  'Actions in progress',
                                )}
                              </SelectItem>
                              <SelectItem value="pending_review">
                                {t('incidents.detail.status_pending_review', 'Pending review')}
                              </SelectItem>
                              <SelectItem value="closed">
                                {t('incidents.detail.status_closed')}
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label
                            htmlFor="incidentdetail-field-5"
                            className="text-sm font-medium text-muted-foreground"
                          >
                            {t('common.location')}
                          </label>
                          <Input
                            id="incidentdetail-field-5"
                            value={editForm.location || ''}
                            onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                            className="mt-1"
                          />
                        </div>
                      </div>
                      <div className="mt-4">
                        <AssetPicker
                          value={editForm.asset_id}
                          onChange={(assetId) => setEditForm({ ...editForm, asset_id: assetId })}
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <span className="text-sm font-medium text-muted-foreground">
                          {t('common.description')}
                        </span>
                        <p className="mt-1 text-foreground whitespace-pre-wrap">
                          {displayIncidentText(incident.description) ||
                            t('incidents.detail.no_description')}
                        </p>
                      </div>
                      {incident.asset_id != null && (
                        <div className="mt-3">
                          <span className="text-sm font-medium text-muted-foreground">
                            Linked asset
                          </span>
                          <p className="mt-1 text-foreground">Asset #{incident.asset_id}</p>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <span className="text-sm font-medium text-muted-foreground">
                            {t('incidents.detail.incident_type')}
                          </span>
                          <p className="mt-1 text-foreground capitalize">
                            {incident.incident_type.replace('_', ' ')}
                          </p>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-muted-foreground">
                            {t('incidents.detail.severity')}
                          </span>
                          <p className="mt-1 text-foreground capitalize">{incident.severity}</p>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-muted-foreground">
                            {t('incidents.detail.incident_date')}
                          </span>
                          <p className="mt-1 text-foreground">
                            {new Date(incident.incident_date).toLocaleString()}
                          </p>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-muted-foreground">
                            {t('common.location')}
                          </span>
                          <p className="mt-1 text-foreground">
                            {incident.location || t('incidents.detail.not_specified')}
                          </p>
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Actions Card */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <ClipboardList className="w-5 h-5 text-primary" />
                    {t('incidents.detail.actions_count', { count: actions.length })}
                  </CardTitle>
                  <Button variant="outline" size="sm" onClick={() => setShowActionModal(true)}>
                    <Plus className="w-4 h-4 mr-1" />
                    {t('incidents.detail.add')}
                  </Button>
                </CardHeader>
                <CardContent>
                  {actions.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>{t('incidents.detail.no_actions')}</p>
                      <p className="text-sm">{t('incidents.detail.no_actions_hint')}</p>
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
                                {action.due_date
                                  ? t('incidents.detail.due_date_value', {
                                      date: new Date(action.due_date).toLocaleDateString(),
                                    })
                                  : t('incidents.detail.no_due_date')}
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
                                      : 'secondary'
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

            {/* Right Column - Timeline & Quick Actions */}
            <div className="space-y-6">
              {/* Quick Info Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('incidents.detail.quick_info')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Calendar className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">
                        {t('incidents.detail.created')}
                      </p>
                      <p className="font-medium text-foreground">
                        {new Date(incident.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
                      <MapPin className="w-5 h-5 text-info" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('common.location')}</p>
                      <p className="font-medium text-foreground">
                        {incident.location || t('incidents.detail.not_specified')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                      <User className="w-5 h-5 text-warning" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Contract / Department</p>
                      <p className="font-medium text-foreground">{contractLabel}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
                      <User className="w-5 h-5 text-success" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Reporter</p>
                      <p className="font-medium text-foreground">
                        {incident.reporter_name || t('incidents.detail.not_specified')}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {incident.reporter_email || 'No reporter email captured'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center">
                      <AlertTriangle className="w-5 h-5 text-destructive" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Impact</p>
                      <p className="font-medium text-foreground">
                        {incidentSubmission?.has_injuries ? 'Injury reported' : 'No injury flagged'}
                      </p>
                      <p className="text-xs text-muted-foreground">{medicalAssistance}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('incidents.detail.handoff_title')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-3" data-testid="incident-workflow-proof">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {t('incidents.detail.proof_eyebrow', 'Workflow proof')}
                    </p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          {t('incidents.detail.linked_investigation')}
                        </p>
                        <p className="mt-1 text-sm font-semibold text-foreground font-mono">
                          {investigationHref
                            ? latestInvestigation?.reference_number ||
                              `INV-${latestInvestigation?.id}`
                            : '0'}
                        </p>
                      </div>
                      <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          {t('incidents.detail.proof_actions', 'CAPA actions')}
                        </p>
                        <p
                          className="mt-1 text-lg font-semibold text-foreground"
                          data-testid="incident-capa-count"
                        >
                          {capaCountLabel}
                        </p>
                      </div>
                      <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          {t('incidents.detail.open_actions')}
                        </p>
                        <p className="mt-1 text-lg font-semibold text-foreground">
                          {openActionsLabel}
                        </p>
                      </div>
                    </div>
                    {actionsLoadFailed ? (
                      <p className="text-sm text-amber-700 dark:text-amber-400" role="status">
                        {t(
                          'incidents.detail.actions_unavailable',
                          'CAPA actions could not be loaded — counts may be incomplete.',
                        )}
                      </p>
                    ) : null}
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Evidence captured</p>
                    <p className="font-medium text-foreground">{surfacedEvidenceSummary}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Affected role</p>
                    <p className="font-medium text-foreground">{personRole}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Witnesses</p>
                    <p className="font-medium text-foreground">
                      {incidentSubmission?.has_witnesses
                        ? 'Witnesses captured'
                        : 'No witnesses recorded'}
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 pt-2 border-t border-border">
                    <Button
                      onClick={() =>
                        investigationHref
                          ? navigate(investigationHref)
                          : setShowInvestigationModal(true)
                      }
                    >
                      <FlaskConical className="w-4 h-4 mr-2" />
                      {investigationHref
                        ? t('incidents.detail.open_investigation')
                        : t('incidents.detail.start_investigation')}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => navigate(capaHref)}
                      disabled={actionsLoading}
                      data-testid="incident-capa-handoff-cta"
                    >
                      <ClipboardList className="w-4 h-4 mr-2" />
                      {t(
                        getCapaHandoffLabelKey('incident', actionsLoadFailed ? 0 : actions.length),
                        {
                          count: actions.length,
                        },
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-primary" />
                    Evidence
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div data-testid="incident-evidence-assets">
                    <EvidenceGallery
                      assets={evidenceAssets}
                      loading={evidenceLoading}
                      loadFailed={evidenceLoadFailed}
                      emptyTitle="No evidence assets are linked to this incident."
                      emptyDescription="Reporter-submission evidence is shown separately."
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldAlert className="w-5 h-5 text-primary" />
                    Linked risks
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {parseLinkedRiskIds(incident.linked_risk_ids).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {canRaiseRisk
                        ? 'No linked risks yet. Use Raise risk to create a register entry.'
                        : 'Raise risk is available for high and critical severity incidents.'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {parseLinkedRiskIds(incident.linked_risk_ids).map((riskId) => (
                        <button
                          key={riskId}
                          type="button"
                          className="w-full rounded-lg border border-border p-3 text-left hover:bg-muted/40"
                          onClick={() =>
                            navigate(
                              riskRegisterHref(riskId, {
                                incidentRef: incident.reference_number,
                              }),
                            )
                          }
                          data-testid={`incident-linked-risk-${riskId}`}
                        >
                          <div className="font-medium text-foreground">Risk #{riskId}</div>
                          <div className="text-sm text-muted-foreground">Open in risk register</div>
                        </button>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Activity Timeline</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex gap-3">
                      <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {t('incidents.detail.incident_reported')}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(incident.reported_date).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {t('incidents.detail.record_created')}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(incident.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="standards" className="mt-6">
          {/* Same StandardsAssessmentPanel host pattern as NearMissDetail */}
          <div data-testid="incident-standards-panel" id="standards-assessment-panel">
            <StandardsAssessmentPanel entityType="incident" entityId={incident.id} />
          </div>
        </TabsContent>

        <TabsContent value="submission" className="mt-6">
          <SubmissionSections
            sections={incidentSubmissionSections}
            emptyMessage="No preserved reporter submission is available for this incident yet."
          />
        </TabsContent>

        <TabsContent value="running-sheet" className="mt-6">
          <RunningSheetPanel
            entries={runningSheet}
            newEntry={newEntry}
            addingEntry={addingEntry}
            title={t('common.running_sheet', 'Running Sheet')}
            placeholder={t(
              'common.running_sheet_placeholder',
              'Add to the story... (auto-timestamped)',
            )}
            emptyTitle={t('common.running_sheet_empty_title', 'No entries yet')}
            emptyDescription={t(
              'incidents.detail.running_sheet_empty_description',
              'Add notes to build the incident narrative over time',
            )}
            onNewEntryChange={setNewEntry}
            onAddEntry={handleAddEntry}
            onDeleteEntry={handleDeleteEntry}
            createActionHref={buildRunningSheetCreateActionHref({
              sourceType: 'incident',
              sourceId: incident.id,
              referenceNumber: incident.reference_number,
              entrySnippet: runningSheet[0]?.content,
            })}
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
              {t('incidents.detail.start_investigation')}
            </DialogTitle>
            <DialogDescription>
              {t('incidents.detail.investigation_description', {
                reference: incident.reference_number,
              })}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateInvestigation} className="space-y-4">
            <div>
              <label
                htmlFor="incidentdetail-field-6"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('incidents.detail.investigation_title')}
              </label>
              <Input
                id="incidentdetail-field-6"
                value={investigationForm.title}
                onChange={(e) =>
                  setInvestigationForm({ ...investigationForm, title: e.target.value })
                }
                placeholder={`Investigation - ${incident.reference_number}`}
              />
            </div>
            <div>
              <label
                htmlFor="incidentdetail-field-7"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('incidents.detail.investigation_type')}
              </label>
              <Select
                value={investigationForm.investigation_type}
                onValueChange={(value) =>
                  setInvestigationForm({ ...investigationForm, investigation_type: value })
                }
              >
                <SelectTrigger id="incidentdetail-field-7">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="root_cause_analysis">
                    {t('incidents.detail.inv_type_rca')}
                  </SelectItem>
                  <SelectItem value="5_whys">{t('incidents.detail.inv_type_5whys')}</SelectItem>
                  <SelectItem value="fishbone">
                    {t('incidents.detail.inv_type_fishbone')}
                  </SelectItem>
                  <SelectItem value="incident_review">
                    {t('incidents.detail.inv_type_incident_review')}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <span className="block text-sm font-medium text-foreground">
                {t('incidents.detail.lead_investigator')}
              </span>
              <EngineerPeoplePicker
                valueLabel={investigationForm.lead_investigator}
                requireLogin
                onChange={(selection) =>
                  setInvestigationForm({
                    ...investigationForm,
                    lead_investigator: selection?.user?.email || selection?.label || '',
                  })
                }
                placeholder={t(
                  'incidents.detail.search_employees_placeholder',
                  'Search active employees…',
                )}
                testId="incident-lead-investigator-picker"
              />
            </div>
            <div>
              <label
                htmlFor="incidentdetail-field-8"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('incidents.detail.initial_notes')}
              </label>
              <Textarea
                id="incidentdetail-field-8"
                value={investigationForm.description}
                onChange={(e) =>
                  setInvestigationForm({ ...investigationForm, description: e.target.value })
                }
                placeholder={t('incidents.detail.investigation_notes_placeholder')}
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
                    {t('incidents.detail.open_existing_investigation', {
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
                  t('incidents.detail.create_investigation')
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
              {t('incidents.detail.add_action')}
            </DialogTitle>
            <DialogDescription>{t('incidents.detail.add_action_description')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label
                htmlFor="incidentdetail-field-9"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('incidents.detail.action_title_required')}
              </label>
              <Input
                id="incidentdetail-field-9"
                value={actionForm.title}
                onChange={(e) => setActionForm({ ...actionForm, title: e.target.value })}
                placeholder={t('incidents.detail.action_title_placeholder')}
                required
              />
            </div>
            <div className="space-y-2">
              <span className="block text-sm font-medium text-foreground">
                {t('incidents.detail.assign_to')}
              </span>
              <EngineerPeoplePicker
                valueLabel={actionForm.assigned_to}
                requireLogin
                onChange={(selection) =>
                  setActionForm({
                    ...actionForm,
                    assigned_to: selection?.user?.email || selection?.label || '',
                  })
                }
                placeholder={t(
                  'incidents.detail.search_employees_placeholder',
                  'Search active employees…',
                )}
                testId="incident-action-assignee-picker"
              />
            </div>
            <div>
              <label
                htmlFor="incidentdetail-field-10"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('common.priority')}
              </label>
              <Select
                value={actionForm.priority}
                onValueChange={(value) => setActionForm({ ...actionForm, priority: value })}
              >
                <SelectTrigger id="incidentdetail-field-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">
                    {t('incidents.detail.severity_critical')}
                  </SelectItem>
                  <SelectItem value="high">{t('incidents.detail.severity_high')}</SelectItem>
                  <SelectItem value="medium">{t('incidents.detail.severity_medium')}</SelectItem>
                  <SelectItem value="low">{t('incidents.detail.severity_low')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label
                htmlFor="incidentdetail-field-11"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('common.due_date')}
              </label>
              <Input
                id="incidentdetail-field-11"
                type="date"
                value={actionForm.due_date}
                onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })}
              />
            </div>
            <div>
              <label
                htmlFor="incidentdetail-field-12"
                className="block text-sm font-medium text-foreground mb-1"
              >
                {t('common.description')}
              </label>
              <Textarea
                id="incidentdetail-field-12"
                value={actionForm.description}
                onChange={(e) => setActionForm({ ...actionForm, description: e.target.value })}
                placeholder={t('incidents.detail.action_description_placeholder')}
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
                  t('incidents.detail.create_action')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Action Detail Modal */}
      <Dialog open={showActionDetailModal} onOpenChange={setShowActionDetailModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-primary" />
              {t('incidents.detail.action_details')}
            </DialogTitle>
            <DialogDescription>{t('incidents.detail.view_update_status')}</DialogDescription>
          </DialogHeader>

          {selectedAction && (
            <div className="space-y-4">
              {/* Action Info */}
              <div className="space-y-3">
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    {t('incidents.detail.title')}
                  </span>
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
                              : 'secondary'
                      }
                      className="mt-1"
                    >
                      {selectedAction.status.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('common.priority')}
                    </span>
                    <p className="text-foreground capitalize">{selectedAction.priority}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('common.due_date')}
                    </span>
                    <p className="text-foreground">
                      {selectedAction.due_date
                        ? new Date(selectedAction.due_date).toLocaleDateString()
                        : t('incidents.detail.not_set')}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('common.assigned_to')}
                    </span>
                    <p className="text-foreground">
                      {selectedAction.assigned_to_email || t('incidents.detail.unassigned')}
                    </p>
                  </div>
                </div>

                {selectedAction.completed_at && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('incidents.detail.completed_at')}
                    </span>
                    <p className="text-foreground">
                      {new Date(selectedAction.completed_at).toLocaleString()}
                    </p>
                  </div>
                )}

                {selectedAction.completion_notes && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">
                      {t('incidents.detail.completion_notes')}
                    </span>
                    <p className="text-foreground">{selectedAction.completion_notes}</p>
                  </div>
                )}
              </div>

              {/* Status Update Section */}
              <div className="border-t pt-4">
                <span className="text-sm font-medium text-muted-foreground mb-2 block">
                  {t('incidents.detail.update_status')}
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
                    <span className="text-sm">{t('incidents.detail.updating')}</span>
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setShowActionDetailModal(false)}>
                  {t('close')}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Completion Notes Dialog */}
      <Dialog open={showCompletionDialog} onOpenChange={setShowCompletionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('incidents.detail.complete_action')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <label className="text-sm font-medium" htmlFor="completion-notes">
              {t('incidents.detail.enter_completion_notes')}
            </label>
            <textarea
              id="completion-notes"
              className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={completionNotes}
              onChange={(e) => setCompletionNotes(e.target.value)}
              placeholder={t('incidents.detail.enter_completion_notes')}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCompletionDialog(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={confirmCompleteAction}>{t('common.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
