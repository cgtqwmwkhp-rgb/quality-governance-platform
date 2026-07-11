import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getRegisteredShortcuts, useKeyboardShortcuts } from './useKeyboardShortcuts'

describe('useKeyboardShortcuts', () => {
  afterEach(() => {
    // Ensure registry is cleared between tests via unmount
  })

  it('registers shortcuts and exposes them via getRegisteredShortcuts', () => {
    const action = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([
        { key: 'k', modifiers: ['meta'], description: 'Command palette', action },
      ]),
    )

    const registered = getRegisteredShortcuts()
    expect(registered.some((s) => s.key === 'k' && s.description === 'Command palette')).toBe(true)
    unmount()
    expect(getRegisteredShortcuts().some((s) => s.key === 'k')).toBe(false)
  })

  it('invokes action on matching keydown and ignores bare keys in inputs', () => {
    const save = vi.fn()
    const plain = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([
        { key: 's', modifiers: ['ctrl'], description: 'Save', action: save },
        { key: 'g', description: 'Go', action: plain },
      ]),
    )

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }),
      )
    })
    expect(save).toHaveBeenCalledTimes(1)

    const input = document.createElement('input')
    document.body.appendChild(input)
    act(() => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'g', bubbles: true }))
    })
    expect(plain).not.toHaveBeenCalled()

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'g', bubbles: true }))
    })
    expect(plain).toHaveBeenCalledTimes(1)

    input.remove()
    unmount()
  })
})
