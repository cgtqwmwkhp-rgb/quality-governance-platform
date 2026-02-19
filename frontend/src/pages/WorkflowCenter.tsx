/**
 * Workflow Center
 * 
 * Features:
 * - Pending approvals management
 * - Bulk actions
 * - Workflow tracking
 * - Delegation management
 * - Template library
 */

import { useState, useEffect, useCallback } from 'react';
import {
  GitBranch,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  User,
  Filter,
  RefreshCw,
  CheckSquare,
  Square,
  FileText,
  MoreVertical,
  Eye,
  UserPlus,
  BarChart3,
} from 'lucide-react';
import { cn } from "../helpers/utils";
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardHeader, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/Select';
import { workflowsApi } from '../api/client';

interface Approval {
  id: string;
  workflow_id: string;
  workflow_name: string;
  step_name: string;
  entity_type: string;
  entity_id: string;
  entity_title: string;
  requested_at: string;
  due_at: string;
  priority: string;
  sla_status: string;
}

interface WorkflowInstance {
  id: string;
  template_code: string;
  template_name: string;
  entity_type: string;
  entity_id: string;
  status: string;
  priority: string;
  current_step: string;
  progress: number;
  sla_status: string;
  started_at: string;
}

interface WorkflowTemplate {
  code: string;
  name: string;
  description: string;
  category: string;
  steps_count: number;
}

const priorityVariants: Record<string, 'destructive' | 'warning' | 'info' | 'default'> = {
  critical: 'destructive',
  high: 'warning',
  normal: 'info',
  low: 'default',
};

const statusVariants: Record<string, 'submitted' | 'in-progress' | 'acknowledged' | 'resolved' | 'destructive' | 'warning'> = {
  pending: 'submitted',
  in_progress: 'in-progress',
  awaiting_approval: 'acknowledged',
  completed: 'resolved',
  rejected: 'destructive',
  escalated: 'warning',
};

const slaColors: Record<string, string> = {
  ok: 'text-success',
  warning: 'text-warning',
  breached: 'text-destructive',
};

