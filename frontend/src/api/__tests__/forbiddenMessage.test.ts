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
