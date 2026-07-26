/**
 * PX-172: a bare `window` keydown listener meant Escape inside a modal both
 * closed the dialog and navigated the detail page back to its register, so the
 * user's typed work vanished and the route changed in one keystroke.
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEscapeToGoBack } from '../useEscapeToGoBack'

function Harness({
  enabled = true,
  onGoBack,
  withDialog = false,
}: {
  enabled?: boolean
  onGoBack: () => void
  withDialog?: boolean
}) {
  useEscapeToGoBack(enabled, onGoBack)
  return (
    <div>
      <input aria-label="Page field" />
      {withDialog ? (
        <div role="dialog" aria-label="Start investigation">
          <input aria-label="Dialog field" />
        </div>
      ) : null}
    </div>
  )
}

describe('useEscapeToGoBack', () => {
  it('goes back when Escape is pressed on the bare page', async () => {
    const user = userEvent.setup()
    const onGoBack = vi.fn()
    render(<Harness onGoBack={onGoBack} />)

    await user.click(screen.getByLabelText('Page field'))
    await user.keyboard('{Escape}')

    expect(onGoBack).toHaveBeenCalledTimes(1)
  })

  it('does not navigate when Escape is pressed inside a dialog', async () => {
    const user = userEvent.setup()
    const onGoBack = vi.fn()
    render(<Harness onGoBack={onGoBack} withDialog />)

    await user.click(screen.getByLabelText('Dialog field'))
    await user.keyboard('{Escape}')

    expect(onGoBack).not.toHaveBeenCalled()
  })

  it('does not navigate while a dialog is open, even if focus sits outside it', async () => {
    const user = userEvent.setup()
    const onGoBack = vi.fn()
    render(<Harness onGoBack={onGoBack} withDialog />)

    await user.click(screen.getByLabelText('Page field'))
    await user.keyboard('{Escape}')

    expect(onGoBack).not.toHaveBeenCalled()
  })

  it('yields to another handler that already claimed the keystroke', () => {
    const onGoBack = vi.fn()
    render(<Harness onGoBack={onGoBack} />)

    const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
    event.preventDefault()
    window.dispatchEvent(event)

    expect(onGoBack).not.toHaveBeenCalled()
  })

  it('ignores keys other than Escape', async () => {
    const user = userEvent.setup()
    const onGoBack = vi.fn()
    render(<Harness onGoBack={onGoBack} />)

    await user.click(screen.getByLabelText('Page field'))
    await user.keyboard('{Enter}')

    expect(onGoBack).not.toHaveBeenCalled()
  })

  it('does nothing at all while disabled, and detaches its listener', async () => {
    const user = userEvent.setup()
    const onGoBack = vi.fn()
    const { unmount } = render(<Harness enabled={false} onGoBack={onGoBack} />)

    await user.keyboard('{Escape}')
    expect(onGoBack).not.toHaveBeenCalled()

    unmount()
    await user.keyboard('{Escape}')
    expect(onGoBack).not.toHaveBeenCalled()
  })
})
