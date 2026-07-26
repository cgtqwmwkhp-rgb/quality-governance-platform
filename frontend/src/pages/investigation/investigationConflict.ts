/**
 * Reading the "an investigation already exists" 409 off the wire (PX-136).
 *
 * The API error envelope is `{ error: { code, message, details } }`. The create-from-record
 * dialog previously looked for `detail.error_code`, a shape the server never sends, so the
 * "Open existing investigation" route out of the conflict was unreachable and the operator
 * was left with a bare error on a record that already had an investigation.
 */

export interface ExistingInvestigationConflict {
  id: number
  reference?: string
}

const CONFLICT_CODE = 'INV_ALREADY_EXISTS'

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

function readDetails(body: Record<string, unknown>): {
  code?: string
  details: Record<string, unknown>
} {
  const envelope = asRecord(body.error)
  if (envelope) {
    return {
      code: typeof envelope.code === 'string' ? envelope.code : undefined,
      details: asRecord(envelope.details) ?? {},
    }
  }
  // Tolerated legacy shapes: `{ detail: { error_code, details } }` and a bare `{ error_code }`.
  const legacy = asRecord(body.detail) ?? body
  const code = legacy.error_code ?? legacy.code
  return {
    code: typeof code === 'string' ? code : undefined,
    details: asRecord(legacy.details) ?? {},
  }
}

/**
 * Extract the existing investigation from a 409, or null when the error is something else.
 *
 * Returns null rather than a partial when there is no usable id — a link with no target is
 * worse than the plain error message.
 */
export function parseExistingInvestigationConflict(error: unknown): ExistingInvestigationConflict | null {
  const response = asRecord(asRecord(error)?.response)
  if (!response || response.status !== 409) return null
  const body = asRecord(response.data)
  if (!body) return null

  const { code, details } = readDetails(body)
  if (code !== CONFLICT_CODE) return null

  const rawId = details.existing_investigation_id
  const id = typeof rawId === 'number' ? rawId : Number(rawId)
  if (!Number.isFinite(id) || id <= 0) return null

  const rawReference = details.existing_reference_number
  return {
    id,
    reference: typeof rawReference === 'string' && rawReference.trim() ? rawReference : undefined,
  }
}
