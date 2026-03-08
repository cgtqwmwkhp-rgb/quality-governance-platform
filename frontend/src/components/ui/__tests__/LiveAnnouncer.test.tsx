import { describe, it, expect } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { LiveAnnouncerProvider, useLiveAnnouncer } from '../LiveAnnouncer'

function AnnounceButton() {
  const { announce } = useLiveAnnouncer()
  return (
    <>
      <button onClick={() => announce('Polite message')}>Polite</button>
      <button onClick={() => announce('Urgent alert', 'assertive')}>Assertive</button>
    </>
  )
}

describe('LiveAnnouncerProvider', () => {
  it('renders children and hidden live regions', () => {
    render(
      <LiveAnnouncerProvider>
        <div>App content</div>
      </LiveAnnouncerProvider>,
    )

    expect(screen.getByText('App content')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('announces polite messages into the status region', async () => {
    render(
      <LiveAnnouncerProvider>
        <AnnounceButton />
      </LiveAnnouncerProvider>,
    )

    await act(async () => {
      screen.getByText('Polite').click()
      // requestAnimationFrame is used internally
      await new Promise((r) => requestAnimationFrame(r))
    })

    expect(screen.getByRole('status')).toHaveTextContent('Polite message')
  })

  it('announces assertive messages into the alert region', async () => {
    render(
      <LiveAnnouncerProvider>
        <AnnounceButton />
      </LiveAnnouncerProvider>,
    )

    await act(async () => {
      screen.getByText('Assertive').click()
      await new Promise((r) => requestAnimationFrame(r))
    })

    expect(screen.getByRole('alert')).toHaveTextContent('Urgent alert')
  })
})
