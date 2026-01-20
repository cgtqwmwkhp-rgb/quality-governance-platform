import { useEffect, useState } from 'react'
import { Search, ListTodo, Plus, Calendar, User, Flag, CheckCircle2, Clock, AlertCircle, ArrowUpRight, Filter, Loader2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { cn } from '../lib/utils'

interface Action {
  id: number
  reference_number: string
  title: string
  description: string
  action_type: string
  priority: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'in_progress' | 'pending_verification' | 'completed' | 'cancelled'
  due_date?: string
  completed_at?: string
  source_type: string
  source_ref: string
  owner?: string
  created_at: string
}

type ViewMode = 'all' | 'my' | 'overdue'
type FilterStatus = 'all' | 'open' | 'in_progress' | 'pending_verification' | 'completed'

const MOCK_ACTIONS: Action[] = [
  {
    id: 1,
    reference_number: 'ACT-2026-0001',
    title: 'Update fire safety procedures',
    description: 'Review and update all fire safety procedures following the recent incident',
    action_type: 'corrective',
    priority: 'high',
    status: 'in_progress',
    due_date: '2026-02-15',
    source_type: 'incident',
    source_ref: 'INC-2026-0042',
    owner: 'John Smith',
    created_at: '2026-01-10',
  },
  {
    id: 2,
    reference_number: 'ACT-2026-0002',
    title: 'Install additional CCTV cameras',
    description: 'Install CCTV coverage in blind spots identified during security audit',
    action_type: 'preventive',
    priority: 'medium',
    status: 'open',
    due_date: '2026-03-01',
    source_type: 'audit',
    source_ref: 'AUD-2026-0015',
    owner: 'Security Team',
    created_at: '2026-01-12',
  },
  {
    id: 3,
    reference_number: 'ACT-2026-0003',
    title: 'Driver re-training program',
    description: 'Mandatory defensive driving training for all fleet drivers',
    action_type: 'corrective',
    priority: 'critical',
    status: 'pending_verification',
    due_date: '2026-01-25',
    source_type: 'rta',
    source_ref: 'RTA-2026-0008',
    owner: 'Fleet Manager',
    created_at: '2026-01-08',
  },
  {
    id: 4,
    reference_number: 'ACT-2026-0004',
    title: 'Customer communication protocol review',
    description: 'Update customer communication templates and response SLAs',
    action_type: 'improvement',
    priority: 'low',
    status: 'completed',
    due_date: '2026-01-20',
    completed_at: '2026-01-18',
    source_type: 'complaint',
    source_ref: 'CMP-2026-0023',
    owner: 'Customer Service',
    created_at: '2026-01-05',
  },
]

export default function Actions() {
  const [actions] = useState<Action[]>(MOCK_ACTIONS)
  const [loading, setLoading] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('all')
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    setLoading(false)
  }, [])

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
      case 'completed': return 'resolved'
      case 'open': return 'submitted'
      case 'in_progress': return 'in-progress'
      case 'pending_verification': return 'acknowledged'
      case 'cancelled': return 'closed'
      default: return 'secondary'
    }
  }

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'incident': return '🔥'
      case 'audit': return '📋'
      case 'rta': return '🚗'
      case 'complaint': return '💬'
      case 'risk': return '⚠️'
      default: return '📌'
    }
  }

  const isOverdue = (dueDate?: string, status?: string) => {
    if (!dueDate || status === 'completed' || status === 'cancelled') return false
    return new Date(dueDate) < new Date()
  }

  const filteredActions = actions.filter(action => {
    if (searchTerm && !action.title.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !action.reference_number.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false
    }
    if (filterStatus !== 'all' && action.status !== filterStatus) {
      return false
    }
    if (viewMode === 'overdue' && !isOverdue(action.due_date, action.status)) {
      return false
    }
    return true
  })

  const stats = {
    total: actions.length,
    open: actions.filter(a => a.status === 'open').length,
    inProgress: actions.filter(a => a.status === 'in_progress').length,
    overdue: actions.filter(a => isOverdue(a.due_date, a.status)).length,
    completed: actions.filter(a => a.status === 'completed').length,
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
          <h1 className="text-3xl font-bold text-foreground">Action Center</h1>
          <p className="text-muted-foreground mt-1">Cross-module corrective & preventive actions</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Action
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Total Actions', value: stats.total, icon: ListTodo, variant: 'primary' as const },
          { label: 'Open', value: stats.open, icon: AlertCircle, variant: 'info' as const },
          { label: 'In Progress', value: stats.inProgress, icon: Clock, variant: 'warning' as const },
          { label: 'Overdue', value: stats.overdue, icon: Flag, variant: 'destructive' as const },
          { label: 'Completed', value: stats.completed, icon: CheckCircle2, variant: 'success' as const },
        ].map((stat) => (
          <Card 
            key={stat.label}
            hoverable
            className={cn(
              "p-5",
              stat.label === 'Overdue' && stats.overdue > 0 && "border-destructive/30"
            )}
          >
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center mb-3",
              stat.variant === 'primary' && "bg-primary/10 text-primary",
              stat.variant === 'info' && "bg-info/10 text-info",
              stat.variant === 'warning' && "bg-warning/10 text-warning",
              stat.variant === 'destructive' && "bg-destructive/10 text-destructive",
              stat.variant === 'success' && "bg-success/10 text-success",
            )}>
              <stat.icon className="w-5 h-5" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
            {stat.label === 'Overdue' && stats.overdue > 0 && (
              <div className="absolute top-3 right-3 w-3 h-3 bg-destructive rounded-full animate-pulse" />
            )}
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search actions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        <div className="flex bg-surface rounded-xl p-1 border border-border">
          {(['all', 'my', 'overdue'] as ViewMode[]).map((mode) => (
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
              {mode === 'my' ? 'My Actions' : mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>

        <Select value={filterStatus} onValueChange={(value) => setFilterStatus(value as FilterStatus)}>
          <SelectTrigger className="w-[180px]">
            <Filter className="w-4 h-4 mr-2" />
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="pending_verification">Pending Verification</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Actions List */}
      <div className="space-y-4">
        {filteredActions.length === 0 ? (
          <Card className="p-12 text-center">
            <ListTodo className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">No Actions Found</h3>
            <p className="text-muted-foreground">
              {filterStatus !== 'all' || viewMode !== 'all' 
                ? 'Try adjusting your filters' 
                : 'Actions from incidents, audits, and investigations will appear here'}
            </p>
          </Card>
        ) : (
          filteredActions.map((action) => {
            const overdue = isOverdue(action.due_date, action.status)
            
            return (
              <Card
                key={action.id}
                hoverable
                className={cn(
                  "overflow-hidden",
                  overdue && "border-destructive/30"
                )}
              >
                <div className="flex items-stretch">
                  <div className={cn(
                    "w-1.5",
                    action.priority === 'critical' && "bg-destructive",
                    action.priority === 'high' && "bg-warning",
                    action.priority === 'medium' && "bg-warning/70",
                    action.priority === 'low' && "bg-success",
                  )} />
                  
                  <CardContent className="flex-1 p-5">
                    <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                          <span className="font-mono text-sm text-primary">{action.reference_number}</span>
                          <Badge variant={getPriorityVariant(action.priority) as any}>
                            {action.priority}
                          </Badge>
                          <Badge variant={getStatusVariant(action.status) as any}>
                            {action.status.replace('_', ' ')}
                          </Badge>
                          {overdue && (
                            <Badge variant="destructive" className="animate-pulse">
                              OVERDUE
                            </Badge>
                          )}
                        </div>
                        <h3 className="text-lg font-semibold text-foreground mb-1">
                          {action.title}
                        </h3>
                        <p className="text-sm text-muted-foreground line-clamp-1">{action.description}</p>
                      </div>

                      <div className="flex flex-wrap lg:flex-col items-start lg:items-end gap-2 lg:gap-1 lg:w-48 flex-shrink-0">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface rounded-lg">
                          <span className="text-lg">{getSourceIcon(action.source_type)}</span>
                          <span className="text-xs font-mono text-muted-foreground">{action.source_ref}</span>
                          <ArrowUpRight className="w-3 h-3 text-muted-foreground" />
                        </div>

                        {action.due_date && (
                          <div className={cn(
                            "flex items-center gap-2 text-sm",
                            overdue ? 'text-destructive' : 'text-muted-foreground'
                          )}>
                            <Calendar className="w-4 h-4" />
                            <span>Due {new Date(action.due_date).toLocaleDateString()}</span>
                          </div>
                        )}

                        {action.owner && (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <User className="w-4 h-4" />
                            <span>{action.owner}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </div>
              </Card>
            )
          })
        )}
      </div>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Action</DialogTitle>
          </DialogHeader>
          <form className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Title</label>
              <Input placeholder="Action title..." />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description</label>
              <Textarea rows={3} placeholder="Describe the action required..." />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Priority</label>
                <Select defaultValue="medium">
                  <SelectTrigger>
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
                <label className="block text-sm font-medium text-foreground mb-2">Due Date</label>
                <Input type="date" />
              </div>
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                Cancel
              </Button>
              <Button type="submit">
                Create Action
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
