import { useEffect, useState } from 'react'
import { Plus, ClipboardCheck, Search, Calendar, MapPin, Target, AlertCircle, CheckCircle2, Clock, BarChart3, Loader2 } from 'lucide-react'
import { auditsApi, AuditRun, AuditFinding } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog'
import { cn } from '../lib/utils'

type ViewMode = 'kanban' | 'list' | 'findings'

const KANBAN_COLUMNS = [
  { id: 'scheduled', label: 'Scheduled', variant: 'info' as const, icon: Calendar },
  { id: 'in_progress', label: 'In Progress', variant: 'warning' as const, icon: Clock },
  { id: 'pending_review', label: 'Pending Review', variant: 'default' as const, icon: Target },
  { id: 'completed', label: 'Completed', variant: 'success' as const, icon: CheckCircle2 },
]

export default function Audits() {
  const [audits, setAudits] = useState<AuditRun[]>([])
  const [findings, setFindings] = useState<AuditFinding[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [auditsRes, findingsRes] = await Promise.all([
        auditsApi.listRuns(1, 100),
        auditsApi.listFindings(1, 100),
      ])
      setAudits(auditsRes.data.items || [])
      setFindings(findingsRes.data.items || [])
    } catch (err) {
      console.error('Failed to load audits:', err)
      setAudits([])
      setFindings([])
    } finally {
      setLoading(false)
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
          <Button onClick={() => setShowModal(true)}>
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
                          {audit.score_percentage !== undefined && (
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
                          {audit.score_percentage !== undefined ? (
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

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule New Audit</DialogTitle>
          </DialogHeader>
          <div className="py-8 text-center">
            <p className="text-muted-foreground">
              Audit scheduling coming soon. Use the API to create audits.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
