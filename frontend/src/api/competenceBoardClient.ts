/**
 * Competence board client — `GET /api/v1/workforce/competence/board` (CB-PR1 /
 * CB-PR3 / CB-PR4, ADR-0026 issued vs demonstrated).
 *
 * Read-only by construction. Plant competencies are issued in PAMS and people
 * competencies are issued in Atlas; QGP records demonstrations against them and
 * writes to neither source, so this client exposes no write method for one to
 * be added to by habit. The change-request and bind endpoints that do exist on
 * the same router are deliberately not surfaced here — they belong to CB-UI-2.
 *
 * The board 404s while `COMPETENCE_BOARD_ENABLED` is false. That is the honest
 * answer and callers must render it as "not enabled", never as zero coverage.
 */
import type { AxiosInstance } from 'axios'

export type CompetenceBoardFamily = 'pams' | 'atlas'

/**
 * One person × one characteristic.
 *
 * A characteristic the person holds no record for is **absent from the map**,
 * not present with `issued: false` — so a missing key means "PAMS/Atlas says
 * nothing here", which is not the same claim as a failure.
 */
export type CompetenceBoardCell = {
  issued: boolean
  /** PAMS family only. Null when the snapshot did not carry the flag. */
  thorough_exam?: boolean | null
  /** Atlas family only (`YYYY-MM-DD`). */
  passed_on?: string | null
  /** Atlas family only (`YYYY-MM-DD`). */
  expires_on?: string | null
  /** CB-PR4 overlay from a bound QGP assessment. Absent = never assessed. */
  demonstrated?: 'pass' | 'fail' | null
  assessed_at?: string | null
  demonstrated_expires_on?: string | null
}

export type CompetenceBoardColumn = {
  key: string
  label: string
}

export type CompetenceBoardPerson = {
  engineer_id?: number | null
  pams_technician_id?: number | null
  atlas_person_id?: number | null
  display_name: string
  email?: string | null
  depot?: string | null
  department?: string | null
  /** False when the source row has no QGP engineer. The row is still shown. */
  mapped: boolean
  cells: Record<string, CompetenceBoardCell>
}

export type CompetenceBoardSnapshotMeta = {
  id?: number | null
  status?: string | null
  source_name?: string | null
  row_count: number
  completed_at?: string | null
  stale: boolean
  stale_reason?: string | null
}

export type CompetenceBoardResponse = {
  family: CompetenceBoardFamily
  snapshot: CompetenceBoardSnapshotMeta
  columns: CompetenceBoardColumn[]
  people: CompetenceBoardPerson[]
  unmapped_count: number
  /** Honest stale/empty notice from the server. Never a grey not-assessed cell. */
  banner?: string | null
}

export function createCompetenceBoardApi(api: AxiosInstance) {
  return {
    getBoard: (family: CompetenceBoardFamily) =>
      api.get<CompetenceBoardResponse>('/api/v1/workforce/competence/board', {
        params: { family },
      }),
  }
}
