import { describe, expect, it } from 'vitest'

import { isSafeReturnTo } from '../knowledgeExceptionsLinks'

describe('isSafeReturnTo', () => {
  it('accepts same-app absolute paths', () => {
    expect(isSafeReturnTo('/actions')).toBe(true)
    expect(isSafeReturnTo('/incidents/42?tab=standards')).toBe(true)
    expect(isSafeReturnTo('/audits?view=findings&findingId=A-1')).toBe(true)
  })

  it('rejects absent or relative values', () => {
    expect(isSafeReturnTo(null)).toBe(false)
    expect(isSafeReturnTo(undefined)).toBe(false)
    expect(isSafeReturnTo('')).toBe(false)
    expect(isSafeReturnTo('actions')).toBe(false)
  })

  it('rejects the obvious off-origin forms', () => {
    expect(isSafeReturnTo('//evil.com')).toBe(false)
    expect(isSafeReturnTo('https://evil.com')).toBe(false)
    expect(isSafeReturnTo('http://evil.com/path')).toBe(false)
    expect(isSafeReturnTo('javascript://evil')).toBe(false)
  })

  // The bypass this guard originally missed. A browser normalises a backslash
  // to a forward slash before resolving, so `/\evil.com` becomes `//evil.com`
  // and leaves the origin — while passing a naive startsWith('//') check.
  it('rejects backslash-smuggled protocol-relative URLs', () => {
    expect(isSafeReturnTo('/\\evil.com')).toBe(false)
    expect(isSafeReturnTo('/\\/evil.com')).toBe(false)
    expect(isSafeReturnTo('/\\\\evil.com')).toBe(false)
    expect(isSafeReturnTo('\\/evil.com')).toBe(false)
  })

  // Browsers strip tab, newline and carriage return outright. Followed by a
  // slash that reassembles into `//host`, which leaves the origin. A bare tab
  // resolves to `/evil.com` on our own origin and is harmless — rejected here
  // only because a control character in a return path is never legitimate.
  it('rejects control characters that browsers strip before resolving', () => {
    expect(isSafeReturnTo('/\t/evil.com')).toBe(false)
    expect(isSafeReturnTo('/\n/evil.com')).toBe(false)
    expect(isSafeReturnTo('/\r/evil.com')).toBe(false)
    expect(isSafeReturnTo('/\tevil.com')).toBe(false)
  })

  it('confirms the hostile values really do leave the origin once resolved', () => {
    const origin = window.location.origin
    for (const hostile of ['//evil.com', '/\\evil.com', '/\\/evil.com', '/\t/evil.com']) {
      expect(isSafeReturnTo(hostile)).toBe(false)
      expect(new URL(hostile, origin).origin).not.toBe(origin)
    }
  })
})
