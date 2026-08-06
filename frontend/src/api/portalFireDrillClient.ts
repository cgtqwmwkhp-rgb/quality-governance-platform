import type { AxiosInstance } from 'axios'

export type PortalFireDrillStatus = 'current' | 'due_soon' | 'overdue'

export type PortalFireDrillItem = {
  id: number
  title: string
  reference_number: string
  next_due_date: string
  status?: PortalFireDrillStatus | null
  location_id?: number | null
  location_name?: string | null
  owner_id?: number | null
  last_completed_at?: string | null
}

export type PortalFireDrillList = {
  items: PortalFireDrillItem[]
  total: number
  evidence_capture_supported: boolean
}

export type PortalFireDrillCompleteRequest = {
  notes?: string | null
  check_passed?: boolean | null
  evidence_asset_ids?: number[] | null
  completed_at?: string | null
  due_date?: string | null
}

export type PortalFireDrillCompleteResponse = {
  id: number
  reference_number: string
  requirement_id: number
  due_date: string
  completed_at?: string | null
  check_passed?: boolean | null
  notes?: string | null
}

export function createPortalFireDrillApi(api: AxiosInstance) {
  return {
    list: () =>
      api.get<PortalFireDrillList>('/api/v1/portal/fire-drills').then((r) => r.data),
    complete: (requirementId: number, body: PortalFireDrillCompleteRequest) =>
      api
        .post<PortalFireDrillCompleteResponse>(
          `/api/v1/portal/fire-drills/${requirementId}/complete`,
          body,
        )
        .then((r) => r.data),
  }
}
