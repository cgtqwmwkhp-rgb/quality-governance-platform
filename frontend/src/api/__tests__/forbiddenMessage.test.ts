import { describe, expect, it } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { forbiddenMessageFor } from '../client'

/**
 * A 403 carries two unrelated failures.
 *
 * A user with no tenant is refused on every endpoint, including ones that check no
 * permission at all. Presenting that as "you don't have permission" is untrue and
 * unactionable — it cost hours of misdirected diagnosis on a real production lockout.
 */
function forbidden(code?: string): AxiosError {
  const error = new AxiosError('Request failed', 'ERR_BAD_REQUEST')
  error.response = {
    status: 403,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: code
      ? { error: { code, error_class: code, message: 'User has no tenant membership' } }
      : { error: { message: 'Not enough permissions' } },
  }
  return error
}

describe('the message shown for a 403', () => {
  it('does not blame permissions when the account has no organisation', () => {
    const shown = forbiddenMessageFor(forbidden('TENANT_ACCESS_DENIED'))

    expect(shown).not.toMatch(/permission to perform/)
    expect(shown).toMatch(/organisation/)
  })

  it('says what to do about it, and who does it', () => {
    const shown = forbiddenMessageFor(forbidden('TENANT_ACCESS_DENIED'))

    expect(shown).toMatch(/administrator/)
    expect(shown).toMatch(/setup/)
  })

  it('still reports a genuine permission denial as one', () => {
    expect(forbiddenMessageFor(forbidden('PERMISSION_DENIED'))).toBe(
      "You don't have permission to perform this action.",
    )
  })

  it('falls back to the permission wording when the server named no code', () => {
    expect(forbiddenMessageFor(forbidden())).toBe(
      "You don't have permission to perform this action.",
    )
  })

  it('does not throw on something that is not an axios error', () => {
    expect(forbiddenMessageFor(new Error('nope'))).toBe(
      "You don't have permission to perform this action.",
    )
  })
})

/**
 * The third failure wearing 403: the CB-UI-3 assessor gate.
 *
 * Rewriting these to the generic line throws away the only actionable part of
 * the response. There is no permission an administrator can grant that makes
 * you a different person from the engineer you are trying to assess, and none
 * that makes PAMS have issued you a skill it has not issued.
 */
function assessorRefusal(message?: string): AxiosError {
  const error = new AxiosError('Request failed', 'ERR_BAD_REQUEST')
  error.response = {
    status: 403,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: {
      error: {
        code: 'ASSESSOR_NOT_ELIGIBLE',
        ...(message === undefined ? {} : { message }),
      },
    },
  }
  return error
}

describe('the message shown for an assessor gate refusal', () => {
  it('keeps the sentence that says you cannot assess yourself', () => {
    const shown = forbiddenMessageFor(
      assessorRefusal(
        'You cannot assess yourself. A demonstration needs a second person to witness it, ' +
          'so the assessor and the engineer being assessed must be different people.',
      ),
    )

    expect(shown).toMatch(/cannot assess yourself/)
    expect(shown).not.toMatch(/permission to perform/)
  })

  it('keeps the sentence that says PAMS has not issued you the skill', () => {
    const shown = forbiddenMessageFor(
      assessorRefusal(
        'PAMS has not issued you MEWP_3A, so you cannot assess it. ' +
          'Issuance lives in PAMS — QGP reads it and never writes it.',
      ),
    )

    expect(shown).toMatch(/PAMS has not issued you MEWP_3A/)
    expect(shown).not.toMatch(/permission to perform/)
  })

  it('distinguishes the four refusals rather than collapsing them', () => {
    const shown = [
      'You cannot assess yourself.',
      'PAMS has not issued you MEWP_3A.',
      'Your user account is not linked to a QGP employee record.',
      'No PAMS competence snapshot has been loaded.',
    ].map((message) => forbiddenMessageFor(assessorRefusal(message)))

    expect(new Set(shown).size).toBe(4)
  })

  it('falls back to the permission wording when the code arrived without a message', () => {
    expect(forbiddenMessageFor(assessorRefusal())).toBe(
      "You don't have permission to perform this action.",
    )
  })

  it('falls back rather than showing an empty toast for a blank message', () => {
    expect(forbiddenMessageFor(assessorRefusal('   '))).toBe(
      "You don't have permission to perform this action.",
    )
  })
})
