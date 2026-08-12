/** Types for Standards cell aggregate read-model (Wave 1 PR-B). */

export type CellVerdict = 'covered' | 'partial' | 'gap' | 'unknown'

export type AuditKind = 'internal' | 'mock' | 'imported'

export type StandardsCellFinding = {
  id: number
  reference_number?: string | null
  run_id: number
  title: string
  description?: string
  severity?: string
  finding_type?: string
  status: string
  is_nc: boolean
  audit_kind: AuditKind | string
  clause_ids?: unknown[]
  risk_ids?: number[] | null
  created_at?: string | null
  updated_at?: string | null
  detail_path?: string
}

export type StandardsCellAction = {
  id: number
  reference_number?: string | null
  title: string
  status: string
  priority?: string | null
  source_type?: string | null
  source_id?: number | null
  clause_reference?: string | null
  iso_standard?: string | null
  due_date?: string | null
  created_at?: string | null
  updated_at?: string | null
  detail_path?: string
}

export type StandardsCellRisk = {
  id: number
  register: 'operational' | 'enterprise' | string
  reference?: string | null
  title: string
  status?: string | null
  detail_path?: string
  source?: string
  from_finding_id?: number
}

export type StandardsCellCertificate = {
  shelf_key: string
  name: string
  scheme: string
  readiness_status?: string
  expiry_date?: string | null
  detail_path?: string | null
  proof_scope?: 'framework' | 'clause' | string
  framework?: string
  linked_clause?: string | null
  is_critical?: boolean
}

export type StandardsCellEvidence = {
  id: number
  entity_type: string
  entity_id: string
  clause_id: string
  title?: string | null
  signal_type?: string | null
  is_operational_signal?: boolean
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type StandardsCellImportedPrior = {
  id: number
  scheme: string
  scheme_label?: string | null
  outcome_status?: string | null
  report_date?: string | null
  findings_count?: number | null
  major_findings?: number | null
  minor_findings?: number | null
  audit_run_id?: number | null
  import_job_id?: number | null
  linked_to_cell_findings?: boolean
  detail_path?: string
}

export type StandardsCellAggregate = {
  framework: string
  clause_number: string
  catalogue_keys: string[]
  verdict: CellVerdict | string
  cover_blocked: boolean
  recurrence_red_flag: boolean
  reasons: string[]
  findings: StandardsCellFinding[]
  actions: StandardsCellAction[]
  risks: StandardsCellRisk[]
  certificates: StandardsCellCertificate[]
  evidence: StandardsCellEvidence[]
  imported_priors: StandardsCellImportedPrior[]
  summary: {
    open_nc_count: number
    closed_nc_count: number
    open_action_count: number
    risk_count: number
    cert_count: number
    evidence_count: number
    imported_prior_count: number
    mock_finding_count: number
    top_evidence_label?: string | null
    freshness?: string | null
  }
  sor_note?: string
}

export type StandardsCellMatrixSummary = {
  cells: Array<{
    framework: string
    clause_number: string
    verdict: CellVerdict | string
    cover_blocked: boolean
    recurrence_red_flag: boolean
    reasons: string[]
    summary: StandardsCellAggregate['summary']
  }>
  sor_note?: string
}
