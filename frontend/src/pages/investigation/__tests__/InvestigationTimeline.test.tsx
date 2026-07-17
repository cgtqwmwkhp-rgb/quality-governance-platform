import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import InvestigationTimeline, { TIMELINE_FILTER_OPTIONS } from '../InvestigationTimeline'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('InvestigationTimeline filters', () => {
  it('exposes backend-aligned event_type filter values', () => {
    const values = TIMELINE_FILTER_OPTIONS.map((o) => o.value)
    expect(values).toContain('STATUS_CHANGED')
    expect(values).toContain('DATA_UPDATED')
    expect(values).toContain('COMMENT_ADDED')
    expect(values).toContain('PACK_GENERATED')
    expect(values).not.toContain('status_change')
    expect(values).not.toContain('comment')
  })

  it('renders filter control and audit honesty hint', () => {
    render(
      <InvestigationTimeline
        timeline={[]}
        timelineLoading={false}
        timelineFilter="all"
        onTimelineFilterChange={vi.fn()}
        onRefresh={vi.fn()}
      />,
    )

    expect(screen.getByTestId('investigation-timeline-filter')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-timeline-hint')).toHaveTextContent(
      'investigations.timeline.audit_hint',
    )
  })
})
