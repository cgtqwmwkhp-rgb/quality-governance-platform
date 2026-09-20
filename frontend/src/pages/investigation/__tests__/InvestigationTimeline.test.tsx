import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import type { TimelineEvent } from '../../../api/client'
import InvestigationTimeline, {
  TIMELINE_FILTER_OPTIONS,
  TIMELINE_ORIGIN_OPTIONS,
} from '../InvestigationTimeline'

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

describe('InvestigationTimeline source origin (INV-C9)', () => {
  const timeline: TimelineEvent[] = [
    {
      id: -91,
      event_type: 'SOURCE_AUDIT',
      created_at: '2026-07-02T10:00:00Z',
      new_value: 'Incident INC-2026-0001 closed',
      event_metadata: {
        origin: 'source',
        source_feed: 'audit',
        source_label: 'Incident · update',
      },
    },
    {
      id: 1,
      event_type: 'STATUS_CHANGED',
      created_at: '2026-07-01T10:00:00Z',
      event_metadata: { origin: 'investigation' },
    },
  ]

  it('keeps origin out of the event_type filter, which is forwarded to the API', () => {
    const eventTypeValues = TIMELINE_FILTER_OPTIONS.map((o) => o.value)

    expect(eventTypeValues).not.toContain('source')
    expect(eventTypeValues).not.toContain('investigation')
    expect(TIMELINE_ORIGIN_OPTIONS.map((o) => o.value)).toEqual(['all', 'investigation', 'source'])
  })

  it('labels a parent-source row as a source record, not as an investigation audit event', () => {
    render(<InvestigationTimeline {...baseProps} timeline={timeline} />)

    const sourceRow = screen.getByTestId('timeline-activity-src-91')
    expect(sourceRow).toHaveTextContent('Source record')
    expect(sourceRow).toHaveTextContent('Incident · update')
    expect(screen.getByTestId('timeline-activity-rev-1')).toHaveTextContent('Audit event')
  })

  it('shows both origins until the reader narrows to one', () => {
    render(<InvestigationTimeline {...baseProps} timeline={timeline} />)

    expect(screen.getByTestId('timeline-activity-src-91')).toBeInTheDocument()
    expect(screen.getByTestId('timeline-activity-rev-1')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('investigation-timeline-origin-source'))
    expect(screen.getByTestId('timeline-activity-src-91')).toBeInTheDocument()
    expect(screen.queryByTestId('timeline-activity-rev-1')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('investigation-timeline-origin-investigation'))
    expect(screen.queryByTestId('timeline-activity-src-91')).not.toBeInTheDocument()
    expect(screen.getByTestId('timeline-activity-rev-1')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('investigation-timeline-origin-all'))
    expect(screen.getByTestId('timeline-activity-src-91')).toBeInTheDocument()
    expect(screen.getByTestId('timeline-activity-rev-1')).toBeInTheDocument()
  })

  it('announces which origin is selected', () => {
    render(<InvestigationTimeline {...baseProps} timeline={timeline} />)

    expect(screen.getByTestId('investigation-timeline-origin-all')).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    fireEvent.click(screen.getByTestId('investigation-timeline-origin-source'))

    expect(screen.getByTestId('investigation-timeline-origin-source')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByTestId('investigation-timeline-origin-all')).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})
