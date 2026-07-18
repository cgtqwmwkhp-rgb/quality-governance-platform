import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import InvestigationTimeline, { TIMELINE_FILTER_OPTIONS } from '../InvestigationTimeline'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const baseProps = {
  timeline: [],
  comments: [],
  actions: [],
  evidence: [],
  packs: [],
  timelineLoading: false,
  timelineFilter: 'all',
  onTimelineFilterChange: vi.fn(),
  onRefresh: vi.fn(),
  onAddManualEntry: vi.fn(async () => {}),
}

describe('InvestigationTimeline filters', () => {
  it('exposes backend-aligned event_type filter values plus spine kinds', () => {
    const values = TIMELINE_FILTER_OPTIONS.map((o) => o.value)
    expect(values).toContain('STATUS_CHANGED')
    expect(values).toContain('DATA_UPDATED')
    expect(values).toContain('COMMENT_ADDED')
    expect(values).toContain('PACK_GENERATED')
    expect(values).toContain('CAPA')
    expect(values).toContain('EVIDENCE')
    expect(values).toContain('MANUAL_ENTRY')
    expect(values).not.toContain('status_change')
    expect(values).not.toContain('comment')
  })

  it('renders activity spine hint and manual entry controls', () => {
    render(<InvestigationTimeline {...baseProps} />)

    expect(screen.getByTestId('investigation-timeline-filter')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-timeline-hint')).toHaveTextContent(
      'Unified activity spine',
    )
    expect(screen.getByTestId('investigation-timeline-manual-input')).toBeInTheDocument()
  })
})
