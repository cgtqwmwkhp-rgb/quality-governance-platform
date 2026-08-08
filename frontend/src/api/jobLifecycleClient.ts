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
  /**
   * JL-UX-W4 — this intersection is expected to hold evidence. Optional on the
   * type so a cell cached by a pre-W4 build still satisfies it; absent reads
   * as "not required", which is the same default the column carries.
   */
  requires_evidence?: boolean
  library_document_ids: number[]
  links?: JobCellLink[]
  created_at: string
  updated_at: string
}

export type JobCellLinkKind = 'app' | 'external' | 'audit_outcome' | 'job_cycle'

/** Audit cadence state. `unknown` means the run has no cadence we can read. */
export type JobAuditLapseState = 'current' | 'due_soon' | 'lapsed' | 'unknown'

export interface JobCellLinkAuditLapse {
  state: JobAuditLapseState
  reason: string
  last_completed_at?: string | null
  next_due_at?: string | null
  frequency?: string | null
  frequency_days?: number | null
}

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
  /** Set for `audit_outcome` links only — absent everywhere else. */
  audit_lapse?: JobCellLinkAuditLapse | null
  sort_order: number
  created_at: string
  updated_at: string
}

/**
 * Document freshness read from the Library / Document Control SSOT.
 * `unknown` is a real answer: the SSOT holds no review date for the document.
 */
export type JobDocumentFreshnessState =
  | 'current'
  | 'due_soon'
  | 'overdue'
  | 'obsolete'
  | 'unknown'

export interface JobDocumentFreshness {
  library_document_id: number
  found: boolean
  title?: string | null
  reference?: string | null
  library_status?: string | null
  controlled_status?: string | null
  state: JobDocumentFreshnessState
  reason: string
  review_date?: string | null
  is_obsolete: boolean
}

export interface JobDocumentFreshnessResponse {
  items: JobDocumentFreshness[]
  total: number
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

/* -------------------------------------------------------------------------- */
/* JL-UX-W4 — mandatory evidence, clone, map / trail, optimistic concurrency   */
/* -------------------------------------------------------------------------- */

export interface JobCellRequirementPayload {
  requires_evidence: boolean
}

export interface JobTypeClonePayload {
  code: string
  name: string
  description?: string | null
  include_inactive?: boolean
}

export interface JobTypeCloneResponse {
  job_type: JobType
  source_job_type_id: number
  cloned_lane_count: number
  cloned_step_count: number
  /** Always 0 — a clone copies axes, never evidence claims. */
  cloned_cell_count: number
  cloned_document_count: number
}

/** `unknown` means the evidence exists but its standing could not be read. */
export type JobCellReadinessState =
  | 'not_required'
  | 'ready'
  | 'missing_evidence'
  | 'obsolete_evidence'
  | 'unknown'

export interface JobCellReadiness {
  state: JobCellReadinessState
  reason: string
  evidence_count: number
  obsolete_count: number
  unresolved_count: number
  is_ready: boolean
}

export interface JobCellReadinessItem extends JobCellReadiness {
  cell_id: number
  lane_id: number
  lane_name: string
  step_id: number
  step_name: string
  requires_evidence: boolean
  library_document_ids: number[]
}

export interface JobEvidenceReadinessResponse {
  items: JobCellReadinessItem[]
  total: number
  job_type_id: number
  assure: boolean
  summary: Record<string, number>
}

export type JobGraphNodeKind =
  | 'job_type'
  | 'cell'
  | 'document'
  | 'audit_finding'
  | 'app'
  | 'external'

export type JobGraphEdgeKind = 'nests' | 'contains' | 'evidences' | 'audits' | 'references'

export interface JobGraphNode {
  key: string
  kind: JobGraphNodeKind
  ref_id: number
  label: string
  href?: string | null
  detail?: string | null
}

export interface JobGraphEdge {
  key: string
  kind: JobGraphEdgeKind
  source: string
  target: string
  label: string
  href?: string | null
  cell_id?: number | null
  lane_id?: number | null
  step_id?: number | null
}

export interface JobCycleGraphResponse {
  root_job_type_id: number
  depth: number
  truncated: boolean
  nodes: JobGraphNode[]
  edges: JobGraphEdge[]
}

export interface JobAuditTrailPath {
  cell_id: number
  lane_id: number
  lane_name: string
  step_id: number
  step_name: string
  requires_evidence: boolean
  library_document_ids: number[]
  node_keys: string[]
  edge_keys: string[]
  readiness: JobCellReadiness
}

export interface JobAuditTrailResponse {
  root_job_type_id: number
  assure: boolean
  limit: number
  total_candidates: number
  truncated: boolean
  paths: JobAuditTrailPath[]
  nodes: JobGraphNode[]
  edges: JobGraphEdge[]
  summary: Record<string, number>
}

/**
 * Optimistic-concurrency precondition for an axis PATCH.
 *
 * `ifMatch` is the `updated_at` that was read. Omitting it keeps the previous
 * last-write-wins behaviour, so no existing caller changes meaning.
 */
export interface JobLifecycleWriteOptions {
  ifMatch?: string | null
}

function ifMatchConfig(
  options: JobLifecycleWriteOptions | undefined,
): { headers: Record<string, string> } | null {
  const token = options?.ifMatch
  if (typeof token !== 'string' || token.trim() === '') return null
  return { headers: { 'If-Match': token } }
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
      options?: JobLifecycleWriteOptions,
    ): Promise<AxiosResponse<JobType>> {
      const config = ifMatchConfig(options)
      const url = `${PREFIX}/job-types/${jobTypeId}`
      return config ? api.patch(url, payload, config) : api.patch(url, payload)
    },

