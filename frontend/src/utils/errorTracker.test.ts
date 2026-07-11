import { afterEach, describe, expect, it, vi } from 'vitest'
import trackError from './errorTracker'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('trackError', () => {
  it('logs Error message with component/action context', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    trackError(new Error('boom'), { component: 'UsersPage', action: 'load' })
    expect(spy).toHaveBeenCalled()
    expect(String(spy.mock.calls[0][0])).toContain('[QGP Error] UsersPage/load: boom')
  })

  it('stringifies non-Error values and defaults unknown context', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    trackError('raw-fail')
    expect(String(spy.mock.calls[0][0])).toContain('[QGP Error] unknown/unknown: raw-fail')
  })
})
