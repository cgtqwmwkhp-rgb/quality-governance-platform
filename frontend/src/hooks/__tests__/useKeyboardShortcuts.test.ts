import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getRegisteredShortcuts, useKeyboardShortcuts } from '../useKeyboardShortcuts'

describe('useKeyboardShortcuts', () => {
  afterEach(() => {
    document.body.innerHTML = ''
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

    unmount()
  })

  it('allows modifier shortcuts inside text fields for accessible save flows', () => {
    const save = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([
        { key: 's', modifiers: ['ctrl'], description: 'Save', action: save },
      ]),
    )

    const textarea = document.createElement('textarea')
    document.body.appendChild(textarea)
    act(() => {
      textarea.dispatchEvent(
        new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }),
      )
    })
    expect(save).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('blocks bare-key shortcuts inside select controls', () => {
    const jump = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([{ key: 'j', description: 'Jump', action: jump }]),
    )

    const select = document.createElement('select')
    document.body.appendChild(select)
    act(() => {
      select.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', bubbles: true }))
    })
    expect(jump).not.toHaveBeenCalled()

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', bubbles: true }))
    })
    expect(jump).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('blocks shift-only shortcuts inside text fields (e.g. Shift+?)', () => {
    const help = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([
        { key: '?', modifiers: ['shift'], description: 'Show keyboard shortcuts', action: help },
      ]),
    )

    const input = document.createElement('input')
    document.body.appendChild(input)
    act(() => {
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: '?', shiftKey: true, bubbles: true }),
      )
    })
    expect(help).not.toHaveBeenCalled()

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', { key: '?', shiftKey: true, bubbles: true }),
      )
    })
    expect(help).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('blocks bare-key shortcuts inside ARIA searchbox controls', () => {
    const find = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([{ key: 'f', description: 'Find', action: find }]),
    )

    const searchbox = document.createElement('div')
    searchbox.setAttribute('role', 'searchbox')
    searchbox.tabIndex = 0
    document.body.appendChild(searchbox)
    act(() => {
      searchbox.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', bubbles: true }))
    })
    expect(find).not.toHaveBeenCalled()

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', bubbles: true }))
    })
    expect(find).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('matches shift+alt modifier combinations and calls preventDefault', () => {
    const help = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([
        { key: '?', modifiers: ['shift', 'alt'], description: 'Help', action: help },
      ]),
    )

    const event = new KeyboardEvent('keydown', {
      key: '?',
      shiftKey: true,
      altKey: true,
      bubbles: true,
      cancelable: true,
    })
    const preventSpy = vi.spyOn(event, 'preventDefault')

    act(() => {
      window.dispatchEvent(event)
    })

    expect(help).toHaveBeenCalledTimes(1)
    expect(preventSpy).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('does not fire when required modifiers are missing', () => {
    const undo = vi.fn()
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts([
        { key: 'z', modifiers: ['meta'], description: 'Undo', action: undo },
      ]),
    )

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', bubbles: true }))
    })
    expect(undo).not.toHaveBeenCalled()

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'z', metaKey: true, bubbles: true }),
      )
    })
    expect(undo).toHaveBeenCalledTimes(1)
    unmount()
  })
})
