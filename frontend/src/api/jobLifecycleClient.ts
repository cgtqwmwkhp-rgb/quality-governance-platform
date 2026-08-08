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

export interface JobStep {
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

export interface JobCell {
  id: number
  tenant_id: number
  job_type_id: number
  lane_id: number
  step_id: number
  library_document_ids: number[]
  created_at: string
  updated_at: string
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
}

export interface JobStepUpdatePayload {
  name?: string
  description?: string | null
  sort_order?: number
  is_active?: boolean
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
  }
}

export type JobLifecycleApi = ReturnType<typeof createJobLifecycleApi>
