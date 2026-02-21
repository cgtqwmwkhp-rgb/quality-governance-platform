import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
  History,
  Pencil,
  Save,
  X,
  ExternalLink,
} from 'lucide-react'
import { incidentsApi, Incident, IncidentUpdate, investigationsApi, actionsApi, Action, UserSearchResult, getApiErrorMessage, CreateFromRecordError } from '../api/client'
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
import { cn } from '../helpers/utils'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { UserEmailSearch } from '../components/UserEmailSearch'
import { useToast, ToastContainer } from '../components/ui/Toast'

// Status options for action updates
const ACTION_STATUS_OPTIONS = [
  { value: 'open', label: 'Open', className: 'bg-blue-100 text-blue-800 hover:bg-blue-200' },
  { value: 'in_progress', label: 'In Progress', className: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200' },
  { value: 'pending_verification', label: 'Pending Verification', className: 'bg-purple-100 text-purple-800 hover:bg-purple-200' },
  { value: 'completed', label: 'Completed', className: 'bg-green-100 text-green-800 hover:bg-green-200' },
  { value: 'cancelled', label: 'Cancelled', className: 'bg-gray-100 text-gray-800 hover:bg-gray-200' },
]

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const [incident, setIncident] = useState<Incident | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [loading, setLoading] = useState(true)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState<IncidentUpdate>({})
  
  // Action detail modal state
  const [selectedAction, setSelectedAction] = useState<Action | null>(null)
  const [showActionDetailModal, setShowActionDetailModal] = useState(false)
  const [updatingAction, setUpdatingAction] = useState(false)
  const [actionUpdateError, setActionUpdateError] = useState('')

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
  }, [id])

  const loadIncident = async (incidentId: number) => {
    try {
      const response = await incidentsApi.get(incidentId)
      setIncident(response.data)
      setEditForm({
        title: response.data.title,
        description: response.data.description,
        incident_type: response.data.incident_type,
        severity: response.data.severity,
        status: response.data.status,
        location: response.data.location,
        department: response.data.department,
      })
      loadActions()
    } catch (err) {
      console.error('Failed to load incident:', err)
      showToast('Failed to load incident', 'error');
    } finally {
      setLoading(false)
    }
  }

  const loadActions = async () => {
    if (!id) return
    try {
      // Load actions filtered by this specific incident
      const response = await actionsApi.list(1, 50)
      // Filter client-side for this incident's actions
      const incidentActions = (response.data.items || []).filter(
        (a) => a.source_type === 'incident' && a.source_id === parseInt(id)
      )
      setActions(incidentActions)
    } catch (err) {
      console.error('Failed to load actions:', err)
    }
  }

  const handleSaveEdit = async () => {
    if (!incident) return
    setSaving(true)
    try {
      const response = await incidentsApi.update(incident.id, editForm)
      setIncident(response.data)
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to update incident:', err)
      showToast('Failed to update incident', 'error');
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    if (incident) {
      setEditForm({
        title: incident.title,
        description: incident.description,
        incident_type: incident.incident_type,
        severity: incident.severity,
        status: incident.status,
        location: incident.location,
        department: incident.department,
      })
    }
    setIsEditing(false)
  }

  const [investigationError, setInvestigationError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{ id: number; reference: string } | null>(null)

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!incident) return
    setCreating(true)
    setInvestigationError('')
    setExistingInvestigation(null)
    
    try {
      // Use from-record endpoint with proper JSON body
      await investigationsApi.createFromRecord({
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
      navigate('/investigations')
    } catch (err: unknown) {
      console.error('Failed to create investigation:', err)
      showToast('Failed to create investigation', 'error');
      
      // Check for 409 Conflict (already exists)
      const axiosErr = err as { response?: { status?: number; data?: { detail?: unknown } } };
      if (axiosErr.response?.status === 409) {
        const errorData = axiosErr.response?.data?.detail as CreateFromRecordError | undefined
        if (errorData?.error_code === 'INV_ALREADY_EXISTS' && errorData.details?.existing_investigation_id) {
          setExistingInvestigation({
            id: errorData.details.existing_investigation_id,
            reference: errorData.details.existing_reference_number || `INV-${errorData.details.existing_investigation_id}`,
          })
          setInvestigationError('An investigation already exists for this incident.')
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
      setActions(prev => prev.map(a => a.id === selectedAction.id ? response.data : a))
    } catch (err) {
      console.error('Failed to update action status:', err)
      showToast('Failed to update action status', 'error');
      setActionUpdateError(getApiErrorMessage(err))
    } finally {
      setUpdatingAction(false)
    }
  }

  const handleCompleteAction = () => {
    const notes = window.prompt('Enter completion notes (optional):')
    handleUpdateActionStatus('completed', notes || undefined)
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'critical': return 'critical'
      case 'high': return 'high'
      case 'medium': return 'medium'
      case 'low': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'open': return 'destructive'
      case 'under_investigation': return 'in-progress'
      case 'pending_actions': return 'acknowledged'
      case 'closed': return 'resolved'
      default: return 'secondary'
    }
  }

  if (loading) {
    return <CardSkeleton count={1} />
  }

  if (!incident) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">Incident not found</p>
        <Button variant="outline" onClick={() => navigate('/incidents')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Incidents
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
            onClick={() => navigate('/incidents')}
            aria-label="Back to incidents"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{incident.reference_number}</span>
              <Badge variant={getSeverityVariant(incident.severity) as BadgeVariant}>
                {incident.severity}
              </Badge>
              <Badge variant={getStatusVariant(incident.status) as BadgeVariant}>
                {incident.status.replace('_', ' ')}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">{incident.title}</h1>
            <p className="text-muted-foreground mt-1">
              Reported on {new Date(incident.reported_date).toLocaleDateString()}
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
                Incident Details
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
                      <label className="text-sm font-medium text-muted-foreground">Incident Type</label>
                      <Select
                        value={editForm.incident_type}
                        onValueChange={(value) => setEditForm({ ...editForm, incident_type: value })}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="safety">Safety</SelectItem>
                          <SelectItem value="environmental">Environmental</SelectItem>
                          <SelectItem value="quality">Quality</SelectItem>
                          <SelectItem value="security">Security</SelectItem>
                          <SelectItem value="near_miss">Near Miss</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
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
                          <SelectItem value="critical">Critical</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="low">Low</SelectItem>
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
                          <SelectItem value="open">Open</SelectItem>
                          <SelectItem value="under_investigation">Under Investigation</SelectItem>
                          <SelectItem value="pending_actions">Pending Actions</SelectItem>
                          <SelectItem value="closed">Closed</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
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
                      {incident.description || 'No description provided'}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Incident Type</label>
                      <p className="mt-1 text-foreground capitalize">{incident.incident_type.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Severity</label>
                      <p className="mt-1 text-foreground capitalize">{incident.severity}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Incident Date</label>
                      <p className="mt-1 text-foreground">
                        {new Date(incident.incident_date).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Location</label>
                      <p className="mt-1 text-foreground">{incident.location || 'Not specified'}</p>
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
                      className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border cursor-pointer hover:bg-accent/50 transition-colors"
                      onClick={() => handleOpenAction(action)}
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
                      <div className="flex items-center gap-2">
                        <Badge variant={
                          action.status === 'completed' ? 'resolved' :
                          action.status === 'cancelled' ? 'destructive' :
                          action.status === 'in_progress' ? 'in-progress' :
                          'secondary' as BadgeVariant
                        }>
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
                    {new Date(incident.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
                  <MapPin className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Location</p>
                  <p className="font-medium text-foreground">{incident.location || 'Not specified'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <User className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Department</p>
                  <p className="font-medium text-foreground">{incident.department || 'Not specified'}</p>
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
                    <p className="text-sm font-medium text-foreground">Incident Reported</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(incident.reported_date).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">Record Created</p>
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
              Create a root cause investigation for incident {incident.reference_number}.
              Data will be prefilled from the incident record.
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
                placeholder={`Investigation - ${incident.reference_number}`}
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
              Create a corrective or follow-up action for this incident.
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
                placeholder="e.g., Review safety procedures"
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

      {/* Action Detail Modal */}
      <Dialog open={showActionDetailModal} onOpenChange={setShowActionDetailModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-primary" />
              Action Details
            </DialogTitle>
            <DialogDescription>
              View and update action status
            </DialogDescription>
          </DialogHeader>
          
          {selectedAction && (
            <div className="space-y-4">
              {/* Action Info */}
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Title</label>
                  <p className="font-medium text-foreground">{selectedAction.title}</p>
                </div>
                
                {selectedAction.description && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Description</label>
                    <p className="text-foreground">{selectedAction.description}</p>
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Status</label>
                    <Badge 
                      variant={
                        selectedAction.status === 'completed' ? 'resolved' :
                        selectedAction.status === 'cancelled' ? 'destructive' :
                        selectedAction.status === 'in_progress' ? 'in-progress' :
                        'secondary' as BadgeVariant
                      }
                      className="mt-1"
                    >
                      {selectedAction.status.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Priority</label>
                    <p className="text-foreground capitalize">{selectedAction.priority}</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Due Date</label>
                    <p className="text-foreground">
                      {selectedAction.due_date 
                        ? new Date(selectedAction.due_date).toLocaleDateString() 
                        : 'Not set'}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Assigned To</label>
                    <p className="text-foreground">
                      {selectedAction.assigned_to_email || 'Unassigned'}
                    </p>
                  </div>
                </div>
                
                {selectedAction.completed_at && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Completed At</label>
                    <p className="text-foreground">
                      {new Date(selectedAction.completed_at).toLocaleString()}
                    </p>
                  </div>
                )}
                
                {selectedAction.completion_notes && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Completion Notes</label>
                    <p className="text-foreground">{selectedAction.completion_notes}</p>
                  </div>
                )}
              </div>
              
              {/* Status Update Section */}
              <div className="border-t pt-4">
                <label className="text-sm font-medium text-muted-foreground mb-2 block">
                  Update Status
                </label>
                <div className="flex flex-wrap gap-2">
                  {ACTION_STATUS_OPTIONS.map((option) => (
                    <Button
                      key={option.value}
                      size="sm"
                      variant="outline"
                      className={cn(
                        option.className,
                        selectedAction.status === option.value && 'ring-2 ring-primary'
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

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
