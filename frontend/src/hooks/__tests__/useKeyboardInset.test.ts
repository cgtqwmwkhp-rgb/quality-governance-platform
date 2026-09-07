/**
 * AUD-P3 keyboard inset.
 *
 * The defect this measures is not "the bar is too low" — it is that mobile
 * Safari keeps the layout viewport at full height when the virtual keyboard
 * opens, so `position: fixed; bottom: 0` resolves to a line behind the
 * keyboard and buries Next / Take Photo / Choose from Library. The only signal
 * for that overlap is `window.visualViewport`, so these cases pin the
 * arithmetic and the lifecycle rather than any pixel.
 */
import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { KEYBOARD_INSET_VAR, keyboardInsetFrom, useKeyboardInset } from '../useKeyboardInset'

type FakeViewport = {
  height: number
  offsetTop: number
  addEventListener: (type: string, fn: () => void) => void
  removeEventListener: (type: string, fn: () => void) => void
  /** Test-only: fire the listeners the hook registered. */
  emit: (type: string) => void
  listenerCount: () => number
}

function fakeViewport(height: number, offsetTop = 0): FakeViewport {
  const listeners = new Map<string, Set<() => void>>()
  return {
    height,
    offsetTop,
    addEventListener(type, fn) {
      const set = listeners.get(type) ?? new Set()
      set.add(fn)
      listeners.set(type, set)
    },
    removeEventListener(type, fn) {
      listeners.get(type)?.delete(fn)
    },
    emit(type) {
      for (const fn of listeners.get(type) ?? []) fn()
    },
    listenerCount() {
      let total = 0
      for (const set of listeners.values()) total += set.size
      return total
    },
  }
}

function setLayoutHeight(height: number) {
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: height })
}

function installViewport(viewport: FakeViewport | undefined) {
  Object.defineProperty(window, 'visualViewport', { configurable: true, value: viewport })
}

function readVar(): string {
  return document.documentElement.style.getPropertyValue(KEYBOARD_INSET_VAR)
}

afterEach(() => {
  installViewport(undefined)
  document.documentElement.style.removeProperty(KEYBOARD_INSET_VAR)
})

describe('keyboardInsetFrom', () => {
  it('is zero when nothing is covering the viewport', () => {
    expect(keyboardInsetFrom(844, { height: 844, offsetTop: 0 })).toBe(0)
  })

  it('measures the overlap when the keyboard shrinks the visual viewport only', () => {
    // iPhone 12/13/14: 844 layout px, ~336 px of keyboard.
    expect(keyboardInsetFrom(844, { height: 508, offsetTop: 0 })).toBe(336)
  })

  it('contributes nothing on engines that shrink the layout viewport instead', () => {
    // There the keyboard has already moved bottom:0, and both numbers fall
    // together, so lifting the bar again would leave a gap.
    expect(keyboardInsetFrom(508, { height: 508, offsetTop: 0 })).toBe(0)
  })

  it('ignores an overlap too small to be a keyboard', () => {
    // A collapsing browser toolbar. Acting on this makes the bar jitter while
    // the auditor scrolls the question list.
    expect(keyboardInsetFrom(844, { height: 820, offsetTop: 0 })).toBe(0)
  })

  it('counts a scrolled visual viewport so a pinch-zoom still shows the bar', () => {
    expect(keyboardInsetFrom(844, { height: 600, offsetTop: 100 })).toBe(144)
  })

  it('clamps so a zoom can never push the action bar off the top', () => {
    // A deep zoom leaves 50 px of visual viewport 100 px down the page: a raw
    // 694 px lift would put the action bar above the header.
    expect(keyboardInsetFrom(844, { height: 50, offsetTop: 100 })).toBe(Math.round(844 * 0.6))
    // Below the ceiling the real measurement is used, not the clamp.
    expect(keyboardInsetFrom(844, { height: 100, offsetTop: 400 })).toBe(344)
  })

  it('declines to guess when there is no visual viewport or no usable numbers', () => {
    expect(keyboardInsetFrom(844, null)).toBe(0)
    expect(keyboardInsetFrom(844, undefined)).toBe(0)
    expect(keyboardInsetFrom(0, { height: 508, offsetTop: 0 })).toBe(0)
    expect(keyboardInsetFrom(Number.NaN, { height: 508, offsetTop: 0 })).toBe(0)
    expect(keyboardInsetFrom(844, { height: Number.NaN, offsetTop: 0 })).toBe(0)
    expect(keyboardInsetFrom(844, { height: 508, offsetTop: Number.NaN })).toBe(336)
  })
})

describe('useKeyboardInset', () => {
  it('publishes 0px while no keyboard is open', () => {
    setLayoutHeight(844)
    installViewport(fakeViewport(844))
    renderHook(() => useKeyboardInset())
    expect(readVar()).toBe('0px')
  })

  it('republishes when the keyboard opens and again when it closes', () => {
    setLayoutHeight(844)
    const viewport = fakeViewport(844)
    installViewport(viewport)
    renderHook(() => useKeyboardInset())

    viewport.height = 508
    viewport.emit('resize')
    expect(readVar()).toBe('336px')

    viewport.height = 844
    viewport.emit('resize')
    expect(readVar()).toBe('0px')
  })

  it('follows a scrolled visual viewport, not just a resized one', () => {
    setLayoutHeight(844)
    const viewport = fakeViewport(844)
    installViewport(viewport)
    renderHook(() => useKeyboardInset())

    viewport.height = 600
    viewport.offsetTop = 100
    viewport.emit('scroll')
    expect(readVar()).toBe('144px')
  })

  it('leaves no stale lift behind for the next page', () => {
    setLayoutHeight(844)
    const viewport = fakeViewport(508)
    installViewport(viewport)
    const { unmount } = renderHook(() => useKeyboardInset())
    expect(readVar()).toBe('336px')

    unmount()
    // Not "0px": the property is gone, so every consumer is back on its own
    // fallback rather than on a value this page happened to leave.
    expect(readVar()).toBe('')
    expect(viewport.listenerCount()).toBe(0)
  })

  it('sets nothing at all when the browser has no visual viewport', () => {
    setLayoutHeight(844)
    installViewport(undefined)
    renderHook(() => useKeyboardInset())
    expect(readVar()).toBe('')
  })

  it('does not measure while disabled', () => {
    setLayoutHeight(844)
    installViewport(fakeViewport(508))
    renderHook(() => useKeyboardInset(false))
    expect(readVar()).toBe('')
  })
})
