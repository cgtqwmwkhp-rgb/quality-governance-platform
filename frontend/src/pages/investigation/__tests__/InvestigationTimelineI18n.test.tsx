import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { createInstance, type i18n as I18n } from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import InvestigationTimeline, { KIND_LABEL, TIMELINE_FILTER_OPTIONS } from '../InvestigationTimeline'
import en from '../../../i18n/locales/en.json'
import type { TimelineEvent } from '../../../api/client'

/**
 * These assertions run against the real en.json through a real i18next instance.
 * The sibling suite stubs `t` so that it echoes the developer fallback, which is
 * why three filter keys were able to go missing without any test failing.
 */

const TIMELINE_NAMESPACE = 'investigations.timeline.'

let i18n: I18n

beforeAll(async () => {
  i18n = createInstance()
  await i18n.use(initReactI18next).init({
    lng: 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    resources: { en: { translation: en } },
    returnNull: false,
  })
})

const baseProps = {
  timeline: [] as TimelineEvent[],
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

function renderWithI18n(props: Partial<typeof baseProps> & Record<string, unknown> = {}) {
  return render(
    <I18nextProvider i18n={i18n}>
      <InvestigationTimeline {...baseProps} {...props} />
    </I18nextProvider>,
  )
}

function collectSourceFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules') continue
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) collectSourceFiles(full, acc)
    else if (entry.endsWith('.ts') || entry.endsWith('.tsx')) acc.push(full)
  }
  return acc
}

describe('investigation timeline i18n coverage', () => {
  it('resolves every filter option label from en.json rather than a developer fallback', () => {
    const unresolved = TIMELINE_FILTER_OPTIONS.filter((opt) => !i18n.exists(opt.labelKey)).map(
      (opt) => opt.labelKey,
    )
    expect(unresolved).toEqual([])
  })

  it('resolves every activity-kind label from en.json', () => {
    const unresolved = Object.values(KIND_LABEL)
      .filter((label) => !i18n.exists(label.key))
      .map((label) => label.key)
    expect(unresolved).toEqual([])
  })

  it('leaves no unreferenced investigations.timeline.* keys in en.json', () => {
    const sources = collectSourceFiles(join(import.meta.dirname, '..', '..', '..'))
      .filter((file) => !file.includes(`${join('i18n', 'locales')}`))
      .map((file) => readFileSync(file, 'utf-8'))
      .join('\n')

    const orphans = Object.keys(en)
      .filter((key) => key.startsWith(TIMELINE_NAMESPACE))
      .filter((key) => !sources.includes(key))

    expect(orphans).toEqual([])
  })

  it('keeps the actor string interpolation in step with its call site', () => {
    expect(en[`${TIMELINE_NAMESPACE}actor` as keyof typeof en]).toContain('{{id}}')
    expect(i18n.t(`${TIMELINE_NAMESPACE}actor`, { id: 7 })).toBe('Actor #7')
  })
})

describe('investigation timeline rendered copy', () => {
  const timeline: TimelineEvent[] = [
    {
      id: 1,
      created_at: '2026-07-20T09:00:00Z',
      event_type: 'STATUS_CHANGED',
      old_value: 'in_progress',
      new_value: 'closed',
      actor_id: 7,
      actor_name: 'Dana Whitfield',
    },
    {
      id: 2,
      created_at: '2026-07-19T09:00:00Z',
      event_type: 'DATA_UPDATED',
      field_path: 'title',
      actor_id: 9,
    },
  ]

  it('labels an audit row with human-readable copy, not the internal kind discriminator', () => {
    renderWithI18n({ timeline })

    const row = screen.getByTestId('timeline-activity-rev-1')
    expect(row).toHaveTextContent('Audit event')
    expect(row).not.toHaveTextContent('revision')
  })

  it('shows the resolved actor name when the API supplies one', () => {
    renderWithI18n({ timeline })

    expect(screen.getByTestId('timeline-actor-rev-1')).toHaveTextContent('Dana Whitfield')
  })

  it('falls back to the opaque actor reference only when no name was resolved', () => {
    renderWithI18n({ timeline })

    expect(screen.getByTestId('timeline-actor-rev-2')).toHaveTextContent('Actor #9')
  })

  it('renders the empty state from en.json rather than a raw key path', () => {
    renderWithI18n()

    expect(screen.getByText('No timeline events')).toBeInTheDocument()
    expect(screen.queryByText(`${TIMELINE_NAMESPACE}empty_title`)).not.toBeInTheDocument()
  })
})
