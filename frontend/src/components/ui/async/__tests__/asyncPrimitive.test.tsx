import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AsyncState } from '../AsyncState'
import { ErrorState } from '../ErrorState'
import { DEFAULT_STALL_MS, resolveAsyncStatus } from '../asyncStatus'

afterEach(() => {
  vi.useRealTimers()
})

describe('resolveAsyncStatus', () => {
  it('reports loading before anything else', () => {
    expect(resolveAsyncStatus({ loading: true, error: 'boom', isEmpty: true })).toBe('loading')
  })

  it('reports error ahead of empty so a failure is never shown as "no records"', () => {
    expect(resolveAsyncStatus({ error: 'Service unavailable', isEmpty: true })).toBe('error')
  })

  it('treats a blank error message as a failure, not as success', () => {
    expect(resolveAsyncStatus({ error: '', isEmpty: true })).toBe('error')
  })

  it('reports empty only when the load succeeded and returned nothing', () => {
    expect(resolveAsyncStatus({ error: null, isEmpty: true })).toBe('empty')
  })

  it('reports ready when there is data', () => {
    expect(resolveAsyncStatus({ error: null, isEmpty: false })).toBe('ready')
  })

  it('defaults to ready when nothing is passed', () => {
    expect(resolveAsyncStatus({})).toBe('ready')
  })
})

describe('AsyncState', () => {
  const empty = <p>No records yet</p>
  const rows = <p>Row one</p>

  it('renders the loading fallback and nothing else', () => {
    render(
      <AsyncState loading loadingFallback={<p>Loading rows</p>} empty={empty}>
        {rows}
      </AsyncState>,
    )

    expect(screen.getByText('Loading rows')).toBeInTheDocument()
    expect(screen.queryByText('No records yet')).not.toBeInTheDocument()
    expect(screen.queryByText('Row one')).not.toBeInTheDocument()
  })

  it('shows the failure and retry instead of the empty state when the load failed', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()

    render(
      <AsyncState
        error="Service unavailable"
        isEmpty
        onRetry={onRetry}
        errorTitle="Near misses unavailable"
        empty={empty}
      >
        {rows}
      </AsyncState>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Near misses unavailable')
    expect(screen.getByText('Service unavailable')).toBeInTheDocument()
    // The whole point of the primitive: an error must never read as "nothing here".
    expect(screen.queryByText('No records yet')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('async-state-error-retry'))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows the empty state only when the load succeeded with no rows', () => {
    render(
      <AsyncState error={null} isEmpty empty={empty}>
        {rows}
      </AsyncState>,
    )

    expect(screen.getByText('No records yet')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('falls through to children when empty with no empty node supplied', () => {
    render(
      <AsyncState error={null} isEmpty>
        {rows}
      </AsyncState>,
    )

    expect(screen.getByText('Row one')).toBeInTheDocument()
  })

  it('renders children unwrapped so it can sit inside a table body', () => {
    const { container } = render(
      <table>
        <AsyncState error={null}>
          <tbody data-testid="rows">
            <tr>
              <td>Row one</td>
            </tr>
          </tbody>
        </AsyncState>
      </table>,
    )

    expect(container.querySelector('table > tbody')).not.toBeNull()
  })

  it('tells the user a load has stalled and offers a way out', () => {
    vi.useFakeTimers()
    const onRetry = vi.fn()

    render(
      <AsyncState loading onRetry={onRetry} loadingFallback={<p>Loading rows</p>} />,
    )

    expect(screen.queryByTestId('async-state-stalled')).not.toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(DEFAULT_STALL_MS)
    })

    // The skeleton stays; the user now also knows why and can act on it.
    expect(screen.getByText('Loading rows')).toBeInTheDocument()
    expect(screen.getByTestId('async-state-stalled')).toHaveTextContent(
      /taking longer than expected/i,
    )
    screen.getByTestId('async-state-stalled-retry').click()
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('does not report a stall once the load finishes', () => {
    vi.useFakeTimers()

    const { rerender } = render(
      <AsyncState loading loadingFallback={<p>Loading rows</p>}>
        {rows}
      </AsyncState>,
    )

    rerender(
      <AsyncState loading={false} error={null}>
        {rows}
      </AsyncState>,
    )

    act(() => {
      vi.advanceTimersByTime(DEFAULT_STALL_MS * 2)
    })

    expect(screen.queryByTestId('async-state-stalled')).not.toBeInTheDocument()
    expect(screen.getByText('Row one')).toBeInTheDocument()
  })

  it('never stalls when the guard is disabled', () => {
    vi.useFakeTimers()

    render(<AsyncState loading stallAfterMs={0} loadingFallback={<p>Loading rows</p>} />)

    act(() => {
      vi.advanceTimersByTime(DEFAULT_STALL_MS * 10)
    })

    expect(screen.queryByTestId('async-state-stalled')).not.toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('is announced assertively and omits retry when there is nothing to retry', () => {
    render(<ErrorState title="Documents unavailable" message="503 Service Unavailable" />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveAttribute('aria-live', 'assertive')
    expect(alert).toHaveTextContent('Documents unavailable')
    expect(screen.queryByTestId('async-error-state-retry')).not.toBeInTheDocument()
  })
})
