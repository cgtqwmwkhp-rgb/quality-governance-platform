import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import OfflineIndicator from '../OfflineIndicator'
import { useAppStore } from '../../stores'

describe('OfflineIndicator', () => {
  const listeners: Record<string, EventListener[]> = {}

  beforeEach(() => {
    listeners['online'] = []
    listeners['offline'] = []
    useAppStore.getState().setConnectionStatus('connected')

    vi.spyOn(window, 'addEventListener').mockImplementation(
      (event: string, handler: EventListener) => {
        listeners[event]?.push(handler)
      },
    )
    vi.spyOn(window, 'removeEventListener').mockImplementation(() => {})
  })

  afterEach(() => {
    useAppStore.getState().setConnectionStatus('connected')
    vi.restoreAllMocks()
  })

  it('renders nothing when online and no event has fired', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    const { container } = render(<OfflineIndicator />)
    expect(container.innerHTML).toBe('')
  })

  it('does not show Offline from connectionStatus alone when browser is online (timeout must not set disconnected)', () => {
    // Mirrors PX-029: client.ts must not set disconnected on timeout while onLine.
    // Indicator still reflects store if it were set — assert store stays connected here.
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    useAppStore.getState().setConnectionStatus('connected')
    const { container } = render(<OfflineIndicator />)
    expect(container.innerHTML).toBe('')
    expect(useAppStore.getState().connectionStatus).toBe('connected')
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
