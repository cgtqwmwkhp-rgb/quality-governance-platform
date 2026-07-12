import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const pathnameRef = { current: '/a' }

vi.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: pathnameRef.current }),
}))

import { useFocusRestore } from '../useFocusRestore'

describe('useFocusRestore', () => {
  let rafQueue: FrameRequestCallback[]

  beforeEach(() => {
    pathnameRef.current = '/a'
    rafQueue = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      rafQueue.push(cb)
      return rafQueue.length
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  function flushRaf() {
    const queued = [...rafQueue]
    rafQueue = []
    for (const cb of queued) {
      cb(0)
    }
  }

  it('focuses #main-content on first mount when focus is outside main', () => {
    const main = document.createElement('div')
    main.id = 'main-content'
    main.tabIndex = -1
    document.body.appendChild(main)
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    outside.focus()

    renderHook(() => useFocusRestore())
    act(() => {
      flushRaf()
    })

    expect(document.activeElement).toBe(main)
  })

  it('focuses #main-content when navigating to a new path', () => {
    const main = document.createElement('div')
    main.id = 'main-content'
    main.tabIndex = -1
    document.body.appendChild(main)

    const { rerender } = renderHook(() => useFocusRestore())
    act(() => {
      flushRaf()
    })

    const outside = document.createElement('button')
    document.body.appendChild(outside)
    outside.focus()
    expect(document.activeElement).toBe(outside)

    pathnameRef.current = '/b'
    rerender()
    act(() => {
      flushRaf()
    })

    expect(document.activeElement).toBe(main)
  })

  it('does not steal focus when active element is already inside main', () => {
    const main = document.createElement('main')
    main.id = 'main-content'
    main.tabIndex = -1
    document.body.appendChild(main)
    const inside = document.createElement('button')
    main.appendChild(inside)
    inside.focus()

    renderHook(() => useFocusRestore())
    act(() => {
      flushRaf()
    })

    expect(document.activeElement).toBe(inside)
  })

  it('clears saved focus refs on unmount without throwing', () => {
    const main = document.createElement('div')
    main.id = 'main-content'
    main.tabIndex = -1
    document.body.appendChild(main)

    const { unmount } = renderHook(() => useFocusRestore())
    act(() => {
      flushRaf()
    })
    expect(() => unmount()).not.toThrow()
  })
})
