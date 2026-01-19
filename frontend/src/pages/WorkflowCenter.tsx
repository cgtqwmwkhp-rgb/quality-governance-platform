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

import { useState, useEffect } from 'react';
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

const priorityColors: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  normal: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  low: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  in_progress: 'bg-blue-500/20 text-blue-400',
  awaiting_approval: 'bg-purple-500/20 text-purple-400',
  completed: 'bg-emerald-500/20 text-emerald-400',
  rejected: 'bg-red-500/20 text-red-400',
  escalated: 'bg-orange-500/20 text-orange-400',
};

const slaColors: Record<string, string> = {
  ok: 'text-emerald-400',
  warning: 'text-yellow-400',
  breached: 'text-red-400',
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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    await new Promise(resolve => setTimeout(resolve, 500));

    setApprovals([
      {
        id: 'APR-001',
        workflow_id: 'WF-20260119001',
        workflow_name: 'RIDDOR Reporting',
        step_name: 'Management Sign-off',
        entity_type: 'incident',
        entity_id: 'INC-2026-0042',
        entity_title: 'Slip and fall incident - Site A',
        requested_at: '2026-01-19T10:00:00Z',
        due_at: '2026-01-19T14:00:00Z',
        priority: 'high',
        sla_status: 'warning',
      },
      {
        id: 'APR-002',
        workflow_id: 'WF-20260119002',
        workflow_name: 'Document Approval',
        step_name: 'Quality Review',
        entity_type: 'document',
        entity_id: 'DOC-POL-012',
        entity_title: 'Updated Safety Policy v2.1',
        requested_at: '2026-01-18T15:00:00Z',
        due_at: '2026-01-20T15:00:00Z',
        priority: 'normal',
        sla_status: 'ok',
      },
      {
        id: 'APR-003',
        workflow_id: 'WF-20260118003',
        workflow_name: 'CAPA Workflow',
        step_name: 'Effectiveness Verification',
        entity_type: 'action',
        entity_id: 'ACT-2026-0089',
        entity_title: 'Update PPE inspection procedure',
        requested_at: '2026-01-17T09:00:00Z',
        due_at: '2026-01-19T09:00:00Z',
        priority: 'critical',
        sla_status: 'breached',
      },
    ]);

    setWorkflows([
      {
        id: 'WF-20260119001',
        template_code: 'RIDDOR',
        template_name: 'RIDDOR Reporting',
        entity_type: 'incident',
        entity_id: 'INC-2026-0042',
        status: 'awaiting_approval',
        priority: 'high',
        current_step: 'Management Sign-off',
        progress: 75,
        sla_status: 'warning',
        started_at: '2026-01-19T08:00:00Z',
      },
      {
        id: 'WF-20260118002',
        template_code: 'CAPA',
        template_name: 'Corrective/Preventive Action',
        entity_type: 'action',
        entity_id: 'ACT-2026-0105',
        status: 'in_progress',
        priority: 'normal',
        current_step: 'Implementation',
        progress: 50,
        sla_status: 'ok',
        started_at: '2026-01-18T10:00:00Z',
      },
    ]);

    setTemplates([
      { code: 'RIDDOR', name: 'RIDDOR Reporting', description: 'Mandatory HSE notification', category: 'regulatory', steps_count: 4 },
      { code: 'CAPA', name: 'Corrective/Preventive Action', description: 'Track corrective actions', category: 'quality', steps_count: 4 },
      { code: 'NCR', name: 'Non-Conformance Report', description: 'Handle non-conformances', category: 'quality', steps_count: 4 },
      { code: 'INCIDENT_INVESTIGATION', name: 'Incident Investigation', description: 'Structured investigation', category: 'safety', steps_count: 6 },
      { code: 'DOCUMENT_APPROVAL', name: 'Document Approval', description: 'Review and approve documents', category: 'documents', steps_count: 3 },
    ]);

    setStats({
      pending_approvals: 3,
      active_workflows: 12,
      overdue: 1,
      completed_today: 5,
    });

    setLoading(false);
  };

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
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Workflow Center</h1>
          <p className="text-gray-400 mt-1">Manage approvals, workflows, and automations</p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <Clock className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{stats.pending_approvals}</div>
              <div className="text-sm text-gray-400">Pending Approvals</div>
            </div>
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20">
              <GitBranch className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{stats.active_workflows}</div>
              <div className="text-sm text-gray-400">Active Workflows</div>
            </div>
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-500/20">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{stats.overdue}</div>
              <div className="text-sm text-gray-400">Overdue</div>
            </div>
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20">
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{stats.completed_today}</div>
              <div className="text-sm text-gray-400">Completed Today</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/50 p-1 rounded-xl">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-emerald-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && (
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                activeTab === tab.id ? 'bg-white/20' : 'bg-slate-700'
              }`}>
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
            <div className="flex items-center gap-4 p-4 bg-emerald-600/20 border border-emerald-500/30 rounded-xl">
              <span className="text-emerald-400 font-medium">
                {selectedApprovals.size} selected
              </span>
              <button
                onClick={handleBulkApprove}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
              >
                <CheckCircle className="w-4 h-4" />
                Approve Selected
              </button>
              <button
                onClick={() => setSelectedApprovals(new Set())}
                className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Approvals List */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={selectAllApprovals}
                  className="text-gray-400 hover:text-white"
                >
                  {selectedApprovals.size === approvals.length ? (
                    <CheckSquare className="w-5 h-5" />
                  ) : (
                    <Square className="w-5 h-5" />
                  )}
                </button>
                <span className="text-white font-medium">All Pending Approvals</span>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-slate-700">
                  <Filter className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="divide-y divide-slate-700">
              {approvals.map(approval => (
                <div
                  key={approval.id}
                  className="p-4 hover:bg-slate-700/30 transition-colors"
                >
                  <div className="flex items-start gap-4">
                    <button
                      onClick={() => toggleApprovalSelection(approval.id)}
                      className="mt-1 text-gray-400 hover:text-white"
                    >
                      {selectedApprovals.has(approval.id) ? (
                        <CheckSquare className="w-5 h-5 text-emerald-400" />
                      ) : (
                        <Square className="w-5 h-5" />
                      )}
                    </button>

                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="font-medium text-white">{approval.entity_title}</h3>
                          <p className="text-sm text-gray-400">
                            {approval.workflow_name} • {approval.step_name}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded text-xs font-medium border ${priorityColors[approval.priority]}`}>
                            {approval.priority}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-gray-400">
                          Requested: {new Date(approval.requested_at).toLocaleDateString()}
                        </span>
                        <span className={`flex items-center gap-1 ${slaColors[approval.sla_status]}`}>
                          <Clock className="w-4 h-4" />
                          Due: {new Date(approval.due_at).toLocaleString()}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 mt-3">
                        <button className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors">
                          <CheckCircle className="w-4 h-4" />
                          Approve
                        </button>
                        <button className="flex items-center gap-2 px-3 py-1.5 bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white rounded-lg text-sm transition-colors">
                          <XCircle className="w-4 h-4" />
                          Reject
                        </button>
                        <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors">
                          <Eye className="w-4 h-4" />
                          View Details
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Workflows Tab */}
      {activeTab === 'workflows' && (
        <div className="space-y-4">
          {workflows.map(workflow => (
            <div
              key={workflow.id}
              className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 hover:border-slate-600 transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-medium text-white">{workflow.template_name}</h3>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[workflow.status]}`}>
                      {workflow.status.replace(/_/g, ' ')}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium border ${priorityColors[workflow.priority]}`}>
                      {workflow.priority}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400">{workflow.entity_id} • Started {new Date(workflow.started_at).toLocaleDateString()}</p>
                </div>
                <button className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-slate-700">
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>

              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">Current Step: {workflow.current_step}</span>
                  <span className={`text-sm ${slaColors[workflow.sla_status]}`}>{workflow.progress}% complete</span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      workflow.sla_status === 'breached' ? 'bg-red-500' :
                      workflow.sla_status === 'warning' ? 'bg-yellow-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${workflow.progress}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors">
                  <Eye className="w-4 h-4" />
                  View Details
                </button>
                <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors">
                  <BarChart3 className="w-4 h-4" />
                  Timeline
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map(template => (
            <div
              key={template.code}
              className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 hover:border-emerald-500/50 transition-colors cursor-pointer"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="p-2 rounded-lg bg-emerald-500/20">
                  <GitBranch className="w-5 h-5 text-emerald-400" />
                </div>
                <span className="px-2 py-1 bg-slate-700 rounded text-xs text-gray-300 capitalize">
                  {template.category}
                </span>
              </div>
              <h3 className="font-medium text-white mb-1">{template.name}</h3>
              <p className="text-sm text-gray-400 mb-3">{template.description}</p>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">{template.steps_count} steps</span>
                <button className="text-emerald-400 hover:text-emerald-300 text-sm font-medium">
                  View Template →
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delegation Tab */}
      {activeTab === 'delegation' && (
        <div className="space-y-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Set Up Delegation</h3>
            <p className="text-gray-400 mb-6">
              Configure out-of-office delegation to automatically route your approvals to a colleague.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Delegate To</label>
                <select className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white">
                  <option value="">Select a colleague...</option>
                  <option value="2">Jane Smith - Safety Manager</option>
                  <option value="3">Bob Johnson - Quality Manager</option>
                  <option value="4">Alice Brown - Operations Director</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Reason</label>
                <input
                  type="text"
                  placeholder="e.g., Annual leave"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-gray-400"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Start Date</label>
                <input
                  type="date"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">End Date</label>
                <input
                  type="date"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
            </div>

            <button className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors">
              <UserPlus className="w-4 h-4" />
              Set Delegation
            </button>
          </div>

          {/* Current Delegations */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-700">
              <h3 className="font-medium text-white">Current & Scheduled Delegations</h3>
            </div>
            <div className="p-4">
              <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-500/20 rounded-full flex items-center justify-center">
                    <User className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Jane Smith</p>
                    <p className="text-sm text-gray-400">Jan 20 - Jan 27, 2026 • Annual leave</p>
                  </div>
                </div>
                <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs font-medium">
                  Scheduled
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