export default function WorkflowCenter() {
  const [activeTab, setActiveTab] = useState<'approvals' | 'workflows' | 'templates' | 'delegation'>('approvals');
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowInstance[]>([]);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [selectedApprovals, setSelectedApprovals] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    pending_approvals: 0,
    active_workflows: 0,
    overdue: 0,
    completed_today: 0,
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [approvalsRes, workflowsRes, templatesRes, statsRes] = await Promise.allSettled([
        workflowsApi.getPendingApprovals(),
        workflowsApi.listInstances({ page: 1, size: 50 }),
        workflowsApi.listTemplates(),
        workflowsApi.getStats(),
      ]);

      if (approvalsRes.status === 'fulfilled') {
        const items = Array.isArray(approvalsRes.value.data) ? approvalsRes.value.data : [];
        setApprovals(items.map((a: any) => ({
          id: String(a.id),
          workflow_id: String(a.workflow_id || ''),
          workflow_name: a.workflow_name || a.template_name || 'Workflow',
          step_name: a.step_name || a.current_step || '',
          entity_type: a.entity_type || '',
          entity_id: a.entity_id || '',
          entity_title: a.entity_title || a.title || '',
          requested_at: a.requested_at || a.created_at || '',
          due_at: a.due_at || '',
          priority: a.priority || 'normal',
          sla_status: a.sla_status || 'ok',
        })));
      }

      if (workflowsRes.status === 'fulfilled') {
        const data = workflowsRes.value.data;
        const items = Array.isArray(data) ? data : (data?.items || []);
        setWorkflows(items.map((w: any) => ({
          id: String(w.id),
          template_code: w.template_code || '',
          template_name: w.template_name || '',
          entity_type: w.entity_type || '',
          entity_id: w.entity_id || '',
          status: w.status || 'pending',
          priority: w.priority || 'normal',
          current_step: w.current_step || '',
          progress: w.progress || 0,
          sla_status: w.sla_status || 'ok',
          started_at: w.started_at || w.created_at || '',
        })));
      }

      if (templatesRes.status === 'fulfilled') {
        const items = Array.isArray(templatesRes.value.data) ? templatesRes.value.data : [];
        setTemplates(items.map((t: any) => ({
          code: t.code || t.template_code || '',
          name: t.name || '',
          description: t.description || '',
          category: t.category || 'general',
          steps_count: t.steps_count || (t.steps?.length || 0),
        })));
      }

      if (statsRes.status === 'fulfilled' && statsRes.value.data) {
        const s = statsRes.value.data;
        setStats({
          pending_approvals: s.pending_approvals ?? 0,
          active_workflows: s.active_workflows ?? 0,
          overdue: s.overdue ?? 0,
          completed_today: s.completed_today ?? 0,
        });
      } else {
        setStats({
          pending_approvals: approvals.length,
          active_workflows: workflows.length,
          overdue: 0,
          completed_today: 0,
        });
      }
    } catch (err) {
      console.error('Failed to load workflow data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const toggleApprovalSelection = (id: string) => {
    const newSelection = new Set(selectedApprovals);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedApprovals(newSelection);
  };

  const selectAllApprovals = () => {
    if (selectedApprovals.size === approvals.length) {
      setSelectedApprovals(new Set());
    } else {
      setSelectedApprovals(new Set(approvals.map(a => a.id)));
    }
  };

  const handleBulkApprove = () => {
    alert(`Approving ${selectedApprovals.size} items...`);
    setSelectedApprovals(new Set());
  };

  const tabs = [
    { id: 'approvals', label: 'Pending Approvals', icon: CheckCircle, count: stats.pending_approvals },
    { id: 'workflows', label: 'Active Workflows', icon: GitBranch, count: stats.active_workflows },
    { id: 'templates', label: 'Templates', icon: FileText },
    { id: 'delegation', label: 'Delegation', icon: UserPlus },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Workflow Center</h1>
          <p className="text-muted-foreground mt-1">Manage approvals, workflows, and automations</p>
        </div>
        <Button variant="secondary" onClick={loadData}>
          <RefreshCw className="w-4 h-4" />
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
                <div className="text-sm text-muted-foreground">Pending Approvals</div>
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
                <div className="text-sm text-muted-foreground">Active Workflows</div>
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
                <div className="text-sm text-muted-foreground">Completed Today</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted/50 p-1 rounded-xl">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && (
              <span className={cn(
                "px-2 py-0.5 rounded-full text-xs",
                activeTab === tab.id ? 'bg-primary-foreground/20' : 'bg-muted'
              )}>
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
              <span className="text-success font-medium">
                {selectedApprovals.size} selected
              </span>
              <Button variant="success" onClick={handleBulkApprove}>
                <CheckCircle className="w-4 h-4" />
                Approve Selected
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
                <span className="text-foreground font-medium">All Pending Approvals</span>
              </div>
              <Button variant="ghost" size="sm">
                <Filter className="w-4 h-4" />
              </Button>
            </CardHeader>

            <div className="divide-y divide-border">
              {approvals.map(approval => (
                <div
                  key={approval.id}
                  className="p-4 hover:bg-muted/30 transition-colors"
                >
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
                        <Badge variant={priorityVariants[approval.priority]}>
                          {approval.priority}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-muted-foreground">
                          Requested: {new Date(approval.requested_at).toLocaleDateString()}
                        </span>
                        <span className={cn("flex items-center gap-1", slaColors[approval.sla_status])}>
                          <Clock className="w-4 h-4" />
                          Due: {new Date(approval.due_at).toLocaleString()}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 mt-3">
                        <Button variant="success" size="sm">
                          <CheckCircle className="w-4 h-4" />
                          Approve
                        </Button>
                        <Button variant="destructive" size="sm">
                          <XCircle className="w-4 h-4" />
                          Reject
                        </Button>
                        <Button variant="secondary" size="sm">
                          <Eye className="w-4 h-4" />
                          View Details
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
          {workflows.map(workflow => (
            <Card key={workflow.id} className="hover:border-border transition-colors">
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-medium text-foreground">{workflow.template_name}</h3>
                      <Badge variant={statusVariants[workflow.status]}>
                        {workflow.status.replace(/_/g, ' ')}
                      </Badge>
                      <Badge variant={priorityVariants[workflow.priority]}>
                        {workflow.priority}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{workflow.entity_id} • Started {new Date(workflow.started_at).toLocaleDateString()}</p>
                  </div>
                  <Button variant="ghost" size="sm">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </div>

                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">Current Step: {workflow.current_step}</span>
                    <span className={cn("text-sm", slaColors[workflow.sla_status])}>{workflow.progress}% complete</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        workflow.sla_status === 'breached' ? 'bg-destructive' :
                        workflow.sla_status === 'warning' ? 'bg-warning' : 'bg-success'
                      )}
                      style={{ width: `${workflow.progress}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm">
                    <Eye className="w-4 h-4" />
                    View Details
                  </Button>
                  <Button variant="secondary" size="sm">
                    <BarChart3 className="w-4 h-4" />
                    Timeline
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
          {templates.map(template => (
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
                  <span className="text-sm text-muted-foreground">{template.steps_count} steps</span>
                  <button className="text-primary hover:text-primary-hover text-sm font-medium">
                    View Template →
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
              <h3 className="text-lg font-semibold text-foreground mb-4">Set Up Delegation</h3>
              <p className="text-muted-foreground mb-6">
                Configure out-of-office delegation to automatically route your approvals to a colleague.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Delegate To</label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a colleague..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="2">Jane Smith - Safety Manager</SelectItem>
                      <SelectItem value="3">Bob Johnson - Quality Manager</SelectItem>
                      <SelectItem value="4">Alice Brown - Operations Director</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Reason</label>
                  <Input type="text" placeholder="e.g., Annual leave" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Start Date</label>
                  <Input type="date" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">End Date</label>
                  <Input type="date" />
                </div>
              </div>

              <Button>
                <UserPlus className="w-4 h-4" />
                Set Delegation
              </Button>
            </CardContent>
          </Card>

          {/* Current Delegations */}
          <Card>
            <CardHeader>
              <h3 className="font-medium text-foreground">Current & Scheduled Delegations</h3>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-info/20 rounded-full flex items-center justify-center">
                    <User className="w-5 h-5 text-info" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">Jane Smith</p>
                    <p className="text-sm text-muted-foreground">Jan 20 - Jan 27, 2026 • Annual leave</p>
                  </div>
                </div>
                <Badge variant="submitted">
                  Scheduled
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
