import { describe, expect, it } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import {
  UNPROVISIONED_ERROR_CODES,
  getApiErrorCode,
  getApiErrorMessage,
  isUnprovisionedError,
} from '../client'

/**
 * A missing table must not be presented as something that went wrong.
 *
 * The response interceptor prefixes every `status >= 500` message with
 * "Server error:", which framed a feature that was never built as a fault that
 * broke and might come back. Both 503 codes carrying an absent table are exempt.
 */

function serverError(status: number, code: string | undefined, message: string): AxiosError {
  const error = new AxiosError('Request failed', 'ERR_BAD_RESPONSE')
  error.response = {
    status,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: code ? { error: { code, message } } : { error: { message } },
  }
  return error
}

describe('getApiErrorCode', () => {
  it('reads the code out of the unified envelope', () => {
    expect(getApiErrorCode(serverError(503, 'FEATURE_NOT_PROVISIONED', 'nope'))).toBe(
      'FEATURE_NOT_PROVISIONED',
    )
  })

  it('returns null rather than a guess when the server named no code', () => {
    expect(getApiErrorCode(serverError(500, undefined, 'boom'))).toBeNull()
    expect(getApiErrorCode(new Error('not an axios error'))).toBeNull()
  })
})

describe('isUnprovisionedError', () => {
  it('recognises both halves of the absent-table contract', () => {
    expect(isUnprovisionedError(serverError(503, 'MEASUREMENT_UNAVAILABLE', 'x'))).toBe(true)
    expect(isUnprovisionedError(serverError(503, 'FEATURE_NOT_PROVISIONED', 'x'))).toBe(true)
  })

  it('does not swallow a genuine server fault', () => {
    expect(isUnprovisionedError(serverError(500, 'INTERNAL_ERROR', 'x'))).toBe(false)
    expect(isUnprovisionedError(serverError(500, 'DATABASE_ERROR', 'x'))).toBe(false)
    expect(isUnprovisionedError(serverError(503, undefined, 'x'))).toBe(false)
  })

  it('lists exactly the two codes, so a third cannot be added silently', () => {
    expect([...UNPROVISIONED_ERROR_CODES].sort()).toEqual([
      'FEATURE_NOT_PROVISIONED',
      'MEASUREMENT_UNAVAILABLE',
    ])
  })
})

describe('the message a user is shown', () => {
  it("does not call a missing table a server error", () => {
    const error = serverError(
      503,
      'FEATURE_NOT_PROVISIONED',
      'A controlled-copy distribution cannot be recorded because document_distributions is absent from this database. Nothing was saved.',
    )
    // The interceptor is what sets classifiedMessage in the app; asserting on
    // getApiErrorMessage with no classifiedMessage present pins the fallback
    // path, which reads the envelope message verbatim.
    const shown = getApiErrorMessage(error)

    expect(shown).not.toMatch(/^Server error:/)
    expect(shown).toContain('document_distributions')
    expect(shown).toContain('Nothing was saved')
  })
})
