import { describe, expect, it } from 'vitest'
import { parseExistingInvestigationConflict } from '../investigationConflict'

function conflict(body: unknown) {
  return { response: { status: 409, data: body } }
}

describe('parseExistingInvestigationConflict (PX-136)', () => {
  it('reads the real API error envelope', () => {
    expect(
      parseExistingInvestigationConflict(
        conflict({
          error: {
            code: 'INV_ALREADY_EXISTS',
            message: 'An investigation already exists for this reporting incident',
            details: { existing_investigation_id: 12, existing_reference_number: 'INV-2026-0012' },
          },
        }),
      ),
    ).toEqual({ id: 12, reference: 'INV-2026-0012' })
  })

  it('still reads the legacy detail shape', () => {
    expect(
      parseExistingInvestigationConflict(
        conflict({
          detail: {
            error_code: 'INV_ALREADY_EXISTS',
            details: { existing_investigation_id: 3 },
          },
        }),
      ),
    ).toEqual({ id: 3, reference: undefined })
  })

  it('ignores conflicts that are not an existing investigation', () => {
    expect(
      parseExistingInvestigationConflict(
        conflict({ error: { code: 'DUPLICATE_ENTITY', details: { existing_investigation_id: 4 } } }),
      ),
    ).toBeNull()
  })

  it('returns null rather than a link with no target', () => {
    expect(
      parseExistingInvestigationConflict(
        conflict({ error: { code: 'INV_ALREADY_EXISTS', details: {} } }),
      ),
    ).toBeNull()
    expect(
      parseExistingInvestigationConflict(
        conflict({ error: { code: 'INV_ALREADY_EXISTS', details: { existing_investigation_id: 0 } } }),
      ),
    ).toBeNull()
  })

  it('ignores non-409 responses and malformed errors', () => {
    expect(
      parseExistingInvestigationConflict({
        response: { status: 500, data: { error: { code: 'INV_ALREADY_EXISTS' } } },
      }),
    ).toBeNull()
    expect(parseExistingInvestigationConflict(new Error('network'))).toBeNull()
    expect(parseExistingInvestigationConflict(null)).toBeNull()
    expect(parseExistingInvestigationConflict(conflict(null))).toBeNull()
  })
})
