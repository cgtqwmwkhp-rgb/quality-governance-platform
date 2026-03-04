import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
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
} from 'lucide-react'
import { rtasApi, RTA, RTAUpdate, investigationsApi, actionsApi, Action, UserSearchResult, getApiErrorMessage, CreateFromRecordError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Textarea } from '../components/ui/Textarea'
import { Input } from '../components/ui/Input'
import { Switch } from '../components/ui/Switch'
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
  const [rta, setRta] = useState<RTA | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState<RTAUpdate>({})

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
      loadRTA(parseInt(id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const loadRTA = async (rtaId: number) => {
    setError(null)
    try {
      const response = await rtasApi.get(rtaId)
      setRta(response.data)
      setEditForm({
        title: response.data.title,
        description: response.data.description,
        severity: response.data.severity,
        status: response.data.status,
        location: response.data.location,
        driver_name: response.data.driver_name,
        company_vehicle_registration: response.data.company_vehicle_registration,
        police_attended: response.data.police_attended,
        driver_injured: response.data.driver_injured,
      })
      loadActions()
    } catch (err) {
      console.error('Failed to load RTA:', err)
      setError(t('rtas.detail.load_error'))
    } finally {
      setLoading(false)
    }
  }

  const loadActions = async () => {
    if (!id) return
    try {
      // Load actions filtered by this specific RTA
      const response = await actionsApi.list(1, 50)
      // Filter client-side for this RTA's actions
      const rtaActions = (response.data.items || []).filter(
        (a) => a.source_type === 'rta' && a.source_id === parseInt(id)
      )
      setActions(rtaActions)
    } catch (err) {
      console.error('Failed to load actions:', err)
      setError(t('rtas.detail.load_error'))
    }
  }

  const handleSaveEdit = async () => {
    if (!rta) return
    setSaving(true)
    try {
      const response = await rtasApi.update(rta.id, editForm)
      setRta(response.data)
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to update RTA:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    if (rta) {
      setEditForm({
        title: rta.title,
        description: rta.description,
        severity: rta.severity,
        status: rta.status,
        location: rta.location,
        driver_name: rta.driver_name,
        company_vehicle_registration: rta.company_vehicle_registration,
        police_attended: rta.police_attended,
        driver_injured: rta.driver_injured,
      })
    }
    setIsEditing(false)
  }

  const [investigationError, setInvestigationError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{ id: number; reference: string } | null>(null)

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!rta) return
    setCreating(true)
    setInvestigationError('')
    setExistingInvestigation(null)
    
    try {
      // Use from-record endpoint with proper JSON body
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
      console.error('Failed to create investigation:', err)
      
      // Check for 409 Conflict (already exists)
      if (err.response?.status === 409) {
        const errorData = err.response?.data?.detail as CreateFromRecordError | undefined
        if (errorData?.error_code === 'INV_ALREADY_EXISTS' && errorData.details?.existing_investigation_id) {
          setExistingInvestigation({
            id: errorData.details.existing_investigation_id,
            reference: errorData.details.existing_reference_number || `INV-${errorData.details.existing_investigation_id}`,
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
      setActionForm({
        title: '',
        description: '',
        priority: 'medium',
        due_date: '',
        assigned_to: '',
      })
      loadActions()
    } catch (err: unknown) {
      console.error('Failed to create action:', err)
      alert(`Failed to create action: ${getApiErrorMessage(err)}`)
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

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'fatal': return 'critical'
      case 'serious_injury': return 'critical'
      case 'minor_injury': return 'high'
      case 'damage_only': return 'medium'
      case 'near_miss': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': return 'resolved'
      case 'reported': return 'submitted'
      case 'under_investigation': return 'in-progress'
      case 'pending_insurance': return 'acknowledged'
      case 'pending_actions': return 'awaiting-user'
      default: return 'secondary'
    }
  }

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
        <button onClick={() => { setError(null); loadRTA(parseInt(id!)); }} className="text-sm font-medium text-destructive hover:underline">
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

  return (
    <div className="space-y-6 animate-fade-in">
      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => { setError(null); loadRTA(parseInt(id!)); }} className="text-sm font-medium text-destructive hover:underline">
            {t('rtas.detail.try_again')}
          </button>
        </div>
      )}
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button 
            variant="outline" 
            size="icon"
            onClick={() => navigate('/rtas')}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{rta.reference_number}</span>
              <Badge variant={getSeverityVariant(rta.severity) as any}>
                {rta.severity.replace('_', ' ')}
              </Badge>
              <Badge variant={getStatusVariant(rta.status) as any}>
                {rta.status.replace('_', ' ')}
              </Badge>
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
                <X className="w-4 h-4 mr-2" />
                {t('cancel')}
              </Button>
              <Button onClick={handleSaveEdit} disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                {t('rtas.detail.save_changes')}
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
                {t('rtas.detail.add_action')}
              </Button>
              <Button onClick={() => setShowInvestigationModal(true)}>
                <FlaskConical className="w-4 h-4 mr-2" />
                {t('rtas.detail.start_investigation')}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description Card */}
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
                    <label htmlFor="rtadetail-field-0" className="text-sm font-medium text-muted-foreground">{t('rtas.detail.title_label')}</label>
                    <Input id="rtadetail-field-0"
                      value={editForm.title || ''}
                      onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label htmlFor="rtadetail-field-1" className="text-sm font-medium text-muted-foreground">{t('common.description')}</label>
                    <Textarea id="rtadetail-field-1"
                      value={editForm.description || ''}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                      rows={4}
                      className="mt-1"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="rtadetail-field-2" className="text-sm font-medium text-muted-foreground">{t('rtas.detail.severity')}</label>
                      <Select
                        value={editForm.severity}
                        onValueChange={(value) => setEditForm({ ...editForm, severity: value })}
                      >
                        <SelectTrigger id="rtadetail-field-2" className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
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
                      <label htmlFor="rtadetail-field-3" className="text-sm font-medium text-muted-foreground">{t('common.status')}</label>
                      <Select
                        value={editForm.status}
                        onValueChange={(value) => setEditForm({ ...editForm, status: value })}
                      >
                        <SelectTrigger id="rtadetail-field-3" className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
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
                      <label htmlFor="rtadetail-field-4" className="text-sm font-medium text-muted-foreground">{t('common.location')}</label>
                      <Input id="rtadetail-field-4"
                        value={editForm.location || ''}
                        onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                        className="mt-1"
                      />
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">{t('common.description')}</span>
                    <p className="mt-1 text-foreground whitespace-pre-wrap">
                      {rta.description || t('rtas.detail.no_description')}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">{t('rtas.detail.severity')}</span>
                      <p className="mt-1 text-foreground capitalize">{rta.severity.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">{t('common.status')}</span>
                      <p className="mt-1 text-foreground capitalize">{rta.status.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">{t('rtas.detail.collision_date')}</span>
                      <p className="mt-1 text-foreground">
                        {new Date(rta.collision_date).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-muted-foreground">{t('common.location')}</span>
                      <p className="mt-1 text-foreground">{rta.location || t('rtas.detail.not_specified')}</p>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Vehicle & Driver Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Car className="w-5 h-5 text-primary" />
                {t('rtas.detail.vehicle_driver_info')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="rtadetail-field-5" className="text-sm font-medium text-muted-foreground">{t('rtas.detail.vehicle_registration')}</label>
                    <Input id="rtadetail-field-5"
                      value={editForm.company_vehicle_registration || ''}
                      onChange={(e) => setEditForm({ ...editForm, company_vehicle_registration: e.target.value })}
                      className="mt-1"
                      placeholder="AB12 CDE"
                    />
                  </div>
                  <div>
                    <label htmlFor="rtadetail-field-6" className="text-sm font-medium text-muted-foreground">{t('rtas.detail.driver_name')}</label>
                    <Input id="rtadetail-field-6"
                      value={editForm.driver_name || ''}
                      onChange={(e) => setEditForm({ ...editForm, driver_name: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div className="flex items-center gap-3 pt-4">
                    <Switch
                      checked={editForm.driver_injured || false}
                      onCheckedChange={(checked) => setEditForm({ ...editForm, driver_injured: checked })}
                    />
                    <span className="text-sm text-foreground">{t('rtas.detail.driver_injured')}</span>
                  </div>
                  <div className="flex items-center gap-3 pt-4">
                    <Switch
                      checked={editForm.police_attended || false}
                      onCheckedChange={(checked) => setEditForm({ ...editForm, police_attended: checked })}
                    />
                    <span className="text-sm text-foreground">{t('rtas.detail.police_attended')}</span>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">{t('rtas.detail.vehicle_registration')}</span>
                    <p className="mt-1 text-foreground">{rta.company_vehicle_registration || t('rtas.detail.not_specified')}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">{t('rtas.detail.driver_name')}</span>
                    <p className="mt-1 text-foreground">{rta.driver_name || t('rtas.detail.not_specified')}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">{t('rtas.detail.driver_injured')}</span>
                    <p className="mt-1 text-foreground">{rta.driver_injured ? t('common.yes') : t('common.no')}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-muted-foreground">{t('rtas.detail.police_attended')}</span>
                    <p className="mt-1 text-foreground">{rta.police_attended ? t('common.yes') : t('common.no')}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Actions Card */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-primary" />
                {t('rtas.detail.actions_count', { count: actions.length })}
              </CardTitle>
              <Button variant="outline" size="sm" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-1" />
                {t('common.add')}
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
                  {actions.slice(0, 5).map((action) => (
                    <div
                      key={action.id}
                      className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border"
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "w-8 h-8 rounded-lg flex items-center justify-center",
                          action.status === 'completed' ? 'bg-success/10 text-success' :
                          action.status === 'cancelled' ? 'bg-destructive/10 text-destructive' :
                          'bg-warning/10 text-warning'
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
                      <Badge variant={action.status === 'completed' ? 'resolved' : 'in-progress' as any}>
                        {action.status}
                      </Badge>
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
              <CardTitle className="text-base">{t('rtas.detail.quick_info')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Calendar className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('rtas.detail.created')}</p>
                  <p className="font-medium text-foreground">
                    {new Date(rta.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
                  <MapPin className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('common.location')}</p>
                  <p className="font-medium text-foreground">{rta.location || t('rtas.detail.not_specified')}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('rtas.detail.insurance_notified')}</p>
                  <p className="font-medium text-foreground">{rta.insurance_notified ? t('common.yes') : t('common.no')}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Timeline Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="w-4 h-4" />
                {t('rtas.detail.activity_timeline')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">{t('rtas.detail.rta_reported')}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(rta.reported_date).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">{t('rtas.detail.record_created')}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(rta.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Create Investigation Modal */}
      <Dialog open={showInvestigationModal} onOpenChange={(open) => {
        setShowInvestigationModal(open)
        if (!open) {
          setInvestigationError('')
          setExistingInvestigation(null)
        }
      }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-primary" />
              {t('rtas.detail.start_investigation')}
            </DialogTitle>
            <DialogDescription>
              {t('rtas.detail.investigation_description', { reference: rta.reference_number })}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateInvestigation} className="space-y-4">
            <div>
              <label htmlFor="rtadetail-field-7" className="block text-sm font-medium text-foreground mb-1">
                {t('rtas.detail.investigation_title')}
              </label>
              <Input id="rtadetail-field-7"
                value={investigationForm.title}
                onChange={(e) => setInvestigationForm({ ...investigationForm, title: e.target.value })}
                placeholder={`Investigation - ${rta.reference_number}`}
              />
            </div>
            <div>
              <label htmlFor="rtadetail-field-8" className="block text-sm font-medium text-foreground mb-1">
                {t('rtas.detail.investigation_type')}
              </label>
              <Select
                value={investigationForm.investigation_type}
                onValueChange={(value) => setInvestigationForm({ ...investigationForm, investigation_type: value })}
              >
                <SelectTrigger id="rtadetail-field-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="root_cause_analysis">Root Cause Analysis</SelectItem>
                  <SelectItem value="5_whys">5 Whys</SelectItem>
                  <SelectItem value="fishbone">Fishbone Analysis</SelectItem>
                  <SelectItem value="incident_review">Incident Review</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <UserEmailSearch
              label={t('rtas.detail.lead_investigator')}
              value={investigationForm.lead_investigator}
              onChange={handleInvestigatorChange}
              placeholder={t('rtas.detail.search_by_email')}
            />
            <div>
              <label htmlFor="rtadetail-field-9" className="block text-sm font-medium text-foreground mb-1">
                {t('rtas.detail.initial_notes')}
              </label>
              <Textarea id="rtadetail-field-9"
                value={investigationForm.description}
                onChange={(e) => setInvestigationForm({ ...investigationForm, description: e.target.value })}
                placeholder={t('rtas.detail.initial_notes_placeholder')}
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
                    {t('rtas.detail.open_existing_investigation', { reference: existingInvestigation.reference })}
                  </Button>
                )}
              </div>
            )}
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowInvestigationModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : t('rtas.detail.create_investigation')}
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
              {t('rtas.detail.add_action')}
            </DialogTitle>
            <DialogDescription>
              {t('rtas.detail.add_action_description')}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label htmlFor="rtadetail-field-10" className="block text-sm font-medium text-foreground mb-1">
                {t('rtas.detail.action_title_required')}
              </label>
              <Input id="rtadetail-field-10"
                value={actionForm.title}
                onChange={(e) => setActionForm({ ...actionForm, title: e.target.value })}
                placeholder={t('rtas.detail.action_title_placeholder')}
                required
              />
            </div>
            <UserEmailSearch
              label={t('rtas.detail.assign_to')}
              value={actionForm.assigned_to}
              onChange={handleAssigneeChange}
              placeholder={t('rtas.detail.search_by_email')}
              required
            />
            <div>
              <label htmlFor="rtadetail-field-11" className="block text-sm font-medium text-foreground mb-1">
                {t('common.priority')}
              </label>
              <Select
                value={actionForm.priority}
                onValueChange={(value) => setActionForm({ ...actionForm, priority: value })}
              >
                <SelectTrigger id="rtadetail-field-11">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label htmlFor="rtadetail-field-12" className="block text-sm font-medium text-foreground mb-1">
                {t('rtas.detail.due_date')}
              </label>
              <Input id="rtadetail-field-12"
                type="date"
                value={actionForm.due_date}
                onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="rtadetail-field-13" className="block text-sm font-medium text-foreground mb-1">
                {t('common.description')}
              </label>
              <Textarea id="rtadetail-field-13"
                value={actionForm.description}
                onChange={(e) => setActionForm({ ...actionForm, description: e.target.value })}
                placeholder={t('rtas.detail.action_description_placeholder')}
                rows={3}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowActionModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating || !actionForm.title}>
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : t('rtas.detail.create_action')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
