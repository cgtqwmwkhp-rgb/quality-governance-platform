/**
 * Workflows API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

export interface WorkflowApprovalRecord {
  id: string
  workflow_id: string
  workflow_name: string
  step_name: string
  entity_type: string
  entity_id: string
  entity_title: string
  requested_at: string
  due_at: string
  priority: string
  sla_status: string
}

export interface WorkflowInstanceRecord {
  id: string
  template_code: string
  template_name: string
  entity_type: string
  entity_id: string
  status: string
  priority: string
  current_step: number | string
  current_step_name?: string | null
  total_steps?: number
  started_at: string
  sla_due_at?: string | null
  sla_breached?: boolean
}

export interface WorkflowTemplateRecord {
  code: string
  name: string
  description: string
  category: string
  trigger_entity_type: string
  sla_hours?: number | null
  steps_count: number
}

export interface WorkflowDelegationRecord {
  id: string
  delegate_id: number
  delegate_name?: string | null
  start_date: string
  end_date: string
  reason?: string | null
  status: string
  workflow_types?: string[]
}

/**
 * Workflow Center KPIs. Every figure except `pending_approvals` is nullable because
 * the workflow engine persists no instances and therefore cannot measure them; null
 * means "unmeasured" and must render as such, never as zero.
 */
export interface WorkflowStatsResponse {
  /** Count of the caller's own pending approvals — the same queue the panel lists. */
  pending_approvals: number
  /** Scope marker for `pending_approvals` so the UI can label it truthfully. */
  pending_approvals_scope?: 'assigned_to_me' | 'organisation'
  active_workflows: number | null
  overdue: number | null
  completed_today: number | null
  completed_this_week?: number | null
  average_completion_time_hours?: number | null
  sla_compliance_rate?: number | null
  by_template?: Record<string, { active: number; completed: number; avg_hours: number }>
  by_priority?: Record<string, number>
}

export function createWorkflowsApi(api: AxiosInstance) {
  return {
    getPendingApprovals: () =>
      api.get<{ approvals: WorkflowApprovalRecord[]; total: number }>(
        '/api/v1/workflows/approvals/pending',
      ),
    approveRequest: (approvalId: string, data?: { notes?: string }) =>
      api.post(`/api/v1/workflows/approvals/${approvalId}/approve`, data),
    rejectRequest: (approvalId: string, data?: { notes?: string; reason?: string }) =>
      api.post(`/api/v1/workflows/approvals/${approvalId}/reject`, data),
    bulkApprove: (approvalIds: string[], data?: { notes?: string }) =>
      api.post('/api/v1/workflows/approvals/bulk-approve', {
        approval_ids: approvalIds,
        ...data,
      }),
    listInstances: (params?: { status?: string; entity_type?: string }) => {
      const sp = new URLSearchParams()
      if (params?.status) sp.set('status', params.status)
      if (params?.entity_type) sp.set('entity_type', params.entity_type)
      return api.get<{ instances: WorkflowInstanceRecord[]; total: number }>(
        `/api/v1/workflows/instances?${sp}`,
      )
    },
    listTemplates: () =>
      api.get<{ templates: WorkflowTemplateRecord[] }>('/api/v1/workflows/templates'),
    getStats: () => api.get<WorkflowStatsResponse>('/api/v1/workflows/stats'),
    getDelegations: () =>
      api.get<{ delegations: WorkflowDelegationRecord[] }>('/api/v1/workflows/delegations'),
    setDelegation: (data: {
      delegate_id: number
      start_date: string
      end_date: string
      reason?: string
      workflow_types?: string[]
    }) => api.post('/api/v1/workflows/delegations', data),
    cancelDelegation: (delegationId: string) =>
      api.delete(`/api/v1/workflows/delegations/${delegationId}`),
  }
}
