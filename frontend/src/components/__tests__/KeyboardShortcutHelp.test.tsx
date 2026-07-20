/**
 * Mount + interaction coverage for the orphaned KeyboardShortcutHelp surface.
 * Complements useKeyboardShortcuts.test.ts hook registry paths (#901).
 */
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import KeyboardShortcutHelp from '../KeyboardShortcutHelp'
import { expectNoA11yViolations } from '../../test/axe-helper'

function pressShiftQuestion() {
  act(() => {
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: '?', shiftKey: true, bubbles: true }),
    )
  })
}

describe('KeyboardShortcutHelp', () => {
  it('opens the shortcuts dialog on Shift+?', async () => {
    render(<KeyboardShortcutHelp />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    pressShiftQuestion()

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument()
  })

  it('does not open the shortcuts dialog when Shift+? is typed in an input', async () => {
    render(
      <>
        <input aria-label="Notes" />
        <KeyboardShortcutHelp />
      </>,
    )

    const input = screen.getByRole('textbox', { name: 'Notes' })
    act(() => {
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: '?', shiftKey: true, bubbles: true }),
      )
    })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('lists the help shortcut when the dialog is open', async () => {
    render(<KeyboardShortcutHelp />)

    pressShiftQuestion()

    expect(screen.getByText('Show keyboard shortcuts')).toBeInTheDocument()
  })

  it('closes the dialog when the user dismisses it', async () => {
    const user = userEvent.setup()
    render(<KeyboardShortcutHelp />)

    pressShiftQuestion()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('has no axe violations when the dialog is open', async () => {
    const { container } = render(<KeyboardShortcutHelp />)

    pressShiftQuestion()

    await expectNoA11yViolations(container)
  })
})
