import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import OfflineIndicator from '../OfflineIndicator'

describe('OfflineIndicator', () => {
  const listeners: Record<string, EventListener[]> = {}

  beforeEach(() => {
    listeners['online'] = []
    listeners['offline'] = []

    vi.spyOn(window, 'addEventListener').mockImplementation(
      (event: string, handler: EventListener) => {
        listeners[event]?.push(handler)
      },
    )
    vi.spyOn(window, 'removeEventListener').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders nothing when online and no event has fired', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    const { container } = render(<OfflineIndicator />)
    expect(container.innerHTML).toBe('')
  })

  it('shows offline banner when an offline event fires', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    render(<OfflineIndicator />)

    act(() => {
      listeners['offline'].forEach((fn) => fn(new Event('offline')))
    })

    expect(screen.getByText(/Offline/i)).toBeInTheDocument()
  })

  it('shows back-online banner when online event fires after being offline', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true })
    render(<OfflineIndicator />)

    act(() => {
      listeners['offline'].forEach((fn) => fn(new Event('offline')))
    })

    act(() => {
      listeners['online'].forEach((fn) => fn(new Event('online')))
    })

    expect(screen.getByText(/Back online/i)).toBeInTheDocument()
  })
})
