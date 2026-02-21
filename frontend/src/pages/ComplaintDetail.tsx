import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
import { complaintsApi, Complaint, ComplaintUpdate, investigationsApi, actionsApi, Action, UserSearchResult, getApiErrorMessage, CreateFromRecordError } from '../api/client'
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

export default function ComplaintDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const [complaint, setComplaint] = useState<Complaint | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [loading, setLoading] = useState(true)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState<ComplaintUpdate>({})

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
  }, [id])

  const loadComplaint = async (complaintId: number) => {
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
    } catch (err) {
      console.error('Failed to load complaint:', err)
      showToast('Failed to load complaint', 'error');
    } finally {
      setLoading(false)
    }
  }

  const loadActions = async () => {
    if (!id) return
    try {
      // Load actions filtered by this specific Complaint
      const response = await actionsApi.list(1, 50)
      // Filter client-side for this complaint's actions
      const complaintActions = (response.data.items || []).filter(
        (a) => a.source_type === 'complaint' && a.source_id === parseInt(id)
      )
      setActions(complaintActions)
    } catch (err) {
      console.error('Failed to load actions:', err)
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
      showToast('Failed to update complaint', 'error');
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

  const [investigationError, setInvestigationError] = useState('')
  const [existingInvestigation, setExistingInvestigation] = useState<{ id: number; reference: string } | null>(null)

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
    } catch (err: unknown) {
      console.error('Failed to create investigation:', err)
      
      // Check for 409 Conflict (already exists)
      const axiosErr = err as { response?: { status?: number; data?: { detail?: unknown } } };
      if (axiosErr.response?.status === 409) {
        const errorData = axiosErr.response?.data?.detail as CreateFromRecordError | undefined
        if (errorData?.error_code === 'INV_ALREADY_EXISTS' && errorData.details?.existing_investigation_id) {
          setExistingInvestigation({
            id: errorData.details.existing_investigation_id,
            reference: errorData.details.existing_reference_number || `INV-${errorData.details.existing_investigation_id}`,
          })
          setInvestigationError('An investigation already exists for this complaint.')
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

  const getPriorityVariant = (priority: string) => {
    switch (priority) {
      case 'critical': return 'critical'
      case 'high': return 'high'
      case 'medium': return 'medium'
      case 'low': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': case 'resolved': return 'resolved'
      case 'received': return 'submitted'
      case 'acknowledged': return 'acknowledged'
      case 'under_investigation': return 'in-progress'
      case 'pending_response': return 'awaiting-user'
      case 'awaiting_customer': return 'awaiting-user'
      case 'escalated': return 'critical'
      default: return 'secondary'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'product': return '📦'
      case 'service': return '🛠️'
      case 'delivery': return '🚚'
      case 'communication': return '📞'
      case 'billing': return '💳'
      case 'staff': return '👤'
      case 'environmental': return '🌿'
      case 'safety': return '⚠️'
      default: return '📋'
    }
  }

  if (loading) {
    return <CardSkeleton count={1} />
  }

  if (!complaint) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <MessageSquare className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">Complaint not found</p>
        <Button variant="outline" onClick={() => navigate('/complaints')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Complaints
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
            onClick={() => navigate('/complaints')}
            aria-label="Back to complaints"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{complaint.reference_number}</span>
              <Badge variant={getPriorityVariant(complaint.priority) as BadgeVariant}>
                {complaint.priority}
              </Badge>
              <Badge variant={getStatusVariant(complaint.status) as BadgeVariant}>
                {complaint.status.replace('_', ' ')}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">{complaint.title}</h1>
            <p className="text-muted-foreground mt-1">
              Received on {new Date(complaint.received_date).toLocaleDateString()}
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
                Complaint Details
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
                      <label className="text-sm font-medium text-muted-foreground">Type</label>
                      <Select
                        value={editForm.complaint_type}
                        onValueChange={(value) => setEditForm({ ...editForm, complaint_type: value })}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="product">Product</SelectItem>
                          <SelectItem value="service">Service</SelectItem>
                          <SelectItem value="delivery">Delivery</SelectItem>
                          <SelectItem value="communication">Communication</SelectItem>
                          <SelectItem value="billing">Billing</SelectItem>
                          <SelectItem value="staff">Staff</SelectItem>
                          <SelectItem value="environmental">Environmental</SelectItem>
                          <SelectItem value="safety">Safety</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Priority</label>
                      <Select
                        value={editForm.priority}
                        onValueChange={(value) => setEditForm({ ...editForm, priority: value })}
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
                    <div className="col-span-2">
                      <label className="text-sm font-medium text-muted-foreground">Status</label>
                      <Select
                        value={editForm.status}
                        onValueChange={(value) => setEditForm({ ...editForm, status: value })}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="received">Received</SelectItem>
                          <SelectItem value="acknowledged">Acknowledged</SelectItem>
                          <SelectItem value="under_investigation">Under Investigation</SelectItem>
                          <SelectItem value="pending_response">Pending Response</SelectItem>
                          <SelectItem value="awaiting_customer">Awaiting Customer</SelectItem>
                          <SelectItem value="escalated">Escalated</SelectItem>
                          <SelectItem value="resolved">Resolved</SelectItem>
                          <SelectItem value="closed">Closed</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Description</label>
                    <p className="mt-1 text-foreground whitespace-pre-wrap">
                      {complaint.description || 'No description provided'}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Type</label>
                      <p className="mt-1 text-foreground capitalize flex items-center gap-2">
                        <span>{getTypeIcon(complaint.complaint_type)}</span>
                        {complaint.complaint_type.replace('_', ' ')}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Priority</label>
                      <p className="mt-1 text-foreground capitalize">{complaint.priority}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Status</label>
                      <p className="mt-1 text-foreground capitalize">{complaint.status.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Received Date</label>
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
                Complainant Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Name</label>
                    <Input
                      value={editForm.complainant_name || ''}
                      onChange={(e) => setEditForm({ ...editForm, complainant_name: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Email</label>
                    <Input
                      type="email"
                      value={editForm.complainant_email || ''}
                      onChange={(e) => setEditForm({ ...editForm, complainant_email: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Phone</label>
                    <Input
                      type="tel"
                      value={editForm.complainant_phone || ''}
                      onChange={(e) => setEditForm({ ...editForm, complainant_phone: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Name</label>
                    <p className="mt-1 text-foreground">{complaint.complainant_name || 'Not specified'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Email</label>
                    <p className="mt-1 text-foreground">{complaint.complainant_email || 'Not specified'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Phone</label>
                    <p className="mt-1 text-foreground">{complaint.complainant_phone || 'Not specified'}</p>
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
                Resolution
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isEditing ? (
                <Textarea
                  value={editForm.resolution_summary || ''}
                  onChange={(e) => setEditForm({ ...editForm, resolution_summary: e.target.value })}
                  rows={4}
                  placeholder="Enter resolution details..."
                />
              ) : (
                <p className="text-foreground whitespace-pre-wrap">
                  {complaint.resolution_summary || 'No resolution recorded yet'}
                </p>
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
                      <Badge variant={action.status === 'completed' ? 'resolved' : 'in-progress' as BadgeVariant}>
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
                    {new Date(complaint.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
                  <Mail className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Email</p>
                  <p className="font-medium text-foreground truncate">{complaint.complainant_email || 'Not specified'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <Phone className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Phone</p>
                  <p className="font-medium text-foreground">{complaint.complainant_phone || 'Not specified'}</p>
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
                    <p className="text-sm font-medium text-foreground">Complaint Received</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(complaint.received_date).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">Record Created</p>
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
              Create a root cause investigation for complaint {complaint.reference_number}.
              Data will be prefilled from the complaint record.
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
                placeholder={`Investigation - ${complaint.reference_number}`}
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
              Create a corrective or follow-up action for this complaint.
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
                placeholder="e.g., Contact customer for follow-up"
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
