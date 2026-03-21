import { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
import { toast } from '../contexts/ToastContext'
import { Breadcrumbs } from '../components/ui/Breadcrumbs'
import { trackError } from '../utils/errorTracker'
import {
  ArrowLeft,
  Car,
  MapPin,
  Calendar,
  FileText,
  Plus,
  FlaskConical,
  CheckCircle,
  Loader2,
  ClipboardList,
  History,
  Shield,
  Pencil,
  Save,
  X,
  ExternalLink,
  Camera,
  Users,
  MessageSquare,
  Upload,
  Trash2,
  User,
} from 'lucide-react'
import {
  rtasApi,
  RTA,
  RTAUpdate,
  Witness,
  RunningSheetEntry,
  ThirdParty,
  EvidenceAsset,
  Investigation,
  investigationsApi,
  actionsApi,
  evidenceAssetsApi,
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
import { Switch } from '../components/ui/Switch'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/Tabs'
import { CaseSummaryRail } from '../components/case/CaseSummaryRail'
import { SubmissionSections } from '../components/case/SubmissionSections'
import {
  buildRtaSubmissionSections,
  getSubmissionPhotoSummary,
  getSubmissionSnapshot,
} from '../helpers/caseSubmission'
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
import { cn } from '../helpers/utils'
import { UserEmailSearch } from '../components/UserEmailSearch'

export default function RTADetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [rta, setRta] = useState<RTA | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState<RTAUpdate>({})

  const [selectedAction, setSelectedAction] = useState<Action | null>(null)
  const [showActionDetailModal, setShowActionDetailModal] = useState(false)
  const [updatingAction, setUpdatingAction] = useState(false)
  const [actionUpdateError, setActionUpdateError] = useState('')

  // Running Sheet
  const [runningSheet, setRunningSheet] = useState<RunningSheetEntry[]>([])
  const [newEntry, setNewEntry] = useState('')
  const [addingEntry, setAddingEntry] = useState(false)

  // Photos
  const [photos, setPhotos] = useState<EvidenceAsset[]>([])
  const [uploading, setUploading] = useState(false)

  // Witnesses (local edit state)
  const [editWitnesses, setEditWitnesses] = useState<Witness[]>([])

  // Third parties (local edit state)
  const [editThirdParties, setEditThirdParties] = useState<ThirdParty[]>([])

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

  const thirdPartyVehicleFieldId = (idx: number, field: string) => `rta-v2-${idx}-${field}`
  const thirdPartyDriverFieldId = (idx: number, field: string) => `rta-d2-${idx}-${field}`
  const witnessFieldId = (idx: number, field: string) => `rta-witness-${idx}-${field}`

  useEffect(() => {
    if (id) {
      loadRTA(parseInt(id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const loadRTA = async (rtaId: number) => {
    setError(null)
    try {
      const response = await rtasApi.get(rtaId)
      setRta(response.data)
      populateEditForm(response.data)
      loadActions()
      loadInvestigations(rtaId)
      loadRunningSheet(rtaId)
      loadPhotos(rtaId)
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'loadRTA' })
      setError(t('rtas.detail.load_error'))
    } finally {
      setLoading(false)
    }
  }

  const populateEditForm = (data: RTA) => {
    setEditForm({
      title: data.title,
      description: data.description,
      severity: data.severity,
      status: data.status,
      location: data.location,
      road_name: data.road_name,
      postcode: data.postcode,
      collision_time: data.collision_time,
      weather_conditions: data.weather_conditions,
      road_conditions: data.road_conditions,
      lighting_conditions: data.lighting_conditions,
      company_vehicle_registration: data.company_vehicle_registration,
      company_vehicle_make_model: data.company_vehicle_make_model,
      company_vehicle_damage: data.company_vehicle_damage,
      driver_name: data.driver_name,
      driver_statement: data.driver_statement,
      driver_injured: data.driver_injured,
      driver_injury_details: data.driver_injury_details,
      police_attended: data.police_attended,
      police_reference: data.police_reference,
      police_station: data.police_station,
      insurance_notified: data.insurance_notified,
      insurance_reference: data.insurance_reference,
      insurance_notes: data.insurance_notes,
      fault_determination: data.fault_determination,
    })
    const ws = (data.witnesses_structured as { witnesses?: Witness[] })?.witnesses
    setEditWitnesses(ws && ws.length > 0 ? ws : [])
    const tp = (data.third_parties as { parties?: ThirdParty[] })?.parties
    setEditThirdParties(tp && tp.length > 0 ? tp : [])
  }

  const loadActions = async () => {
    if (!id) return
    try {
      const response = await actionsApi.list(1, 50, undefined, 'rta', parseInt(id))
      setActions(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'loadActions' })
    }
  }

  const loadInvestigations = async (rtaId: number) => {
    try {
      const response = await rtasApi.listInvestigations(rtaId, 1, 10)
      setInvestigations(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'loadInvestigations' })
    }
  }

  const loadRunningSheet = async (rtaId: number) => {
    try {
      const response = await rtasApi.listRunningSheet(rtaId)
      setRunningSheet(response.data)
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'loadRunningSheet' })
    }
  }

  const loadPhotos = async (rtaId: number) => {
    try {
      const response = await evidenceAssetsApi.list({
        source_module: 'road_traffic_collision',
        source_id: rtaId,
        page_size: 50,
      })
      setPhotos(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'loadPhotos' })
    }
  }

  const handleSaveEdit = async () => {
    if (!rta) return
    setSaving(true)
    try {
      const payload: RTAUpdate = {
        ...editForm,
        third_parties:
          editThirdParties.length > 0
            ? { parties: editThirdParties }
            : undefined,
        witnesses_structured:
          editWitnesses.length > 0
            ? { witnesses: editWitnesses }
            : undefined,
      }
      const response = await rtasApi.update(rta.id, payload)
      setRta(response.data)
      setIsEditing(false)
      toast.success('Changes saved')
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'saveEdit' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    if (rta) populateEditForm(rta)
    setIsEditing(false)
  }

  // Running sheet handlers
  const handleAddEntry = async () => {
    if (!rta || !newEntry.trim()) return
    setAddingEntry(true)
    try {
      await rtasApi.addRunningSheetEntry(rta.id, { content: newEntry.trim() })
      setNewEntry('')
      loadRunningSheet(rta.id)
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'addRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setAddingEntry(false)
    }
  }

  const handleDeleteEntry = async (entryId: number) => {
    if (!rta) return
    try {
      await rtasApi.deleteRunningSheetEntry(rta.id, entryId)
      loadRunningSheet(rta.id)
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'deleteRunningSheetEntry' })
    }
  }

  // Photo upload handler
  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!rta || !e.target.files?.length) return
    setUploading(true)
    try {
      for (const file of Array.from(e.target.files)) {
        await evidenceAssetsApi.upload(file, {
          source_module: 'road_traffic_collision',
          source_id: rta.id,
          title: file.name,
          visibility: 'internal',
        })
      }
      loadPhotos(rta.id)
      toast.success('Photos uploaded')
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'uploadPhoto' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDeletePhoto = async (assetId: number) => {
    if (!rta) return
    try {
      await evidenceAssetsApi.delete(assetId)
      loadPhotos(rta.id)
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'deletePhoto' })
    }
  }

  const [investigationError, setInvestigationError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{
    id: number
    reference: string
  } | null>(null)

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!rta) return
    setCreating(true)
    setInvestigationError('')
    setExistingInvestigation(null)

    try {
      await investigationsApi.createFromRecord({
        source_type: 'road_traffic_collision',
        source_id: rta.id,
        title: investigationForm.title || `Investigation - ${rta.reference_number}`,
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
      trackError(err, { component: 'RTADetail', action: 'createInvestigation' })
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
          setInvestigationError(t('rtas.detail.investigation_exists'))
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
    if (!rta) return
    setCreating(true)
    try {
      await actionsApi.create({
        title: actionForm.title,
        description: actionForm.description || `Action for ${rta.reference_number}`,
        priority: actionForm.priority,
        due_date: actionForm.due_date || undefined,
        action_type: 'corrective',
        source_type: 'rta',
        source_id: rta.id,
        assigned_to_email: actionForm.assigned_to || undefined,
      })
      setShowActionModal(false)
      setActionForm({ title: '', description: '', priority: 'medium', due_date: '', assigned_to: '' })
      loadActions()
    } catch (err: unknown) {
      trackError(err, { component: 'RTADetail', action: 'createAction' })
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
    { value: 'in_progress', label: 'In Progress', className: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200' },
    { value: 'pending_verification', label: 'Pending Verification', className: 'bg-purple-100 text-purple-800 hover:bg-purple-200' },
    { value: 'completed', label: 'Completed', className: 'bg-green-100 text-green-800 hover:bg-green-200' },
    { value: 'cancelled', label: 'Cancelled', className: 'bg-gray-100 text-gray-800 hover:bg-gray-200' },
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
      const response = await actionsApi.update(selectedAction.id, 'rta', updatePayload)
      setSelectedAction(response.data)
      setActions((prev) => prev.map((a) => (a.id === selectedAction.id ? response.data : a)))
    } catch (err) {
      trackError(err, { component: 'RTADetail', action: 'updateActionStatus' })
      setActionUpdateError(getApiErrorMessage(err))
    } finally {
      setUpdatingAction(false)
    }
  }

  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completionNotes, setCompletionNotes] = useState('')

  const handleCompleteAction = () => {
    setCompletionNotes('')
    setShowCompletionDialog(true)
  }

  const handleConfirmCompletion = () => {
    setShowCompletionDialog(false)
    handleUpdateActionStatus('completed', completionNotes.trim() || undefined)
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'fatal': case 'serious_injury': return 'critical'
      case 'minor_injury': return 'high'
      case 'damage_only': return 'medium'
      case 'near_miss': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (st: string) => {
    switch (st) {
      case 'closed': return 'resolved'
      case 'reported': return 'submitted'
      case 'under_investigation': return 'in-progress'
      case 'pending_insurance': return 'acknowledged'
      case 'pending_actions': return 'awaiting-user'
      default: return 'secondary'
    }
  }

  // ──────────────────────── Loading / Error / Not Found ────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  if (error && !rta) {
    return (
      <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
        <p className="text-sm text-destructive">{error}</p>
        <button onClick={() => { setError(null); loadRTA(parseInt(id!)) }} className="text-sm font-medium text-destructive hover:underline">
          {t('rtas.detail.try_again')}
        </button>
      </div>
    )
  }

  if (!rta) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Car className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">{t('rtas.detail.not_found')}</p>
        <Button variant="outline" onClick={() => navigate('/rtas')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('rtas.back')}
        </Button>
      </div>
    )
  }

  // ──────────────────────── Helper: Read-only field ────────────────────────
  const Field = ({ label, value }: { label: string; value?: string | null }) => (
    <div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <p className="text-sm text-foreground mt-0.5">{value || '—'}</p>
    </div>
  )

  const parties = (rta.third_parties as { parties?: ThirdParty[] })?.parties || []
  const witnesses = (rta.witnesses_structured as { witnesses?: Witness[] })?.witnesses || []
  const rtaSubmission = getSubmissionSnapshot(rta.reporter_submission)
  const rtaSubmissionSections = buildRtaSubmissionSections(rtaSubmission)
  const evidenceSummary =
    photos.length > 0 ? `${photos.length} uploaded` : getSubmissionPhotoSummary(rtaSubmission)
  const latestInvestigation = investigations[0]
  const investigationSummary = latestInvestigation
    ? `${latestInvestigation.reference_number || latestInvestigation.title || 'Linked investigation'}`
    : 'Not started'
  const openActions = actions.filter((action) => action.status !== 'completed' && action.status !== 'cancelled')

  // ──────────────────────── RENDER ────────────────────────

  return (
    <div className="space-y-6 animate-fade-in">
      <Breadcrumbs
        items={[
          { label: t('rtas.title', 'Road Traffic Collisions'), href: '/rtas' },
          { label: rta?.reference_number || `#${id}` },
        ]}
      />

      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => { setError(null); loadRTA(parseInt(id!)) }} className="text-sm font-medium text-destructive hover:underline">
            {t('rtas.detail.try_again')}
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate('/rtas')} aria-label="Back to RTAs">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{rta.reference_number}</span>
              <Badge variant={getSeverityVariant(rta.severity) as any}>{rta.severity.replace('_', ' ')}</Badge>
              <Badge variant={getStatusVariant(rta.status) as any}>{rta.status.replace('_', ' ')}</Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">{rta.title}</h1>
            <p className="text-muted-foreground mt-1">
              {t('rtas.detail.reported_on', { date: new Date(rta.reported_date).toLocaleDateString() })}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={handleCancelEdit} disabled={saving}>
                <X className="w-4 h-4 mr-2" />{t('cancel')}
              </Button>
              <Button onClick={handleSaveEdit} disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                {t('rtas.detail.save_changes')}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                <Pencil className="w-4 h-4 mr-2" />{t('edit')}
              </Button>
              <Button variant="outline" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-2" />{t('rtas.detail.add_action')}
              </Button>
              <Button onClick={() => setShowInvestigationModal(true)}>
                <FlaskConical className="w-4 h-4 mr-2" />{t('rtas.detail.start_investigation')}
              </Button>
            </>
          )}
        </div>
      </div>

      <CaseSummaryRail
        items={[
          { label: 'Driver / Reporter', value: rta.reporter_name || rta.driver_name || 'Not provided', icon: <User className="w-4 h-4" /> },
          { label: 'Vehicle', value: rta.company_vehicle_registration || 'Not provided', icon: <Car className="w-4 h-4" /> },
          { label: 'Occurred at', value: new Date(rta.collision_date).toLocaleString(), icon: <Calendar className="w-4 h-4" /> },
          { label: 'Location', value: rta.location || 'Not specified', icon: <MapPin className="w-4 h-4" /> },
          { label: 'Third parties', value: `${parties.length} recorded`, icon: <Users className="w-4 h-4" /> },
          { label: 'Witnesses', value: `${witnesses.length} recorded`, icon: <Users className="w-4 h-4" /> },
          { label: 'Evidence', value: evidenceSummary, icon: <Camera className="w-4 h-4" /> },
          { label: 'Investigation', value: investigationSummary, icon: <FlaskConical className="w-4 h-4" /> },
        ]}
      />

      {/* ═══════════════════ TABBED CONTENT ═══════════════════ */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="w-full justify-start flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="overview"><FileText className="w-4 h-4 mr-1.5" />{t('rtas.tabs.overview', 'Overview')}</TabsTrigger>
          <TabsTrigger value="submission"><FileText className="w-4 h-4 mr-1.5" />Reporter Submission</TabsTrigger>
          <TabsTrigger value="vehicle1"><Car className="w-4 h-4 mr-1.5" />{t('rtas.tabs.vehicle1', 'Vehicle 1')}</TabsTrigger>
          <TabsTrigger value="vehicle2"><Car className="w-4 h-4 mr-1.5" />{t('rtas.tabs.vehicle2', 'Vehicle 2')}</TabsTrigger>
          <TabsTrigger value="driver1"><User className="w-4 h-4 mr-1.5" />{t('rtas.tabs.our_driver', 'Our Driver')}</TabsTrigger>
          <TabsTrigger value="driver2"><User className="w-4 h-4 mr-1.5" />{t('rtas.tabs.other_driver', 'Other Driver')}</TabsTrigger>
          <TabsTrigger value="witnesses"><Users className="w-4 h-4 mr-1.5" />{t('rtas.tabs.witnesses', 'Witnesses')}</TabsTrigger>
          <TabsTrigger value="photos"><Camera className="w-4 h-4 mr-1.5" />{t('rtas.tabs.photos', 'Photos')}</TabsTrigger>
          <TabsTrigger value="running-sheet"><MessageSquare className="w-4 h-4 mr-1.5" />{t('rtas.tabs.running_sheet', 'Running Sheet')}</TabsTrigger>
          <TabsTrigger value="actions"><ClipboardList className="w-4 h-4 mr-1.5" />{t('rtas.tabs.actions', 'Actions')} ({actions.length})</TabsTrigger>
        </TabsList>

        {/* ────── OVERVIEW TAB ────── */}
        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-primary" />
                    {t('rtas.detail.collision_details')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {isEditing ? (
                    <>
                      <div>
                        <label htmlFor="rta-edit-title" className="text-sm font-medium text-muted-foreground">{t('rtas.detail.title_label')}</label>
                        <Input id="rta-edit-title" value={editForm.title || ''} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} className="mt-1" />
                      </div>
                      <div>
                        <label htmlFor="rta-edit-description" className="text-sm font-medium text-muted-foreground">{t('common.description')}</label>
                        <Textarea id="rta-edit-description" value={editForm.description || ''} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} rows={4} className="mt-1" />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label htmlFor="rta-edit-severity" className="text-sm font-medium text-muted-foreground">{t('rtas.detail.severity')}</label>
                          <Select value={editForm.severity} onValueChange={(v) => setEditForm({ ...editForm, severity: v })}>
                            <SelectTrigger id="rta-edit-severity" className="mt-1"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="near_miss">Near Miss</SelectItem>
                              <SelectItem value="damage_only">Damage Only</SelectItem>
                              <SelectItem value="minor_injury">Minor Injury</SelectItem>
                              <SelectItem value="serious_injury">Serious Injury</SelectItem>
                              <SelectItem value="fatal">Fatal</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label htmlFor="rta-edit-status" className="text-sm font-medium text-muted-foreground">{t('common.status')}</label>
                          <Select value={editForm.status} onValueChange={(v) => setEditForm({ ...editForm, status: v })}>
                            <SelectTrigger id="rta-edit-status" className="mt-1"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="reported">Reported</SelectItem>
                              <SelectItem value="under_investigation">Under Investigation</SelectItem>
                              <SelectItem value="pending_insurance">Pending Insurance</SelectItem>
                              <SelectItem value="pending_actions">Pending Actions</SelectItem>
                              <SelectItem value="closed">Closed</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="col-span-2">
                          <label htmlFor="rta-edit-location" className="text-sm font-medium text-muted-foreground">{t('common.location')}</label>
                          <Input id="rta-edit-location" value={editForm.location || ''} onChange={(e) => setEditForm({ ...editForm, location: e.target.value })} className="mt-1" />
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <label htmlFor="rta-edit-weather" className="text-sm font-medium text-muted-foreground">Weather</label>
                          <Input id="rta-edit-weather" value={editForm.weather_conditions || ''} onChange={(e) => setEditForm({ ...editForm, weather_conditions: e.target.value })} className="mt-1" placeholder="e.g. Rain" />
                        </div>
                        <div>
                          <label htmlFor="rta-edit-road" className="text-sm font-medium text-muted-foreground">Road Conditions</label>
                          <Input id="rta-edit-road" value={editForm.road_conditions || ''} onChange={(e) => setEditForm({ ...editForm, road_conditions: e.target.value })} className="mt-1" placeholder="e.g. Wet" />
                        </div>
                        <div>
                          <label htmlFor="rta-edit-lighting" className="text-sm font-medium text-muted-foreground">Lighting</label>
                          <Input id="rta-edit-lighting" value={editForm.lighting_conditions || ''} onChange={(e) => setEditForm({ ...editForm, lighting_conditions: e.target.value })} className="mt-1" placeholder="e.g. Daylight" />
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <span className="text-sm font-medium text-muted-foreground">{t('common.description')}</span>
                        <p className="mt-1 text-foreground whitespace-pre-wrap">{rta.description || t('rtas.detail.no_description')}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <Field label={t('rtas.detail.severity')} value={rta.severity.replace('_', ' ')} />
                        <Field label={t('common.status')} value={rta.status.replace('_', ' ')} />
                        <Field label={t('rtas.detail.collision_date')} value={new Date(rta.collision_date).toLocaleString()} />
                        <Field label={t('common.location')} value={rta.location} />
                        {rta.weather_conditions && <Field label="Weather" value={rta.weather_conditions} />}
                        {rta.road_conditions && <Field label="Road Conditions" value={rta.road_conditions} />}
                        {rta.lighting_conditions && <Field label="Lighting" value={rta.lighting_conditions} />}
                        {rta.fault_determination && <Field label="Fault Determination" value={rta.fault_determination.replace('_', ' ')} />}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
            <div className="space-y-6">
              <Card>
                <CardHeader><CardTitle className="text-base">{t('rtas.detail.quick_info')}</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center"><Calendar className="w-5 h-5 text-primary" /></div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('rtas.detail.created')}</p>
                      <p className="font-medium text-foreground">{new Date(rta.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center"><MapPin className="w-5 h-5 text-info" /></div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('common.location')}</p>
                      <p className="font-medium text-foreground">{rta.location || t('rtas.detail.not_specified')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center"><Shield className="w-5 h-5 text-warning" /></div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('rtas.detail.insurance_notified')}</p>
                      <p className="font-medium text-foreground">{rta.insurance_notified ? t('common.yes') : t('common.no')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center"><User className="w-5 h-5 text-success" /></div>
                    <div>
                      <p className="text-sm text-muted-foreground">Reporter</p>
                      <p className="font-medium text-foreground">{rta.reporter_name || rta.driver_name || 'Not provided'}</p>
                      <p className="text-xs text-muted-foreground">{rta.reporter_email || rta.driver_email || 'No contact captured'}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-base">Investigation Status</CardTitle></CardHeader>
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
                    <p className="text-sm text-muted-foreground">Evidence captured</p>
                    <p className="font-medium text-foreground">{evidenceSummary}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Footage</p>
                    <p className="font-medium text-foreground">
                      {rta.dashcam_footage_available || rta.cctv_available ? 'Available' : 'Not flagged'}
                    </p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><History className="w-4 h-4" />{t('rtas.detail.activity_timeline')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex gap-3">
                      <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{t('rtas.detail.rta_reported')}</p>
                        <p className="text-xs text-muted-foreground">{new Date(rta.reported_date).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{t('rtas.detail.record_created')}</p>
                        <p className="text-xs text-muted-foreground">{new Date(rta.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="submission">
          <SubmissionSections
            sections={rtaSubmissionSections}
            emptyMessage="No preserved reporter submission is available for this collision yet."
          />
        </TabsContent>

        {/* ────── VEHICLE 1 TAB ────── */}
        <TabsContent value="vehicle1">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Car className="w-5 h-5 text-primary" />Company Vehicle (Vehicle 1)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="rta-v1-reg" className="text-sm font-medium text-muted-foreground">Registration</label>
                    <Input id="rta-v1-reg" value={editForm.company_vehicle_registration || ''} onChange={(e) => setEditForm({ ...editForm, company_vehicle_registration: e.target.value })} className="mt-1" placeholder="AB12 CDE" />
                  </div>
                  <div>
                    <label htmlFor="rta-v1-make" className="text-sm font-medium text-muted-foreground">Make / Model</label>
                    <Input id="rta-v1-make" value={editForm.company_vehicle_make_model || ''} onChange={(e) => setEditForm({ ...editForm, company_vehicle_make_model: e.target.value })} className="mt-1" placeholder="e.g. Ford Transit" />
                  </div>
                  <div className="col-span-2">
                    <label htmlFor="rta-v1-damage" className="text-sm font-medium text-muted-foreground">Damage Description</label>
                    <Textarea id="rta-v1-damage" value={editForm.company_vehicle_damage || ''} onChange={(e) => setEditForm({ ...editForm, company_vehicle_damage: e.target.value })} rows={3} className="mt-1" placeholder="Describe damage to company vehicle" />
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Registration" value={rta.company_vehicle_registration} />
                  <Field label="Make / Model" value={rta.company_vehicle_make_model} />
                  <div className="col-span-2">
                    <Field label="Damage" value={rta.company_vehicle_damage} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── VEHICLE 2 TAB ────── */}
        <TabsContent value="vehicle2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Car className="w-5 h-5 text-primary" />Other Vehicle (Vehicle 2)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  {editThirdParties.length === 0 && (
                    <Button type="button" variant="outline" onClick={() => setEditThirdParties([{ vehicle_reg: '', vehicle_make_model: '', damage: '' }])}>
                      <Plus className="w-4 h-4 mr-1" />Add Third Party Vehicle
                    </Button>
                  )}
                  {editThirdParties.map((tp, idx) => (
                    <div key={idx} className="border rounded-lg p-4 space-y-3 bg-muted/30">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Vehicle {idx + 2}</span>
                        <Button type="button" variant="ghost" size="sm" className="text-destructive h-6 px-2 text-xs" onClick={() => setEditThirdParties(editThirdParties.filter((_, i) => i !== idx))}>Remove</Button>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label htmlFor={thirdPartyVehicleFieldId(idx, 'registration')} className="block text-xs font-medium text-muted-foreground mb-1">Registration</label>
                          <Input id={thirdPartyVehicleFieldId(idx, 'registration')} value={tp.vehicle_reg || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], vehicle_reg: e.target.value }; setEditThirdParties(u) }} placeholder="AB12 CDE" />
                        </div>
                        <div>
                          <label htmlFor={thirdPartyVehicleFieldId(idx, 'make-model')} className="block text-xs font-medium text-muted-foreground mb-1">Make / Model</label>
                          <Input id={thirdPartyVehicleFieldId(idx, 'make-model')} value={tp.vehicle_make_model || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], vehicle_make_model: e.target.value }; setEditThirdParties(u) }} placeholder="e.g. VW Polo" />
                        </div>
                      </div>
                      <div>
                        <label htmlFor={thirdPartyVehicleFieldId(idx, 'damage')} className="block text-xs font-medium text-muted-foreground mb-1">Damage</label>
                        <Textarea id={thirdPartyVehicleFieldId(idx, 'damage')} value={tp.damage || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], damage: e.target.value }; setEditThirdParties(u) }} rows={2} placeholder="Describe damage" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label htmlFor={thirdPartyVehicleFieldId(idx, 'insurer')} className="block text-xs font-medium text-muted-foreground mb-1">Insurer</label>
                          <Input id={thirdPartyVehicleFieldId(idx, 'insurer')} value={tp.insurer || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], insurer: e.target.value }; setEditThirdParties(u) }} placeholder="Insurance company" />
                        </div>
                        <div>
                          <label htmlFor={thirdPartyVehicleFieldId(idx, 'policy-number')} className="block text-xs font-medium text-muted-foreground mb-1">Policy No.</label>
                          <Input id={thirdPartyVehicleFieldId(idx, 'policy-number')} value={tp.insurer_policy_number || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], insurer_policy_number: e.target.value }; setEditThirdParties(u) }} placeholder="Policy number" />
                        </div>
                      </div>
                    </div>
                  ))}
                  {editThirdParties.length > 0 && (
                    <Button type="button" variant="outline" size="sm" onClick={() => setEditThirdParties([...editThirdParties, { vehicle_reg: '', vehicle_make_model: '', damage: '' }])}>
                      <Plus className="w-3 h-3 mr-1" />Add Another Vehicle
                    </Button>
                  )}
                </>
              ) : (
                parties.length === 0 ? (
                  <p className="text-muted-foreground text-sm py-4">No third party vehicles recorded. Click Edit to add.</p>
                ) : (
                  parties.map((tp, idx) => (
                    <div key={idx} className="border rounded-lg p-4 bg-muted/30">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Vehicle {idx + 2}</span>
                      <div className="grid grid-cols-2 gap-3 mt-2">
                        <Field label="Registration" value={tp.vehicle_reg} />
                        <Field label="Make / Model" value={tp.vehicle_make_model} />
                        <div className="col-span-2"><Field label="Damage" value={tp.damage} /></div>
                        {tp.insurer && <Field label="Insurer" value={tp.insurer} />}
                        {tp.insurer_policy_number && <Field label="Policy No." value={tp.insurer_policy_number} />}
                      </div>
                    </div>
                  ))
                )
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── DRIVER 1 TAB ────── */}
        <TabsContent value="driver1">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><User className="w-5 h-5 text-primary" />Our Driver</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="rta-d1-name" className="text-sm font-medium text-muted-foreground">Driver Name</label>
                    <Input id="rta-d1-name" value={editForm.driver_name || ''} onChange={(e) => setEditForm({ ...editForm, driver_name: e.target.value })} className="mt-1" />
                  </div>
                  <div className="flex items-center gap-3 pt-6">
                    <Switch id="rta-d1-injured" checked={editForm.driver_injured || false} onCheckedChange={(c) => setEditForm({ ...editForm, driver_injured: c })} />
                    <label htmlFor="rta-d1-injured" className="text-sm text-foreground">Driver Injured</label>
                  </div>
                  {editForm.driver_injured && (
                    <div className="col-span-2">
                      <label htmlFor="rta-d1-injury" className="text-sm font-medium text-muted-foreground">Injury Details</label>
                      <Textarea id="rta-d1-injury" value={editForm.driver_injury_details || ''} onChange={(e) => setEditForm({ ...editForm, driver_injury_details: e.target.value })} rows={3} className="mt-1" placeholder="Describe injuries" />
                    </div>
                  )}
                  <div className="col-span-2">
                    <label htmlFor="rta-d1-statement" className="text-sm font-medium text-muted-foreground">Driver Statement</label>
                    <Textarea id="rta-d1-statement" value={editForm.driver_statement || ''} onChange={(e) => setEditForm({ ...editForm, driver_statement: e.target.value })} rows={4} className="mt-1" placeholder="Driver's account of the incident" />
                  </div>
                  <div className="flex items-center gap-3">
                    <Switch id="rta-d1-police" checked={editForm.police_attended || false} onCheckedChange={(c) => setEditForm({ ...editForm, police_attended: c })} />
                    <label htmlFor="rta-d1-police" className="text-sm text-foreground">Police Attended</label>
                  </div>
                  {editForm.police_attended && (
                    <>
                      <div>
                        <label htmlFor="rta-d1-police-ref" className="text-sm font-medium text-muted-foreground">Police Reference</label>
                        <Input id="rta-d1-police-ref" value={editForm.police_reference || ''} onChange={(e) => setEditForm({ ...editForm, police_reference: e.target.value })} className="mt-1" />
                      </div>
                      <div>
                        <label htmlFor="rta-d1-police-stn" className="text-sm font-medium text-muted-foreground">Police Station</label>
                        <Input id="rta-d1-police-stn" value={editForm.police_station || ''} onChange={(e) => setEditForm({ ...editForm, police_station: e.target.value })} className="mt-1" />
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Driver Name" value={rta.driver_name} />
                  <Field label="Driver Injured" value={rta.driver_injured ? 'Yes' : 'No'} />
                  {rta.driver_injury_details && <div className="col-span-2"><Field label="Injury Details" value={rta.driver_injury_details} /></div>}
                  {rta.driver_statement && <div className="col-span-2"><Field label="Driver Statement" value={rta.driver_statement} /></div>}
                  <Field label="Police Attended" value={rta.police_attended ? 'Yes' : 'No'} />
                  {rta.police_reference && <Field label="Police Reference" value={rta.police_reference} />}
                  {rta.police_station && <Field label="Police Station" value={rta.police_station} />}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── DRIVER 2 TAB ────── */}
        <TabsContent value="driver2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><User className="w-5 h-5 text-primary" />Other Driver</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  {editThirdParties.length === 0 && (
                    <Button type="button" variant="outline" onClick={() => setEditThirdParties([{ name: '', phone: '' }])}>
                      <Plus className="w-4 h-4 mr-1" />Add Third Party Driver
                    </Button>
                  )}
                  {editThirdParties.map((tp, idx) => (
                    <div key={idx} className="border rounded-lg p-4 space-y-3 bg-muted/30">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Third Party {idx + 1}</span>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label htmlFor={thirdPartyDriverFieldId(idx, 'name')} className="block text-xs font-medium text-muted-foreground mb-1">Name</label>
                          <Input id={thirdPartyDriverFieldId(idx, 'name')} value={tp.name || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], name: e.target.value }; setEditThirdParties(u) }} placeholder="Full name" />
                        </div>
                        <div>
                          <label htmlFor={thirdPartyDriverFieldId(idx, 'phone')} className="block text-xs font-medium text-muted-foreground mb-1">Phone</label>
                          <Input id={thirdPartyDriverFieldId(idx, 'phone')} value={tp.phone || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], phone: e.target.value }; setEditThirdParties(u) }} placeholder="07xxx xxxxxx" />
                        </div>
                        <div>
                          <label htmlFor={thirdPartyDriverFieldId(idx, 'email')} className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
                          <Input id={thirdPartyDriverFieldId(idx, 'email')} value={tp.email || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], email: e.target.value }; setEditThirdParties(u) }} placeholder="email@example.com" />
                        </div>
                        <div className="flex items-center gap-2 pt-5">
                          <Switch id={thirdPartyDriverFieldId(idx, 'injured')} checked={tp.injured || false} onCheckedChange={(c) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], injured: c }; setEditThirdParties(u) }} />
                          <label htmlFor={thirdPartyDriverFieldId(idx, 'injured')} className="text-sm">Injured</label>
                        </div>
                      </div>
                      {tp.injured && (
                        <div>
                          <label htmlFor={thirdPartyDriverFieldId(idx, 'injury-details')} className="block text-xs font-medium text-muted-foreground mb-1">Injury Details</label>
                          <Textarea id={thirdPartyDriverFieldId(idx, 'injury-details')} value={tp.injury_details || ''} onChange={(e) => { const u = [...editThirdParties]; u[idx] = { ...u[idx], injury_details: e.target.value }; setEditThirdParties(u) }} rows={2} placeholder="Describe injuries" />
                        </div>
                      )}
                    </div>
                  ))}
                </>
              ) : (
                parties.length === 0 ? (
                  <p className="text-muted-foreground text-sm py-4">No third party driver details recorded. Click Edit to add.</p>
                ) : (
                  parties.map((tp, idx) => (
                    <div key={idx} className="border rounded-lg p-4 bg-muted/30">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Third Party {idx + 1}</span>
                      <div className="grid grid-cols-2 gap-3 mt-2">
                        <Field label="Name" value={tp.name} />
                        <Field label="Phone" value={tp.phone} />
                        {tp.email && <Field label="Email" value={tp.email} />}
                        <Field label="Injured" value={tp.injured ? 'Yes' : 'No'} />
                        {tp.injury_details && <div className="col-span-2"><Field label="Injury Details" value={tp.injury_details} /></div>}
                      </div>
                    </div>
                  ))
                )
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── WITNESSES TAB ────── */}
        <TabsContent value="witnesses">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Users className="w-5 h-5 text-primary" />Witnesses</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  {editWitnesses.map((w, idx) => (
                    <div key={idx} className="border rounded-lg p-4 space-y-3 bg-muted/30">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Witness {idx + 1}</span>
                        <Button type="button" variant="ghost" size="sm" className="text-destructive h-6 px-2 text-xs" onClick={() => setEditWitnesses(editWitnesses.filter((_, i) => i !== idx))}>Remove</Button>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label htmlFor={witnessFieldId(idx, 'name')} className="block text-xs font-medium text-muted-foreground mb-1">Name</label>
                          <Input id={witnessFieldId(idx, 'name')} value={w.name || ''} onChange={(e) => { const u = [...editWitnesses]; u[idx] = { ...u[idx], name: e.target.value }; setEditWitnesses(u) }} placeholder="Full name" />
                        </div>
                        <div>
                          <label htmlFor={witnessFieldId(idx, 'phone')} className="block text-xs font-medium text-muted-foreground mb-1">Phone</label>
                          <Input id={witnessFieldId(idx, 'phone')} value={w.phone || ''} onChange={(e) => { const u = [...editWitnesses]; u[idx] = { ...u[idx], phone: e.target.value }; setEditWitnesses(u) }} placeholder="07xxx xxxxxx" />
                        </div>
                        <div>
                          <label htmlFor={witnessFieldId(idx, 'email')} className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
                          <Input id={witnessFieldId(idx, 'email')} value={w.email || ''} onChange={(e) => { const u = [...editWitnesses]; u[idx] = { ...u[idx], email: e.target.value }; setEditWitnesses(u) }} placeholder="email@example.com" />
                        </div>
                        <div className="flex items-center gap-2 pt-5">
                          <Switch id={witnessFieldId(idx, 'statement-consent')} checked={w.willing_to_provide_statement || false} onCheckedChange={(c) => { const u = [...editWitnesses]; u[idx] = { ...u[idx], willing_to_provide_statement: c }; setEditWitnesses(u) }} />
                          <label htmlFor={witnessFieldId(idx, 'statement-consent')} className="text-sm">Willing to give statement</label>
                        </div>
                      </div>
                      <div>
                        <label htmlFor={witnessFieldId(idx, 'statement')} className="block text-xs font-medium text-muted-foreground mb-1">Statement</label>
                        <Textarea id={witnessFieldId(idx, 'statement')} value={w.statement || ''} onChange={(e) => { const u = [...editWitnesses]; u[idx] = { ...u[idx], statement: e.target.value }; setEditWitnesses(u) }} rows={3} placeholder="Witness account" />
                      </div>
                    </div>
                  ))}
                  <Button type="button" variant="outline" onClick={() => setEditWitnesses([...editWitnesses, { name: '', phone: '' }])}>
                    <Plus className="w-4 h-4 mr-1" />Add Witness
                  </Button>
                </>
              ) : witnesses.length === 0 ? (
                <p className="text-muted-foreground text-sm py-4">No witnesses recorded. Click Edit to add.</p>
              ) : (
                witnesses.map((w, idx) => (
                  <div key={idx} className="border rounded-lg p-4 bg-muted/30">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Witness {idx + 1}</span>
                    <div className="grid grid-cols-2 gap-3 mt-2">
                      <Field label="Name" value={w.name} />
                      <Field label="Phone" value={w.phone} />
                      {w.email && <Field label="Email" value={w.email} />}
                      <Field label="Willing to give statement" value={w.willing_to_provide_statement ? 'Yes' : 'No'} />
                      {w.statement && <div className="col-span-2"><Field label="Statement" value={w.statement} /></div>}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── PHOTOS TAB ────── */}
        <TabsContent value="photos">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2"><Camera className="w-5 h-5 text-primary" />Scene Photos &amp; Evidence</CardTitle>
              <div>
                <input ref={fileInputRef} type="file" multiple accept="image/*,video/*,.pdf" className="hidden" onChange={handlePhotoUpload} aria-label="Upload photos or evidence files" />
                <Button variant="outline" size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
                  {uploading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />}
                  Upload
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {photos.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Camera className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No photos or evidence uploaded yet</p>
                  <p className="text-sm mt-1">Upload photos of the scene, vehicle damage, or other evidence</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {photos.map((photo) => (
                    <div key={photo.id} className="group relative border rounded-lg overflow-hidden bg-muted/30">
                      {photo.content_type?.startsWith('image/') ? (
                        <div className="aspect-square bg-muted flex items-center justify-center">
                          <Camera className="w-8 h-8 text-muted-foreground" />
                        </div>
                      ) : (
                        <div className="aspect-square bg-muted flex flex-col items-center justify-center">
                          <FileText className="w-8 h-8 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground mt-1">{photo.content_type?.split('/')[1]?.toUpperCase()}</span>
                        </div>
                      )}
                      <div className="p-2">
                        <p className="text-xs text-foreground truncate">{photo.title || photo.original_filename}</p>
                        <p className="text-xs text-muted-foreground">{new Date(photo.created_at).toLocaleDateString()}</p>
                      </div>
                      <Button variant="ghost" size="sm" className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 h-6 w-6 p-0 text-destructive" onClick={() => handleDeletePhoto(photo.id)} aria-label={`Delete photo ${photo.title || photo.original_filename}`}>
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── RUNNING SHEET TAB ────── */}
        <TabsContent value="running-sheet">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><MessageSquare className="w-5 h-5 text-primary" />Running Sheet</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-3">
                <Textarea value={newEntry} onChange={(e) => setNewEntry(e.target.value)} placeholder="Add to the story... (auto-timestamped)" rows={2} className="flex-1" />
                <Button onClick={handleAddEntry} disabled={addingEntry || !newEntry.trim()} className="self-end">
                  {addingEntry ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4 mr-1" />}
                  Add
                </Button>
              </div>

              {runningSheet.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No entries yet</p>
                  <p className="text-sm mt-1">Add notes to build the incident narrative over time</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {runningSheet.map((entry) => (
                    <div key={entry.id} className="group border rounded-lg p-4 bg-muted/30 relative">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-mono font-semibold text-primary">
                          {new Date(entry.created_at).toLocaleString()}
                        </span>
                        {entry.author_email && (
                          <span className="text-xs text-muted-foreground">— {entry.author_email}</span>
                        )}
                      </div>
                      <p className="text-sm text-foreground whitespace-pre-wrap">{entry.content}</p>
                      <Button variant="ghost" size="sm" className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6 p-0 text-destructive" onClick={() => handleDeleteEntry(entry.id)} aria-label="Delete running sheet entry">
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ────── ACTIONS TAB ────── */}
        <TabsContent value="actions">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-primary" />
                {t('rtas.detail.actions_count', { count: actions.length })}
              </CardTitle>
              <Button variant="outline" size="sm" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-1" />{t('common.add')}
              </Button>
            </CardHeader>
            <CardContent>
              {actions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>{t('rtas.detail.no_actions')}</p>
                  <p className="text-sm">{t('rtas.detail.no_actions_description')}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {actions.map((action) => (
                    <div
                      key={action.id}
                      className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border cursor-pointer hover:bg-accent/50 transition-colors"
                      onClick={() => handleOpenAction(action)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleOpenAction(action) } }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'w-8 h-8 rounded-lg flex items-center justify-center',
                          action.status === 'completed' ? 'bg-success/10 text-success' : action.status === 'cancelled' ? 'bg-destructive/10 text-destructive' : 'bg-warning/10 text-warning',
                        )}>
                          <CheckCircle className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{action.title}</p>
                          <p className="text-sm text-muted-foreground">
                            {action.due_date ? t('rtas.detail.due', { date: new Date(action.due_date).toLocaleDateString() }) : t('rtas.detail.no_due_date')}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={action.status === 'completed' ? 'resolved' : action.status === 'cancelled' ? 'destructive' : action.status === 'in_progress' ? 'in-progress' : ('secondary' as any)}>
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
        </TabsContent>
      </Tabs>

      {/* ═══════════════════ MODALS ═══════════════════ */}

      {/* Create Investigation Modal */}
      <Dialog open={showInvestigationModal} onOpenChange={(open) => { setShowInvestigationModal(open); if (!open) { setInvestigationError(''); setExistingInvestigation(null) } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><FlaskConical className="w-5 h-5 text-primary" />{t('rtas.detail.start_investigation')}</DialogTitle>
            <DialogDescription>{t('rtas.detail.investigation_description', { reference: rta.reference_number })}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateInvestigation} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('rtas.detail.investigation_title')}</label>
              <Input value={investigationForm.title} onChange={(e) => setInvestigationForm({ ...investigationForm, title: e.target.value })} placeholder={`Investigation - ${rta.reference_number}`} />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('rtas.detail.investigation_type')}</label>
              <Select value={investigationForm.investigation_type} onValueChange={(v) => setInvestigationForm({ ...investigationForm, investigation_type: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="root_cause_analysis">Root Cause Analysis</SelectItem>
                  <SelectItem value="5_whys">5 Whys</SelectItem>
                  <SelectItem value="fishbone">Fishbone Analysis</SelectItem>
                  <SelectItem value="incident_review">Incident Review</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <UserEmailSearch label={t('rtas.detail.lead_investigator')} value={investigationForm.lead_investigator} onChange={handleInvestigatorChange} placeholder={t('rtas.detail.search_by_email')} />
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('rtas.detail.initial_notes')}</label>
              <Textarea value={investigationForm.description} onChange={(e) => setInvestigationForm({ ...investigationForm, description: e.target.value })} placeholder={t('rtas.detail.initial_notes_placeholder')} rows={4} />
            </div>
            {investigationError && (
              <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3">
                <p className="text-sm text-destructive">{investigationError}</p>
                {existingInvestigation && (
                  <Button type="button" variant="link" size="sm" onClick={() => { setShowInvestigationModal(false); navigate(`/investigations/${existingInvestigation.id}`) }} className="mt-2 p-0 h-auto text-primary">
                    <ExternalLink className="w-3 h-3 mr-1" />
                    {t('rtas.detail.open_existing_investigation', { reference: existingInvestigation.reference })}
                  </Button>
                )}
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowInvestigationModal(false)}>{t('cancel')}</Button>
              <Button type="submit" disabled={creating}>{creating ? <Loader2 className="w-4 h-4 animate-spin" /> : t('rtas.detail.create_investigation')}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Create Action Modal */}
      <Dialog open={showActionModal} onOpenChange={setShowActionModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><ClipboardList className="w-5 h-5 text-primary" />{t('rtas.detail.add_action')}</DialogTitle>
            <DialogDescription>{t('rtas.detail.add_action_description')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('rtas.detail.action_title_required')}</label>
              <Input value={actionForm.title} onChange={(e) => setActionForm({ ...actionForm, title: e.target.value })} placeholder={t('rtas.detail.action_title_placeholder')} required />
            </div>
            <UserEmailSearch label={t('rtas.detail.assign_to')} value={actionForm.assigned_to} onChange={handleAssigneeChange} placeholder={t('rtas.detail.search_by_email')} required />
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('common.priority')}</label>
              <Select value={actionForm.priority} onValueChange={(v) => setActionForm({ ...actionForm, priority: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('rtas.detail.due_date')}</label>
              <Input type="date" value={actionForm.due_date} onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('common.description')}</label>
              <Textarea value={actionForm.description} onChange={(e) => setActionForm({ ...actionForm, description: e.target.value })} placeholder={t('rtas.detail.action_description_placeholder')} rows={3} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowActionModal(false)}>{t('cancel')}</Button>
              <Button type="submit" disabled={creating || !actionForm.title}>{creating ? <Loader2 className="w-4 h-4 animate-spin" /> : t('rtas.detail.create_action')}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Completion Notes Dialog */}
      <Dialog open={showCompletionDialog} onOpenChange={setShowCompletionDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t('rtas.detail.completion_notes_title', 'Complete Action')}</DialogTitle>
            <DialogDescription>{t('rtas.detail.completion_notes_desc', 'Add optional completion notes before marking this action as completed.')}</DialogDescription>
          </DialogHeader>
          <div>
            <label htmlFor="completion-notes" className="block text-sm font-medium text-foreground mb-1">{t('rtas.detail.completion_notes_label', 'Completion Notes')}</label>
            <Textarea id="completion-notes" value={completionNotes} onChange={(e) => setCompletionNotes(e.target.value)} rows={3} placeholder={t('rtas.detail.completion_notes_placeholder', 'Optional notes about how this action was completed...')} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCompletionDialog(false)}>{t('cancel')}</Button>
            <Button onClick={handleConfirmCompletion}>{t('rtas.detail.mark_complete', 'Mark Complete')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Action Detail Modal */}
      <Dialog open={showActionDetailModal} onOpenChange={(open) => { setShowActionDetailModal(open); if (!open) { setSelectedAction(null); setActionUpdateError('') } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><ClipboardList className="w-5 h-5 text-primary" />Action Details</DialogTitle>
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
                    <span className="text-sm font-medium text-muted-foreground">{t('common.description')}</span>
                    <p className="text-foreground">{selectedAction.description}</p>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">{t('common.status')}</span>
                    <Badge variant={selectedAction.status === 'completed' ? 'resolved' : selectedAction.status === 'cancelled' ? 'destructive' : selectedAction.status === 'in_progress' ? 'in-progress' : ('secondary' as any)} className="mt-1">
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
                    <p className="text-foreground">{selectedAction.due_date ? new Date(selectedAction.due_date).toLocaleDateString() : 'Not set'}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Assigned to</span>
                    <p className="text-foreground">{selectedAction.assigned_to_email || 'Unassigned'}</p>
                  </div>
                </div>
                {selectedAction.completed_at && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Completed at</span>
                    <p className="text-foreground">{new Date(selectedAction.completed_at).toLocaleString()}</p>
                  </div>
                )}
                {selectedAction.completion_notes && (
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">Completion Notes</span>
                    <p className="text-foreground">{selectedAction.completion_notes}</p>
                  </div>
                )}
              </div>
              <div className="border-t pt-4">
                <span className="text-sm font-medium text-muted-foreground mb-2 block">Update Status</span>
                <div className="flex flex-wrap gap-2">
                  {ACTION_STATUS_OPTIONS.map((option) => (
                    <Button key={option.value} size="sm" variant="outline"
                      className={cn(option.className, selectedAction.status === option.value && 'ring-2 ring-primary')}
                      disabled={updatingAction || selectedAction.status === option.value}
                      onClick={() => { option.value === 'completed' ? handleCompleteAction() : handleUpdateActionStatus(option.value) }}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
                {actionUpdateError && <p className="text-sm text-destructive mt-2">{actionUpdateError}</p>}
                {updatingAction && (
                  <div className="flex items-center gap-2 mt-2 text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" /><span className="text-sm">Updating...</span>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowActionDetailModal(false)}>Close</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
