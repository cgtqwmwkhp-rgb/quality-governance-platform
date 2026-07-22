import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { HighlightRail, HIGHLIGHT_RAIL_SCROLL_KEY } from '../HighlightRail'
import type { HighlightChip } from '../dashboardMetrics'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

function chips(n: number): HighlightChip[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `chip-${i}`,
    label: `Item ${i}`,
    tone: i === 0 ? 'critical' : 'warning',
    href: `/path-${i}`,
  }))
}

describe('HighlightRail', () => {
  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  it('shows all-clear when empty', () => {
    render(
      <MemoryRouter>
        <HighlightRail chips={[]} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('highlight-rail-empty')).toBeInTheDocument()
  })

  it('defaults to static wrap (no marquee) when many chips', () => {
    render(
      <MemoryRouter>
        <HighlightRail chips={chips(6)} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('highlight-rail')).toBeInTheDocument()
    expect(screen.getByTestId('highlight-rail-scroll-toggle')).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    // No duplicated marquee copies when scroll is off
    expect(screen.getAllByTestId(/^highlight-chip-/)).toHaveLength(6)
  })

  it('toggle enables auto-scroll and persists preference', () => {
    render(
      <MemoryRouter>
        <HighlightRail chips={chips(6)} />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByTestId('highlight-rail-scroll-toggle'))
    expect(screen.getByTestId('highlight-rail-scroll-toggle')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(localStorage.getItem(HIGHLIGHT_RAIL_SCROLL_KEY)).toBe('true')
    // Marquee duplicates the chip set
    expect(screen.getAllByTestId(/^highlight-chip-/)).toHaveLength(12)
  })

  it('hides toggle when chips fit without scrolling', () => {
    render(
      <MemoryRouter>
        <HighlightRail chips={chips(3)} />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('highlight-rail-scroll-toggle')).not.toBeInTheDocument()
  })

  it('respects reduced-motion and never marquees', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes('prefers-reduced-motion'),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    localStorage.setItem(HIGHLIGHT_RAIL_SCROLL_KEY, 'true')
    render(
      <MemoryRouter>
        <HighlightRail chips={chips(6)} />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('highlight-rail-scroll-toggle')).not.toBeInTheDocument()
    expect(screen.getAllByTestId(/^highlight-chip-/)).toHaveLength(6)
  })
})
