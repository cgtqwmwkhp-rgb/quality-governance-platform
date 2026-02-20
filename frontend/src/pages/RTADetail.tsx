import { useEffect, useState } from 'react'
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
import { useToast, ToastContainer } from '../components/ui/Toast'

export default function RTADetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const [rta, setRta] = useState<RTA | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [loading, setLoading] = useState(true)
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
  }, [id])

  const loadRTA = async (rtaId: number) => {
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
      showToast('Failed to load RTA details', 'error');
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
      showToast('Failed to load actions', 'error');
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
          setInvestigationError('An investigation already exists for this RTA.')
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
      showToast('Failed to create action', 'error');
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

  if (!rta) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Car className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">RTA not found</p>
        <Button variant="outline" onClick={() => navigate('/rtas')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to RTAs
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
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
              Reported on {new Date(rta.reported_date).toLocaleDateString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={handleCancelEdit} disabled={saving}>
                <X className="w-4 h-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={handleSaveEdit} disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Save Changes
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                <Pencil className="w-4 h-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add Action
              </Button>
              <Button onClick={() => setShowInvestigationModal(true)}>
                <FlaskConical className="w-4 h-4 mr-2" />
                Start Investigation
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
                Collision Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Title</label>
                    <Input
                      value={editForm.title || ''}
                      onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Description</label>
                    <Textarea
                      value={editForm.description || ''}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                      rows={4}
                      className="mt-1"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Severity</label>
                      <Select
                        value={editForm.severity}
                        onValueChange={(value) => setEditForm({ ...editForm, severity: value })}
                      >
                        <SelectTrigger className="mt-1">
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
                      <label className="text-sm font-medium text-muted-foreground">Status</label>
                      <Select
                        value={editForm.status}
                        onValueChange={(value) => setEditForm({ ...editForm, status: value })}
                      >
                        <SelectTrigger className="mt-1">
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
                      <label className="text-sm font-medium text-muted-foreground">Location</label>
                      <Input
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
                    <label className="text-sm font-medium text-muted-foreground">Description</label>
                    <p className="mt-1 text-foreground whitespace-pre-wrap">
                      {rta.description || 'No description provided'}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Severity</label>
                      <p className="mt-1 text-foreground capitalize">{rta.severity.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Status</label>
                      <p className="mt-1 text-foreground capitalize">{rta.status.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Collision Date</label>
                      <p className="mt-1 text-foreground">
                        {new Date(rta.collision_date).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Location</label>
                      <p className="mt-1 text-foreground">{rta.location || 'Not specified'}</p>
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
                Vehicle & Driver Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Vehicle Registration</label>
                    <Input
                      value={editForm.company_vehicle_registration || ''}
                      onChange={(e) => setEditForm({ ...editForm, company_vehicle_registration: e.target.value })}
                      className="mt-1"
                      placeholder="AB12 CDE"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Driver Name</label>
                    <Input
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
                    <label className="text-sm text-foreground">Driver Injured</label>
                  </div>
                  <div className="flex items-center gap-3 pt-4">
                    <Switch
                      checked={editForm.police_attended || false}
                      onCheckedChange={(checked) => setEditForm({ ...editForm, police_attended: checked })}
                    />
                    <label className="text-sm text-foreground">Police Attended</label>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Vehicle Registration</label>
                    <p className="mt-1 text-foreground">{rta.company_vehicle_registration || 'Not specified'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Driver Name</label>
                    <p className="mt-1 text-foreground">{rta.driver_name || 'Not specified'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Driver Injured</label>
                    <p className="mt-1 text-foreground">{rta.driver_injured ? 'Yes' : 'No'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Police Attended</label>
                    <p className="mt-1 text-foreground">{rta.police_attended ? 'Yes' : 'No'}</p>
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
                Actions ({actions.length})
              </CardTitle>
              <Button variant="outline" size="sm" onClick={() => setShowActionModal(true)}>
                <Plus className="w-4 h-4 mr-1" />
                Add
              </Button>
            </CardHeader>
            <CardContent>
              {actions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No actions yet</p>
                  <p className="text-sm">Create actions to track follow-up tasks</p>
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
                            Due: {action.due_date ? new Date(action.due_date).toLocaleDateString() : 'No due date'}
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
              <CardTitle className="text-base">Quick Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Calendar className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Created</p>
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
                  <p className="text-sm text-muted-foreground">Location</p>
                  <p className="font-medium text-foreground">{rta.location || 'Not specified'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Insurance Notified</p>
                  <p className="font-medium text-foreground">{rta.insurance_notified ? 'Yes' : 'No'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Timeline Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="w-4 h-4" />
                Activity Timeline
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">RTA Reported</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(rta.reported_date).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">Record Created</p>
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
              Start Investigation
            </DialogTitle>
            <DialogDescription>
              Create a root cause investigation for RTA {rta.reference_number}. 
              Data will be prefilled from the collision record.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateInvestigation} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Investigation Title
              </label>
              <Input
                value={investigationForm.title}
                onChange={(e) => setInvestigationForm({ ...investigationForm, title: e.target.value })}
                placeholder={`Investigation - ${rta.reference_number}`}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Investigation Type
              </label>
              <Select
                value={investigationForm.investigation_type}
                onValueChange={(value) => setInvestigationForm({ ...investigationForm, investigation_type: value })}
              >
                <SelectTrigger>
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
              label="Lead Investigator"
              value={investigationForm.lead_investigator}
              onChange={handleInvestigatorChange}
              placeholder="Search by email..."
            />
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Initial Notes
              </label>
              <Textarea
                value={investigationForm.description}
                onChange={(e) => setInvestigationForm({ ...investigationForm, description: e.target.value })}
                placeholder="Describe the scope and initial findings..."
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
                    Open existing investigation ({existingInvestigation.reference})
                  </Button>
                )}
              </div>
            )}
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowInvestigationModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Investigation'}
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
              Add Action
            </DialogTitle>
            <DialogDescription>
              Create a corrective or follow-up action for this road traffic collision.
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
                placeholder="e.g., Review driver training"
                required
              />
            </div>
            <UserEmailSearch
              label="Assign To"
              value={actionForm.assigned_to}
              onChange={handleAssigneeChange}
              placeholder="Search by email..."
              required
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
                placeholder="Describe the action to be taken..."
                rows={3}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowActionModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating || !actionForm.title}>
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Action'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
