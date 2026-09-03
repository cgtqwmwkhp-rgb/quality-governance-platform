/**
 * Family assessment start client — `POST /api/v1/workforce/competence/assessments`
 * (CB-UI-3).
 *
 * A third client on the same router, for the same reason CB-UI-2 added a second
 * one. `competenceBoardClient` is read-only *by construction* so the board can
 * never grow a PAMS write by habit, and `competenceBindClient` is the IT-Admin
 * mapping surface. This one is the assessor's, and the only thing it writes is a
 * QGP `assessment_runs` row.
 *
 * It creates the run and stops there. Execution and completion are the existing
 * assessment routes — `/workforce/assessments/{run_id}/execute` and
 * `POST /api/v1/assessments/{run_id}/complete` — which is what makes a pass land
 * on the CB-PR4 demonstration overlay and a fail open the IT-Admin revoke
 * change request. There is no complete method here, because a second one would
 * be a second execute shell.
 *
 * The endpoint 404s while `COMPETENCE_BOARD_ENABLED` is false and 403s when the
 * assessor gate refuses. Both are the server's answer and must be rendered as
 * such, never as a start that silently did nothing.
 */
import type { AxiosInstance } from 'axios'
import type { CompetenceBindMode } from './competenceBindClient'

/**
 * Which machine the demonstration happened on. Evidence, not issuance: none of
 * these fields grants anything, and an absent one does not invalidate the run.
 */
export type CompetencePlantEvidence = {
  make?: string | null
  model?: string | null
  serial?: string | null
  pams_plant_id?: string | null
}

export type CompetenceAssessmentStartCreate = {
  /** The engineer being assessed (`engineers.id`), never the assessor. */
  engineer_id: number
  characteristic_key: string
  mode: CompetenceBindMode
  plant_evidence?: CompetencePlantEvidence | null
}

export type CompetenceAssessmentStart = {
  run_id: string
  reference_number: string
  template_id: number
  engineer_id: number
  characteristic_key: string
  mode: CompetenceBindMode
  status: string
  /** Echoed back normalised: blank boxes are absent rather than empty strings. */
  plant_evidence?: CompetencePlantEvidence | null
}

const BASE = '/api/v1/workforce/competence/assessments'

/** Where the run created above is actually carried out. */
export function competenceAssessmentExecutePath(runId: string): string {
  return `/workforce/assessments/${runId}/execute`
}

export function createCompetenceStartApi(api: AxiosInstance) {
  return {
    start: (payload: CompetenceAssessmentStartCreate) =>
      api.post<CompetenceAssessmentStart>(BASE, payload),
  }
}