    /** Copy a pack's lanes and steps into a new cycle. Cells stay empty. */
    cloneJobType(
      jobTypeId: number,
      payload: JobTypeClonePayload,
    ): Promise<AxiosResponse<JobTypeCloneResponse>> {
      return api.post(`${PREFIX}/job-types/${jobTypeId}/clone`, payload)
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

    updateLane(
      laneId: number,
      payload: JobLaneUpdatePayload,
      options?: JobLifecycleWriteOptions,
    ): Promise<AxiosResponse<JobLane>> {
      const config = ifMatchConfig(options)
      const url = `${PREFIX}/lanes/${laneId}`
      return config ? api.patch(url, payload, config) : api.patch(url, payload)
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

    updateStep(
      stepId: number,
      payload: JobStepUpdatePayload,
      options?: JobLifecycleWriteOptions,
    ): Promise<AxiosResponse<JobStep>> {
      const config = ifMatchConfig(options)
      const url = `${PREFIX}/steps/${stepId}`
      return config ? api.patch(url, payload, config) : api.patch(url, payload)
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

    /** Author the mandatory-evidence flag. Creates the cell if it is empty. */
    patchCellRequirement(
      jobTypeId: number,
      laneId: number,
      stepId: number,
      payload: JobCellRequirementPayload,
    ): Promise<AxiosResponse<JobCell>> {
      return api.patch(`${PREFIX}/job-types/${jobTypeId}/cells/${laneId}/${stepId}`, payload)
    },

    /** Readiness of every mandatory cell. `assure` also reads document status. */
    listEvidenceReadiness(
      jobTypeId: number,
      assure = false,
    ): Promise<AxiosResponse<JobEvidenceReadinessResponse>> {
      return api.get(
        `${PREFIX}/job-types/${jobTypeId}/evidence-readiness?assure=${assure ? 'true' : 'false'}`,
      )
    },

    /** Sample path walk for an auditor, in the map's node/edge vocabulary. */
    getAuditTrail(
      jobTypeId: number,
      options: { limit?: number; assure?: boolean } = {},
    ): Promise<AxiosResponse<JobAuditTrailResponse>> {
      const params = new URLSearchParams()
      if (typeof options.limit === 'number') params.set('limit', String(options.limit))
      params.set('assure', options.assure ? 'true' : 'false')
      return api.get(`${PREFIX}/job-types/${jobTypeId}/audit-trail?${params.toString()}`)
    },

    /** Process interaction map over `job_cycle` links (needs job_cell_links). */
    getCycleGraph(
      jobTypeId: number,
      depth?: number,
    ): Promise<AxiosResponse<JobCycleGraphResponse>> {
      const suffix = typeof depth === 'number' ? `?depth=${depth}` : ''
      return api.get(`${PREFIX}/job-types/${jobTypeId}/cycle-graph${suffix}`)
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

    /** Freshness for specific library documents. Repeats the id param per id. */
    listDocumentFreshness(
      libraryDocumentIds: readonly number[],
    ): Promise<AxiosResponse<JobDocumentFreshnessResponse>> {
      const params = new URLSearchParams()
      for (const id of libraryDocumentIds) params.append('library_document_ids', String(id))
      return api.get(`${PREFIX}/document-freshness?${params.toString()}`)
    },
  }
}

export type JobLifecycleApi = ReturnType<typeof createJobLifecycleApi>
