import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BarChart3,
  CheckCircle,
  CheckSquare,
  Clock,
  Eye,
  FileText,
  Filter,
  GitBranch,
  MoreVertical,
  RefreshCw,
  Square,
  User,
  UserPlus,
  XCircle,
  AlertTriangle,
} from 'lucide-react'

import {
  getApiErrorMessage,
  type UserDetail,
  type WorkflowApprovalRecord,
  type WorkflowDelegationRecord,
  type WorkflowInstanceRecord,
  type WorkflowTemplateRecord,
  workflowsApi,
  usersApi,
} from '../api/client'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { toast } from '../contexts/ToastContext'
import { cn } from '../helpers/utils'

const priorityVariants: Record<string, 'destructive' | 'warning' | 'info' | 'default'> = {
  critical: 'destructive',
  high: 'warning',
  normal: 'info',
  low: 'default',
}

const statusVariants: Record<
  string,
  'submitted' | 'in-progress' | 'acknowledged' | 'resolved' | 'destructive' | 'warning'
> = {
  pending: 'submitted',
  in_progress: 'in-progress',
  awaiting_approval: 'acknowledged',
  completed: 'resolved',
  rejected: 'destructive',
  escalated: 'warning',
}

const slaColors: Record<string, string> = {
  ok: 'text-success',
  warning: 'text-warning',
  breached: 'text-destructive',
}

