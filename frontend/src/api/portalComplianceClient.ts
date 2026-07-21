import type { AxiosInstance } from 'axios'

export type PortalClearState = 'clear' | 'attention' | 'blocked'

export type PortalToolBand =
  | 'overdue'
  | 'due_30'
  | 'due_60'
  | 'due_90'
  | 'in_date'
  | 'none'
  | 'quarantined'
  | 'decommissioned'

export type PortalToolSummary = {
  total: number
  overdue: number
  due_30: number
  due_60: number
  due_90: number
  in_date: number
  quarantined: number
  mine: number
  on_van: number
}

export type PortalToolItem = {
  id: number
  name: string
  asset_number: string
  serial_number?: string | null
  status: string
  expiry_date?: string | null
  band: PortalToolBand
  vehicle_reg?: string | null
  owner_user_id?: number | null
  asset_type_name?: string | null
  type_pending: boolean
  why_shown: string
}

export type PortalDefectCounts = {
  p1: number
  p2: number
  p3: number
  total: number
}

export type PortalOpenDefect = {
  id: number
  priority: string
  status: string
  check_field: string
  check_value?: string | null
  notes?: string | null
  created_at?: string | null
}

export type PortalVanSummary = {
  vehicle_reg?: string | null
  daily_last_at?: string | null
  daily_pass?: boolean | null
  monthly_last_at?: string | null
  defect_counts: PortalDefectCounts
  empty_reason?: string | null
  assignment_conflict: boolean
}

export type PortalMyCompliance = {
  clear_state: PortalClearState
  tool_summary: PortalToolSummary
  tool_badge: number
  van_summary: PortalVanSummary
  van_badge: number
  tools_empty_reason?: string | null
}

export type PortalMyTools = {
  items: PortalToolItem[]
  summary: PortalToolSummary
  empty_reason?: string | null
}

export type PortalMyVan = {
  linked_driver: boolean
  vehicle_reg?: string | null
  assignment_conflict: boolean
  conflicting_regs: string[]
  empty_reason?: string | null
  daily_last_at?: string | null
  daily_pass?: boolean | null
  monthly_last_at?: string | null
  open_defects: PortalOpenDefect[]
  defect_counts: PortalDefectCounts
  fleet_status?: string | null
  compliance_status?: string | null
}

export function createPortalComplianceApi(api: AxiosInstance) {
  return {
    myCompliance: () => api.get<PortalMyCompliance>('/portal/my-compliance').then((r) => r.data),
    myTools: () => api.get<PortalMyTools>('/portal/my-tools').then((r) => r.data),
    myVan: () => api.get<PortalMyVan>('/portal/my-van').then((r) => r.data),
  }
}
