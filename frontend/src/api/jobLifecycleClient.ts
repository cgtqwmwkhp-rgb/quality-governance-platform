/**
 * Job Lifecycle API client (JL-1 / JL-2 / ADR-0022).
 *
 * Axes are JL-owned Job Type / Lane / Step. Cells hold library_document_id[]
 * refs only — never document bodies. Every route 404s while `job_lifecycle` is
 * closed.
 */
import type { AxiosInstance, AxiosResponse } from 'axios'

export interface JobType {
  id: number
  tenant_id: number
  code: string
  name: string
  description?: string | null
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface JobLane {
  id: number
  tenant_id: number
  job_type_id: number
  code: string
  name: string
  description?: string | null
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Deming phase used to colour a step. `null` is a legitimate "unset". */
export type JobStepPdcaPhase = 'plan' | 'do' | 'check' | 'act'

export interface JobStep {
  id: number
  tenant_id: number
  job_type_id: number
  code: string
  name: string
  description?: string | null
  sort_order: number
  is_active: boolean
  pdca_phase?: JobStepPdcaPhase | null
  created_at: string
  updated_at: string
}

export interface JobCell {
  id: number
  tenant_id: number
  job_type_id: number
  lane_id: number
  step_id: number
  library_document_ids: number[]
  links?: JobCellLink[]
  created_at: string
  updated_at: string
}

export type JobCellLinkKind = 'app' | 'external' | 'audit_outcome' | 'job_cycle'

export interface JobCellLink {
  id: number
  tenant_id: number
  cell_id: number
  kind: JobCellLinkKind
  label: string
  entity_type?: string | null
  entity_id?: number | null
  external_url?: string | null
  audit_run_id?: number | null
  audit_finding_id?: number | null
  /** Set only for `job_cycle` — the nested JobType. Sole SSOT for nesting. */
  target_job_type_id?: number | null
  href: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface JobCellLinkCreatePayload {
  kind: JobCellLinkKind
  label: string
  entity_type?: string
  entity_id?: number
  external_url?: string
  audit_run_id?: number
  audit_finding_id?: number
  target_job_type_id?: number
  sort_order?: number
}

export interface JobLinkEntityTypesResponse {
  items: string[]
  total: number
}

export interface JobCellLinkListResponse {
  items: JobCellLink[]
  total: number
}

export interface JobTypeCreatePayload {
  code: string
  name: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
}

export interface JobTypeUpdatePayload {
  name?: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
}

export interface JobLaneCreatePayload {
  code: string
  name: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
}

export interface JobLaneUpdatePayload {
  name?: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
}

export interface JobStepCreatePayload {
  code: string
  name: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
  pdca_phase?: JobStepPdcaPhase | null
}

export interface JobStepUpdatePayload {
  name?: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
  /** Send an explicit null to clear the phase; omit the key to leave it alone. */
  pdca_phase?: JobStepPdcaPhase | null
}

export interface JobTypeListResponse {
  items: JobType[]
  total: number
}

export interface JobLaneListResponse {
  items: JobLane[]
  total: number
}

export interface JobStepListResponse {
  items: JobStep[]
  total: number
}

export interface JobCellListResponse {
  items: JobCell[]
  total: number
}

export interface JobCellDocumentsPutPayload {
  library_document_ids: number[]
}

const PREFIX = '/api/v1/job-lifecycle'

export function createJobLifecycleApi(api: AxiosInstance) {
  return {
    listJobTypes(): Promise<AxiosResponse<JobTypeListResponse>> {
      return api.get(`${PREFIX}/job-types`)
    },

    createJobType(payload: JobTypeCreatePayload): Promise<AxiosResponse<JobType>> {
      return api.post(`${PREFIX}/job-types`, payload)
    },

    getJobType(jobTypeId: number): Promise<AxiosResponse<JobType>> {
      return api.get(`${PREFIX}/job-types/${jobTypeId}`)
    },

    updateJobType(
      jobTypeId: number,
      payload: JobTypeUpdatePayload,
    ): Promise<AxiosResponse<JobType>> {
      return api.patch(`${PREFIX}/job-types/${jobTypeId}`, payload)
    },

    deleteJobType(jobTypeId: number): Promise<AxiosResponse<void>> {
      return api.delete(`${PREFIX}/job-types/${jobTypeId}`)
    },

    listLanes(jobTypeId: number): Promise<AxiosResponse<JobLaneListResponse>> {
      return api.get(`${PREFIX}/job-types/${jobTypeId}/lanes`)
    },

    createLane(
      jobTypeId: number,
      payload: JobLaneCreatePayload,
    ): Promise<AxiosResponse<JobLane>> {
      return api.post(`${PREFIX}/job-types/${jobTypeId}/lanes`, payload)
    },

    updateLane(laneId: number, payload: JobLaneUpdatePayload): Promise<AxiosResponse<JobLane>> {
      return api.patch(`${PREFIX}/lanes/${laneId}`, payload)
    },

    deleteLane(laneId: number): Promise<AxiosResponse<void>> {
      return api.delete(`${PREFIX}/lanes/${laneId}`)
    },

    listSteps(jobTypeId: number): Promise<AxiosResponse<JobStepListResponse>> {
      return api.get(`${PREFIX}/job-types/${jobTypeId}/steps`)
    },

    createStep(
      jobTypeId: number,
      payload: JobStepCreatePayload,
    ): Promise<AxiosResponse<JobStep>> {
      return api.post(`${PREFIX}/job-types/${jobTypeId}/steps`, payload)
    },

    updateStep(stepId: number, payload: JobStepUpdatePayload): Promise<AxiosResponse<JobStep>> {
      return api.patch(`${PREFIX}/steps/${stepId}`, payload)
    },

    deleteStep(stepId: number): Promise<AxiosResponse<void>> {
      return api.delete(`${PREFIX}/steps/${stepId}`)
    },

    listCells(jobTypeId: number): Promise<AxiosResponse<JobCellListResponse>> {
      return api.get(`${PREFIX}/job-types/${jobTypeId}/cells`)
    },

    putCellDocuments(
      jobTypeId: number,
      laneId: number,
      stepId: number,
      payload: JobCellDocumentsPutPayload,
    ): Promise<AxiosResponse<JobCell>> {
      return api.put(
        `${PREFIX}/job-types/${jobTypeId}/cells/${laneId}/${stepId}/documents`,
        payload,
      )
    },

    listCellLinks(
      jobTypeId: number,
      laneId: number,
      stepId: number,
    ): Promise<AxiosResponse<JobCellLinkListResponse>> {
      return api.get(`${PREFIX}/job-types/${jobTypeId}/cells/${laneId}/${stepId}/links`)
    },

    createCellLink(
      jobTypeId: number,
      laneId: number,
      stepId: number,
      payload: JobCellLinkCreatePayload,
    ): Promise<AxiosResponse<JobCellLink>> {
      return api.post(
        `${PREFIX}/job-types/${jobTypeId}/cells/${laneId}/${stepId}/links`,
        payload,
      )
    },

    deleteCellLink(linkId: number): Promise<AxiosResponse<void>> {
      return api.delete(`${PREFIX}/links/${linkId}`)
    },

    listLinkEntityTypes(): Promise<AxiosResponse<JobLinkEntityTypesResponse>> {
      return api.get(`${PREFIX}/link-entity-types`)
    },
  }
}

export type JobLifecycleApi = ReturnType<typeof createJobLifecycleApi>
