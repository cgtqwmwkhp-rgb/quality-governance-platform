/**
 * Workflows API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

// `WorkflowApprovalRecord`, `WorkflowDelegationRecord` and `WorkflowStatsResponse`
// were removed with the endpoints that returned them (FR-APPROVALS-01). Nothing
// in the app read them: the approvals queue behind them was `[]` for every user,
// and the delegation list was one invented record served to everybody. Outstanding
// decisions are now `PendingDecision` in `approvalsClient.ts`, read from the
// domains that hold them.

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

export function createWorkflowsApi(api: AxiosInstance) {
  return {
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
    // No approve, reject, bulk-approve, stats or delegation methods: those routes
    // no longer exist. See the note at the top of this file.
  }
}
