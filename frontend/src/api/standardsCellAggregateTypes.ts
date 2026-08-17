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
  /** `unmatched` = on the shelf but attributable to no framework; never counted. */
  proof_scope?: 'framework' | 'clause' | 'unmatched' | string
  framework?: string | null
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
    unmatched_cert_count?: number
    evidence_count: number
    imported_prior_count: number
    mock_finding_count: number
    top_evidence_label?: string | null
    freshness?: string | null
    scan_truncated?: boolean
  }
  alignment?: StandardsCellAlignment
  trap_blocked?: Array<Record<string, unknown>>
  tech_gap?: StandardsCellTechGap
  exact_share?: StandardsCellExactShare
  /** AP-07: ISO-family NEAR proposed-share preflight (never auto-confirm). */
  near_share?: StandardsCellNearShare
  /** Int-W8 Entra MFA posture — present on technical cells only. */
  attestation?: StandardsCellAttestation
  /** A source hit its read cap: the counts above are a floor, not a total. */
  scan_truncated?: boolean
  scan_truncated_sources?: string[]
  sor_note?: string
}

/** EXACT shared-apply preflight (Wave 2 PR-D). */
export type StandardsExactShareCandidate = {
  framework: string
  clause_key: string
  clause_number: string
  verdict: AlignmentVerdict | string
  eligible: boolean
  blocked_reasons: string[]
  open_nc_count: number
  open_action_count: number
  tech_gap_warning?: string | null
  addition_text?: string | null
}

export type StandardsExactShareLink = {
  link_id: number
  entity_type: string
  entity_id: string
  title?: string | null
  cover_kind: string
  already_shared_frameworks: string[]
}

export type StandardsCellExactShare = {
  available: boolean
  unavailable_reason?: string | null
  matrix_version?: string | null
  matrix_version_id?: number | null
  source: {
    framework: string
    clause_number: string
    clause_key: string
    cover_blocked: boolean
  }
  candidates: StandardsExactShareCandidate[]
  shareable_links: StandardsExactShareLink[]
}

export type ExactShareApplyResponse = {
  status: string
  applied_at: string
  matrix_version?: string | null
  created: Array<{ link_id: number; framework: string; clause_id: string; verdict: string }>
  already_linked: Array<{ link_id?: number | null; framework: string; clause_id: string }>
  warnings: Array<{ framework: string; code: string }>
  undo: { link_ids: number[]; applied_at: string }
  sor_note?: string
}

export type ExactShareUndoResponse = {
  status: string
  deleted: number[]
  skipped: Array<{ link_id: number; reason: string }>
}

/** AP-07: ISO NEAR proposed-share uses the same plan/apply envelope as EXACT. */
export type StandardsCellNearShare = StandardsCellExactShare
export type NearShareApplyResponse = ExactShareApplyResponse
export type NearShareUndoResponse = ExactShareUndoResponse

/** PEL-HSEQ-5064 alignment vocabulary (Wave 2 PR-C). */
export type AlignmentVerdict = 'EXACT' | 'NEAR' | 'DIFFERENT' | 'UNIQUE'

export type StandardsCellAlignment = {
  matrix_version?: string | null
  matrix_loaded: boolean
  row_verdict?: AlignmentVerdict | string | null
  is_trap_row: boolean
  is_unique: boolean
  unique_reason?: string | null
  trap_peer_count: number
  /** False when the imported edition says nothing about this cell at all. */
  alignment_known?: boolean
  /** False when the edition carries no axis for this framework (CHAS, SSIP, CE…). */
  framework_covered?: boolean
  frameworks_on_row?: string[]
  peers: Array<{
    framework: string
    clause_key: string
    verdict: AlignmentVerdict | string
    shareable: boolean
    addition_text?: string | null
  }>
}

export type StandardsCellTechGap = {
  covered?: boolean
  stub?: boolean
  is_technical?: boolean
  reason?: string
  attestation_status?: string | null
  attested_kind?: string | null
  unattested_elements?: string[]
  requirement?: {
    key: string
    title: string
    frameworks: string[]
    attestation_needed: string
    source_position: string
  } | null
}

export type StandardsCellAttestation = {
  status: 'pass' | 'fail' | 'unavailable' | 'disabled' | 'not_applicable' | string
  source?: string | null
  reason?: string | null
  observed_at?: string | null
}

export type FrameworkCountdownStatus = 'none' | 'current' | 'due_soon' | 'expired'

export type FrameworkCountdownEntry = {
  status: FrameworkCountdownStatus | string
  next_expiry: string | null
  days_remaining: number | null
  name: string | null
}

/** Per-column cert expiry for the matrix countdown strip (SG-D-03). */
export type FrameworkCountdown = {
  due_soon_days: number
  unmatched_on_shelf: boolean
  frameworks: Record<string, FrameworkCountdownEntry>
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
    alignment?: StandardsCellAlignment
    tech_gap?: StandardsCellTechGap
    attestation?: StandardsCellAttestation
    scan_truncated?: boolean
  }>
  matrix_version?: string | null
  matrix_loaded?: boolean
  scan_truncated?: boolean
  scan_truncated_sources?: string[]
  sor_note?: string
  framework_countdown?: FrameworkCountdown
}

/** One clause row of the imported alignment catalogue. */
export type AlignmentCatalogueRow = {
  id: string
  kind: string
  row_key: string
  clauseNumber: string
  title: string
  verdict: AlignmentVerdict | string
  row_verdict: AlignmentVerdict | string
  is_trap: boolean
  has_unique: boolean
  addition_text?: string | null
  rationale?: string | null
  deliverables?: string | null
  pair_count: number
  trap_pair_count: number
  axis_frameworks?: string[]
  frameworks: Record<
    string,
    {
      clause_key: string
      clause_number: string
      label?: string | null
      verdicts: string[]
    }
  >
}

export type AlignmentCatalogueResponse = {
  matrix_loaded: boolean
  matrix_version?: string | null
  matrix_version_id?: number
  source_date?: string | null
  rows: AlignmentCatalogueRow[]
  frameworks: string[]
  excluded_frameworks: string[]
  row_count?: number
  edge_count?: number
  fallback_note?: string
  sor_note?: string
}