export default function WorkflowCenter() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<
    'approvals' | 'workflows' | 'templates' | 'delegation'
  >('approvals')
  const [approvals, setApprovals] = useState<WorkflowApprovalRecord[]>([])
  const [workflows, setWorkflows] = useState<WorkflowInstanceRecord[]>([])
  const [templates, setTemplates] = useState<WorkflowTemplateRecord[]>([])
  const [delegations, setDelegations] = useState<WorkflowDelegationRecord[]>([])
  const [colleagues, setColleagues] = useState<UserDetail[]>([])
  const [selectedApprovals, setSelectedApprovals] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [stats, setStats] = useState({
    pending_approvals: 0,
    active_workflows: 0,
    overdue: 0,
    completed_today: 0,
  })
  const [delegationForm, setDelegationForm] = useState({
    delegate_id: '',
    reason: '',
    start_date: '',
    end_date: '',
  })

  const loadData = useCallback(async () => {
    setLoading(true)
    setRefreshing(true)

    const [
      approvalsResult,
      workflowsResult,
      templatesResult,
      statsResult,
      delegationsResult,
      colleaguesResult,
    ] = await Promise.allSettled([
      workflowsApi.getPendingApprovals(),
      workflowsApi.listInstances(),
      workflowsApi.listTemplates(),
      workflowsApi.getStats(),
      workflowsApi.getDelegations(),
      usersApi.list(1, 50),
    ])

    if (approvalsResult.status === 'fulfilled') {
      setApprovals(approvalsResult.value.data.approvals)
    } else {
      setApprovals([])
    }

    if (workflowsResult.status === 'fulfilled') {
      setWorkflows(workflowsResult.value.data.instances)
    } else {
      setWorkflows([])
    }

    if (templatesResult.status === 'fulfilled') {
      setTemplates(templatesResult.value.data.templates)
    } else {
      setTemplates([])
    }

    if (statsResult.status === 'fulfilled') {
      setStats({
        pending_approvals: statsResult.value.data.pending_approvals,
        active_workflows: statsResult.value.data.active_workflows,
        overdue: statsResult.value.data.overdue,
        completed_today: statsResult.value.data.completed_today,
      })
    } else {
      setStats({
        pending_approvals: 0,
        active_workflows: 0,
        overdue: 0,
        completed_today: 0,
      })
    }

    if (delegationsResult.status === 'fulfilled') {
      setDelegations(delegationsResult.value.data.delegations)
    } else {
      setDelegations([])
    }

    if (colleaguesResult.status === 'fulfilled') {
      setColleagues(colleaguesResult.value.data.items)
    } else {
      setColleagues([])
    }

    const rejected = [
      approvalsResult,
      workflowsResult,
      templatesResult,
      statsResult,
      delegationsResult,
      colleaguesResult,
    ].filter((result) => result.status === 'rejected')

    if (rejected.length > 0) {
      const firstError = rejected[0]
      toast.error(getApiErrorMessage(firstError.reason))
    }

    setLoading(false)
    setRefreshing(false)
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const toggleApprovalSelection = (id: string) => {
    const newSelection = new Set(selectedApprovals)
    if (newSelection.has(id)) {
      newSelection.delete(id)
    } else {
      newSelection.add(id)
    }
    setSelectedApprovals(newSelection)
  }

  const selectAllApprovals = () => {
    if (selectedApprovals.size === approvals.length) {
      setSelectedApprovals(new Set())
    } else {
      setSelectedApprovals(new Set(approvals.map((a) => a.id)))
    }
  }

  const handleBulkApprove = async () => {
    if (selectedApprovals.size === 0) return
    try {
      await workflowsApi.bulkApprove(Array.from(selectedApprovals))
      toast.success(`Approved ${selectedApprovals.size} workflow items`)
      await loadData()
    } catch (error) {
      toast.error(getApiErrorMessage(error))
    }
    setSelectedApprovals(new Set())
  }

  const handleApprove = async (approvalId: string) => {
    try {
      await workflowsApi.approveRequest(approvalId)
      toast.success('Approval completed')
      await loadData()
    } catch (error) {
      toast.error(getApiErrorMessage(error))
    }
  }

  const handleReject = async (approvalId: string) => {
    const reason = window.prompt('Enter a rejection reason')
    if (!reason) return

    try {
      await workflowsApi.rejectRequest(approvalId, { reason })
      toast.success('Approval rejected')
      await loadData()
    } catch (error) {
      toast.error(getApiErrorMessage(error))
    }
  }

  const handleSetDelegation = async () => {
    if (!delegationForm.delegate_id || !delegationForm.start_date || !delegationForm.end_date) {
      toast.error('Select a delegate and both dates before saving')
      return
    }

    try {
      await workflowsApi.setDelegation({
        delegate_id: Number(delegationForm.delegate_id),
        start_date: new Date(`${delegationForm.start_date}T00:00:00`).toISOString(),
        end_date: new Date(`${delegationForm.end_date}T23:59:59`).toISOString(),
        reason: delegationForm.reason || undefined,
      })
      toast.success('Delegation saved')
      setDelegationForm({
        delegate_id: '',
        reason: '',
        start_date: '',
        end_date: '',
      })
      await loadData()
    } catch (error) {
      toast.error(getApiErrorMessage(error))
    }
  }

  const handleCancelDelegation = async (delegationId: string) => {
    try {
      await workflowsApi.cancelDelegation(delegationId)
      toast.success('Delegation cancelled')
      await loadData()
    } catch (error) {
      toast.error(getApiErrorMessage(error))
    }
  }

  const workflowCards = useMemo(
    () =>
      workflows.map((workflow) => {
        const totalSteps = workflow.total_steps || 1
        const currentStepIndex =
          typeof workflow.current_step === 'number'
            ? workflow.current_step + 1
            : Number.parseInt(String(workflow.current_step), 10) || 1
        const progress = Math.max(0, Math.min(100, Math.round((currentStepIndex / totalSteps) * 100)))

        let slaStatus = 'ok'
        if (workflow.sla_breached) {
          slaStatus = 'breached'
        } else if (workflow.sla_due_at) {
          const dueAt = new Date(workflow.sla_due_at).getTime()
          const now = Date.now()
          if (dueAt < now) {
            slaStatus = 'breached'
          } else if (dueAt - now < 24 * 60 * 60 * 1000) {
            slaStatus = 'warning'
          }
        }

        return {
          ...workflow,
          progress,
          currentStepLabel: workflow.current_step_name || `Step ${currentStepIndex} of ${totalSteps}`,
          slaStatus,
        }
      }),
    [workflows],
  )

  const tabs = [
    {
      id: 'approvals',
      label: t('workflows.pending_approvals'),
      icon: CheckCircle,
      count: stats.pending_approvals,
    },
    {
      id: 'workflows',
      label: t('workflows.active_workflows'),
      icon: GitBranch,
      count: stats.active_workflows,
    },
    { id: 'templates', label: 'Templates', icon: FileText },
    { id: 'delegation', label: 'Delegation', icon: UserPlus },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('workflows.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('workflows.subtitle')}</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/20">
                <Clock className="w-5 h-5 text-primary" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">{stats.pending_approvals}</div>
                <div className="text-sm text-muted-foreground">
                  {t('workflows.pending_approvals')}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-info/20">
                <GitBranch className="w-5 h-5 text-info" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">{stats.active_workflows}</div>
                <div className="text-sm text-muted-foreground">
                  {t('workflows.active_workflows')}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-destructive/20">
                <AlertTriangle className="w-5 h-5 text-destructive" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">{stats.overdue}</div>
                <div className="text-sm text-muted-foreground">Overdue</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-success/20">
                <CheckCircle className="w-5 h-5 text-success" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">{stats.completed_today}</div>
                <div className="text-sm text-muted-foreground">
                  {t('workflows.completed_today')}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted/50 p-1 rounded-xl">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all',
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted',
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && (
              <span
                className={cn(
                  'px-2 py-0.5 rounded-full text-xs',
                  activeTab === tab.id ? 'bg-primary-foreground/20' : 'bg-muted',
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Approvals Tab */}
      {activeTab === 'approvals' && (
        <div className="space-y-4">
          {/* Bulk Actions */}
          {selectedApprovals.size > 0 && (
            <div className="flex items-center gap-4 p-4 bg-success/20 border border-success/30 rounded-xl">
              <span className="text-success font-medium">{selectedApprovals.size} selected</span>
              <Button variant="success" onClick={handleBulkApprove}>
                <CheckCircle className="w-4 h-4" />
                {t('workflows.approve_selected')}
              </Button>
              <Button variant="ghost" onClick={() => setSelectedApprovals(new Set())}>
                Cancel
              </Button>
            </div>
          )}

          {/* Approvals List */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={selectAllApprovals}
                  className="text-muted-foreground hover:text-foreground"
                >
                  {selectedApprovals.size === approvals.length ? (
                    <CheckSquare className="w-5 h-5" />
                  ) : (
                    <Square className="w-5 h-5" />
                  )}
                </button>
                <span className="text-foreground font-medium">{t('workflows.all_pending')}</span>
              </div>
              <Button variant="ghost" size="sm">
                <Filter className="w-4 h-4" />
              </Button>
            </CardHeader>

            <div className="divide-y divide-border">
              {approvals.length === 0 && (
                <div className="p-8 text-sm text-muted-foreground">
                  No pending approvals are assigned to you right now.
                </div>
              )}
              {approvals.map((approval) => (
                <div key={approval.id} className="p-4 hover:bg-muted/30 transition-colors">
                  <div className="flex items-start gap-4">
                    <button
                      onClick={() => toggleApprovalSelection(approval.id)}
                      className="mt-1 text-muted-foreground hover:text-foreground"
                    >
                      {selectedApprovals.has(approval.id) ? (
                        <CheckSquare className="w-5 h-5 text-success" />
                      ) : (
                        <Square className="w-5 h-5" />
                      )}
                    </button>

                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="font-medium text-foreground">{approval.entity_title}</h3>
                          <p className="text-sm text-muted-foreground">
                            {approval.workflow_name} • {approval.step_name}
                          </p>
                        </div>
                        <Badge variant={priorityVariants[approval.priority] || 'default'}>
                          {approval.priority}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-muted-foreground">
                          Requested: {new Date(approval.requested_at).toLocaleDateString()}
                        </span>
                        <span
                          className={cn('flex items-center gap-1', slaColors[approval.sla_status] || '')}
                        >
                          <Clock className="w-4 h-4" />
                          Due: {new Date(approval.due_at).toLocaleString()}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 mt-3">
                        <Button
                          variant="success"
                          size="sm"
                          onClick={() => void handleApprove(approval.id)}
                        >
                          <CheckCircle className="w-4 h-4" />
                          Approve
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => void handleReject(approval.id)}
                        >
                          <XCircle className="w-4 h-4" />
                          Reject
                        </Button>
                        <Button variant="secondary" size="sm">
                          <Eye className="w-4 h-4" />
                          {t('workflows.view_details')}
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Workflows Tab */}
      {activeTab === 'workflows' && (
        <div className="space-y-4">
          {workflowCards.length === 0 && (
            <Card>
              <CardContent className="p-8 text-sm text-muted-foreground">
                No active workflow instances are currently visible.
              </CardContent>
            </Card>
          )}
          {workflowCards.map((workflow) => (
            <Card key={workflow.id} className="hover:border-border transition-colors">
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-medium text-foreground">{workflow.template_name}</h3>
                      <Badge variant={statusVariants[workflow.status] || 'default'}>
                        {workflow.status.replace(/_/g, ' ')}
                      </Badge>
                      <Badge variant={priorityVariants[workflow.priority] || 'default'}>
                        {workflow.priority}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {workflow.entity_id} • Started{' '}
                      {new Date(workflow.started_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </div>

                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">
                      Current Step: {workflow.currentStepLabel}
                    </span>
                    <span className={cn('text-sm', slaColors[workflow.slaStatus] || '')}>
                      {workflow.progress}% complete
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        workflow.slaStatus === 'breached'
                          ? 'bg-destructive'
                          : workflow.slaStatus === 'warning'
                            ? 'bg-warning'
                            : 'bg-success',
                      )}
                      style={{ width: `${workflow.progress}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm">
                    <Eye className="w-4 h-4" />
                    {t('workflows.view_details')}
                  </Button>
                  <Button variant="secondary" size="sm">
                    <BarChart3 className="w-4 h-4" />
                    {t('workflows.timeline')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.length === 0 && (
            <Card>
              <CardContent className="p-5 text-sm text-muted-foreground">
                No workflow templates were returned by the backend.
              </CardContent>
            </Card>
          )}
          {templates.map((template) => (
            <Card
              key={template.code}
              className="hover:border-primary/50 transition-colors cursor-pointer"
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="p-2 rounded-lg bg-primary/20">
                    <GitBranch className="w-5 h-5 text-primary" />
                  </div>
                  <Badge variant="default" className="capitalize">
                    {template.category}
                  </Badge>
                </div>
                <h3 className="font-medium text-foreground mb-1">{template.name}</h3>
                <p className="text-sm text-muted-foreground mb-3">{template.description}</p>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {template.steps_count} steps
                  </span>
                  <button className="text-primary hover:text-primary-hover text-sm font-medium">
                    {t('workflows.view_template')}
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Delegation Tab */}
      {activeTab === 'delegation' && (
        <div className="space-y-6">
          <Card>
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                {t('workflows.set_up_delegation')}
              </h3>
              <p className="text-muted-foreground mb-6">
                Configure out-of-office delegation to automatically route your approvals to a
                colleague.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label
                    htmlFor="workflowcenter-field-0"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('workflows.delegate_to')}
                  </label>
                  <Select
                    value={delegationForm.delegate_id}
                    onValueChange={(value) =>
                      setDelegationForm((current) => ({ ...current, delegate_id: value }))
                    }
                  >
                    <SelectTrigger id="workflowcenter-field-0">
                      <SelectValue placeholder="Select a colleague..." />
                    </SelectTrigger>
                    <SelectContent>
                      {colleagues.map((colleague) => (
                        <SelectItem key={colleague.id} value={String(colleague.id)}>
                          {colleague.full_name} - {colleague.department || colleague.job_title || 'User'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label
                    htmlFor="workflowcenter-field-1"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('workflows.reason')}
                  </label>
                  <Input
                    id="workflowcenter-field-1"
                    type="text"
                    placeholder="e.g., Annual leave"
                    value={delegationForm.reason}
                    onChange={(event) =>
                      setDelegationForm((current) => ({ ...current, reason: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="workflowcenter-field-2"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Start Date
                  </label>
                  <Input
                    id="workflowcenter-field-2"
                    type="date"
                    value={delegationForm.start_date}
                    onChange={(event) =>
                      setDelegationForm((current) => ({ ...current, start_date: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="workflowcenter-field-3"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    End Date
                  </label>
                  <Input
                    id="workflowcenter-field-3"
                    type="date"
                    value={delegationForm.end_date}
                    onChange={(event) =>
                      setDelegationForm((current) => ({ ...current, end_date: event.target.value }))
                    }
                  />
                </div>
              </div>

              <Button onClick={() => void handleSetDelegation()}>
                <UserPlus className="w-4 h-4" />
                {t('workflows.set_delegation')}
              </Button>
            </CardContent>
          </Card>

          {/* Current Delegations */}
          <Card>
            <CardHeader>
              <h3 className="font-medium text-foreground">{t('workflows.current_delegations')}</h3>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {delegations.length === 0 && (
                  <div className="text-sm text-muted-foreground">No active delegations are configured.</div>
                )}
                {delegations.map((delegation) => (
                  <div
                    key={delegation.id}
                    className="flex items-center justify-between p-4 bg-muted/30 rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-info/20 rounded-full flex items-center justify-center">
                        <User className="w-5 h-5 text-info" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">
                          {delegation.delegate_name || `User ${delegation.delegate_id}`}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {new Date(delegation.start_date).toLocaleDateString()} -{' '}
                          {new Date(delegation.end_date).toLocaleDateString()}
                          {delegation.reason ? ` • ${delegation.reason}` : ''}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="submitted" className="capitalize">
                        {delegation.status}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleCancelDelegation(delegation.id)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
