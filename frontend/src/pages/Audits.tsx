import { useEffect, useState } from 'react'
import { Plus, ClipboardCheck, Search, Calendar, MapPin, Target, AlertCircle, CheckCircle2, Clock, BarChart3, Loader2, FileText } from 'lucide-react'
import { auditsApi, AuditRun, AuditFinding, AuditTemplate, AuditRunCreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import { cn } from "../helpers/utils"

type ViewMode = 'kanban' | 'list' | 'findings'

// Form state for creating a new audit
interface CreateAuditForm {
  template_id: number | null
  title: string
  location: string
  scheduled_date: string
}

const KANBAN_COLUMNS = [
  { id: 'scheduled', label: 'Scheduled', variant: 'info' as const, icon: Calendar },
  { id: 'in_progress', label: 'In Progress', variant: 'warning' as const, icon: Clock },
  { id: 'pending_review', label: 'Pending Review', variant: 'default' as const, icon: Target },
  { id: 'completed', label: 'Completed', variant: 'success' as const, icon: CheckCircle2 },
]

const INITIAL_FORM_STATE: CreateAuditForm = {
  template_id: null,
  title: '',
  location: '',
  scheduled_date: new Date().toISOString().split('T')[0], // Default to today
}

export default function Audits() {
  const [audits, setAudits] = useState<AuditRun[]>([])
  const [findings, setFindings] = useState<AuditFinding[]>([])
  const [templates, setTemplates] = useState<AuditTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  
  // Form state
  const [formData, setFormData] = useState<CreateAuditForm>(INITIAL_FORM_STATE)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [auditsRes, findingsRes, templatesRes] = await Promise.all([
        auditsApi.listRuns(1, 100),
        auditsApi.listFindings(1, 100),
        auditsApi.listTemplates(1, 100),
      ])
      setAudits(auditsRes.data.items || [])
      setFindings(findingsRes.data.items || [])
      // Only show published templates
      setTemplates((templatesRes.data.items || []).filter(t => t.is_published))
    } catch (err) {
      console.error('Failed to load audits:', err)
      setAudits([])
      setFindings([])
      setTemplates([])
    } finally {
      setLoading(false)
    }
  }

  const handleOpenModal = () => {
    setFormData(INITIAL_FORM_STATE)
    setFormError(null)
    setSuccessMessage(null)
    setShowModal(true)
  }

  const handleCloseModal = () => {
    setShowModal(false)
    setFormData(INITIAL_FORM_STATE)
    setFormError(null)
  }

  const handleSubmitAudit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    
    // Validation
    if (!formData.template_id) {
      setFormError('Please select an audit template')
      return
    }
    
    setIsSubmitting(true)
    
    try {
      const payload: AuditRunCreate = {
        template_id: formData.template_id,
        title: formData.title || undefined,
        location: formData.location || undefined,
        scheduled_date: formData.scheduled_date || undefined,
      }
      
      const response = await auditsApi.createRun(payload)
      
      // Success - show message and refresh list
      setSuccessMessage(`Audit scheduled successfully! Reference: ${response.data.reference_number}`)
      
      // Refresh the audit list
      await loadData()
      
      // Close modal after short delay to show success (STATIC_UI_CONFIG_OK: UX delay, not mock)
      setTimeout(() => {
        handleCloseModal()
        setSuccessMessage(null)
      }, 2000)
      
    } catch (err: any) {
      console.error('Failed to create audit:', err)
      const errorMessage = err.response?.data?.detail || 'Failed to schedule audit. Please try again.'
      setFormError(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  const getAuditsByStatus = (status: string) => {
    return audits.filter(a => a.status === status)
  }

  const getScoreColor = (percentage?: number) => {
    if (!percentage) return 'text-muted-foreground'
    if (percentage >= 90) return 'text-success'
    if (percentage >= 70) return 'text-warning'
    return 'text-destructive'
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'critical': return 'critical'
      case 'high': return 'high'
      case 'medium': return 'medium'
      case 'low': return 'low'
      case 'observation': return 'info'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': return 'resolved'
      case 'open': return 'destructive'
      case 'in_progress': return 'in-progress'
      case 'pending_verification': return 'acknowledged'
      case 'deferred': return 'secondary'
      default: return 'secondary'
    }
  }

  const stats = {
    total: audits.length,
    inProgress: audits.filter(a => a.status === 'in_progress').length,
    completed: audits.filter(a => a.status === 'completed').length,
    avgScore: audits.filter(a => a.score_percentage).reduce((acc, a) => acc + (a.score_percentage || 0), 0) / 
              (audits.filter(a => a.score_percentage).length || 1),
    openFindings: findings.filter(f => f.status === 'open').length,
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
          <h1 className="text-3xl font-bold text-foreground">
            Audit Management
          </h1>
          <p className="text-muted-foreground mt-1">Internal audits, inspections & compliance checks</p>
        </div>
        <div className="flex items-center gap-3">
          {/* View Toggle */}
          <div className="flex bg-surface rounded-xl p-1 border border-border">
            {(['kanban', 'list', 'findings'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                  viewMode === mode 
                    ? 'bg-primary text-primary-foreground shadow-sm' 
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {mode === 'kanban' ? 'Board' : mode === 'findings' ? 'Findings' : 'List'}
              </button>
            ))}
          </div>
          <Button onClick={handleOpenModal}>
            <Plus size={20} />
            New Audit
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Total Audits', value: stats.total, icon: ClipboardCheck, variant: 'info' as const },
          { label: 'In Progress', value: stats.inProgress, icon: Clock, variant: 'warning' as const },
          { label: 'Completed', value: stats.completed, icon: CheckCircle2, variant: 'success' as const },
          { label: 'Avg Score', value: `${stats.avgScore.toFixed(0)}%`, icon: BarChart3, variant: 'primary' as const },
          { label: 'Open Findings', value: stats.openFindings, icon: AlertCircle, variant: 'destructive' as const },
        ].map((stat) => (
          <Card 
            key={stat.label}
            hoverable
            className="p-5"
          >
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center mb-3",
              stat.variant === 'info' && "bg-info/10 text-info",
              stat.variant === 'warning' && "bg-warning/10 text-warning",
              stat.variant === 'success' && "bg-success/10 text-success",
              stat.variant === 'primary' && "bg-primary/10 text-primary",
              stat.variant === 'destructive' && "bg-destructive/10 text-destructive",
            )}>
              <stat.icon className="w-5 h-5" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
          </Card>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search audits..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Kanban View */}
      {viewMode === 'kanban' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {KANBAN_COLUMNS.map((column) => {
            const columnAudits = getAuditsByStatus(column.id)
            return (
              <div key={column.id}>
                {/* Column Header */}
                <div className="flex items-center gap-3 mb-4">
                  <div className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center",
                    column.variant === 'info' && "bg-info/10 text-info",
                    column.variant === 'warning' && "bg-warning/10 text-warning",
                    column.variant === 'success' && "bg-success/10 text-success",
                    column.variant === 'default' && "bg-primary/10 text-primary",
                  )}>
                    <column.icon className="w-4 h-4" />
                  </div>
                  <h3 className="font-semibold text-foreground">{column.label}</h3>
                  <Badge variant="secondary" className="ml-auto">
                    {columnAudits.length}
                  </Badge>
                </div>

                {/* Column Content */}
                <div className="space-y-3 min-h-[200px] bg-surface rounded-2xl p-3 border border-border">
                  {columnAudits.length === 0 ? (
                    <div className="flex items-center justify-center h-32 text-muted-foreground">
                      <p className="text-sm">No audits</p>
                    </div>
                  ) : (
                    columnAudits.map((audit) => (
                      <Card
                        key={audit.id}
                        hoverable
                        className="p-4 cursor-pointer"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <span className="font-mono text-xs text-primary">{audit.reference_number}</span>
                          {audit.score_percentage != null && (
                            <span className={cn("text-sm font-bold", getScoreColor(audit.score_percentage))}>
                              {audit.score_percentage.toFixed(0)}%
                            </span>
                          )}
                        </div>
                        <h4 className="font-medium text-foreground text-sm mb-2 line-clamp-2">
                          {audit.title || 'Untitled Audit'}
                        </h4>
                        {audit.location && (
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
                            <MapPin size={12} />
                            <span className="truncate">{audit.location}</span>
                          </div>
                        )}
                        {audit.scheduled_date && (
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Calendar size={12} />
                            <span>{new Date(audit.scheduled_date).toLocaleDateString()}</span>
                          </div>
                        )}
                      </Card>
                    ))
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Reference</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Title</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Location</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Score</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {audits.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                        <ClipboardCheck className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                        <p>No audits found</p>
                      </td>
                    </tr>
                  ) : (
                    audits.map((audit) => (
                      <tr
                        key={audit.id}
                        className="hover:bg-surface transition-colors cursor-pointer"
                      >
                        <td className="px-6 py-4">
                          <span className="font-mono text-sm text-primary">{audit.reference_number}</span>
                        </td>
                        <td className="px-6 py-4">
                          <p className="text-sm font-medium text-foreground truncate max-w-xs">{audit.title || 'Untitled'}</p>
                        </td>
                        <td className="px-6 py-4 text-sm text-foreground">{audit.location || '-'}</td>
                        <td className="px-6 py-4">
                          <Badge variant={
                            audit.status === 'completed' ? 'resolved' :
                            audit.status === 'in_progress' ? 'in-progress' :
                            audit.status === 'pending_review' ? 'acknowledged' :
                            'submitted'
                          }>
                            {audit.status.replace('_', ' ')}
                          </Badge>
                        </td>
                        <td className="px-6 py-4">
                          {audit.score_percentage != null ? (
                            <span className={cn("font-bold", getScoreColor(audit.score_percentage))}>
                              {audit.score_percentage.toFixed(0)}%
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {audit.scheduled_date ? new Date(audit.scheduled_date).toLocaleDateString() : '-'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Findings View */}
      {viewMode === 'findings' && (
        <div className="space-y-4">
          {findings.length === 0 ? (
            <Card className="p-12 text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <p className="text-muted-foreground">No findings recorded</p>
            </Card>
          ) : (
            findings.map((finding) => (
              <Card
                key={finding.id}
                hoverable
                className="p-5"
              >
                <div className="flex items-start gap-4">
                  <div className={cn(
                    "w-12 h-12 rounded-xl flex items-center justify-center",
                    finding.severity === 'critical' && 'bg-destructive/10 text-destructive',
                    finding.severity === 'high' && 'bg-warning/10 text-warning',
                    finding.severity === 'medium' && 'bg-warning/10 text-warning',
                    finding.severity === 'low' && 'bg-success/10 text-success',
                    !['critical', 'high', 'medium', 'low'].includes(finding.severity) && 'bg-info/10 text-info',
                  )}>
                    <AlertCircle className="w-6 h-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-xs text-primary">{finding.reference_number}</span>
                      <Badge variant={getSeverityVariant(finding.severity) as any}>
                        {finding.severity}
                      </Badge>
                      <Badge variant={getStatusVariant(finding.status) as any}>
                        {finding.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <h3 className="font-semibold text-foreground mb-1">{finding.title}</h3>
                    <p className="text-sm text-muted-foreground line-clamp-2">{finding.description}</p>
                    {finding.corrective_action_due_date && (
                      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                        <Calendar size={14} />
                        <span>Due: {new Date(finding.corrective_action_due_date).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Create Audit Modal */}
      <Dialog open={showModal} onOpenChange={handleCloseModal}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardCheck className="w-5 h-5 text-primary" />
              Schedule New Audit
            </DialogTitle>
            <DialogDescription>
              Select a published template and schedule an audit run.
            </DialogDescription>
          </DialogHeader>
          
          {successMessage ? (
            <div className="py-8 text-center">
              <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-success" />
              </div>
              <p className="text-lg font-semibold text-foreground mb-2">Audit Scheduled!</p>
              <p className="text-muted-foreground">{successMessage}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmitAudit} className="space-y-5">
              {/* Template Selection */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Audit Template <span className="text-destructive">*</span>
                </label>
                {templates.length === 0 ? (
                  <div className="p-4 rounded-xl bg-warning/10 border border-warning/20">
                    <p className="text-sm text-warning">
                      No published templates available. Please create and publish a template first.
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-2 max-h-48 overflow-y-auto">
                    {templates.map((template) => (
                      <button
                        key={template.id}
                        type="button"
                        onClick={() => setFormData(prev => ({ 
                          ...prev, 
                          template_id: template.id,
                          title: prev.title || template.name
                        }))}
                        className={cn(
                          "flex items-start gap-3 p-3 rounded-xl border text-left transition-all",
                          formData.template_id === template.id
                            ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                            : "border-border hover:border-primary/50 hover:bg-surface"
                        )}
                      >
                        <div className={cn(
                          "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                          formData.template_id === template.id
                            ? "bg-primary text-primary-foreground"
                            : "bg-surface text-muted-foreground"
                        )}>
                          <FileText className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-foreground truncate">{template.name}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {template.category || template.audit_type} • {template.reference_number}
                          </p>
                        </div>
                        {formData.template_id === template.id && (
                          <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Title */}
              <div className="space-y-2">
                <label htmlFor="audit-title" className="text-sm font-medium text-foreground">
                  Audit Title
                </label>
                <Input
                  id="audit-title"
                  type="text"
                  placeholder="e.g., Q1 2026 Safety Inspection - Site A"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                  maxLength={300}
                />
                <p className="text-xs text-muted-foreground">Optional. Defaults to template name.</p>
              </div>

              {/* Location */}
              <div className="space-y-2">
                <label htmlFor="audit-location" className="text-sm font-medium text-foreground">
                  Location
                </label>
                <Input
                  id="audit-location"
                  type="text"
                  placeholder="e.g., Warehouse B, Office Floor 3"
                  value={formData.location}
                  onChange={(e) => setFormData(prev => ({ ...prev, location: e.target.value }))}
                  maxLength={200}
                />
              </div>

              {/* Scheduled Date */}
              <div className="space-y-2">
                <label htmlFor="audit-date" className="text-sm font-medium text-foreground">
                  Scheduled Date
                </label>
                <Input
                  id="audit-date"
                  type="date"
                  value={formData.scheduled_date}
                  onChange={(e) => setFormData(prev => ({ ...prev, scheduled_date: e.target.value }))}
                  min={new Date().toISOString().split('T')[0]}
                />
              </div>

              {/* Error Message */}
              {formError && (
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-destructive">{formError}</p>
                </div>
              )}

              {/* Footer */}
              <DialogFooter className="gap-2 sm:gap-0">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCloseModal}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting || templates.length === 0 || !formData.template_id}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Scheduling...
                    </>
                  ) : (
                    <>
                      <Calendar className="w-4 h-4" />
                      Schedule Audit
                    </>
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
