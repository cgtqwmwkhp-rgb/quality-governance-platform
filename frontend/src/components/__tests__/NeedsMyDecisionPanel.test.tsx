/**
 * The panel has four outcomes and three of them look like "nothing to do".
 *
 * What is pinned here is that they are told apart on screen: an empty list is
 * only ever rendered as "you are clear" when the server said every source
 * answered. The surface this replaced showed an empty approvals queue to every
 * user forever, so a test that merely proved "renders without crashing" would
 * have passed on the bug.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const mockMyDecisions = vi.fn()

vi.mock('../../api/client', () => ({
  approvalsApi: {
    myDecisions: (...args: unknown[]) => mockMyDecisions(...args),
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string, options?: Record<string, unknown>) => {
      const template = fallback ?? key
      if (!options) return template
      return template.replace(/\{\{(\w+)\}\}/g, (_, name) => String(options[name] ?? ''))
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

import { NeedsMyDecisionPanel } from '../NeedsMyDecisionPanel'

const LIVE_SOURCES = [
  {
    key: 'investigation_review',
    label: 'Investigations awaiting my review',
    status: 'live',
    count: 0,
  },
  {
    key: 'document_approval',
    label: 'Controlled documents naming me as approver',
    status: 'live',
    count: 0,
  },
  {
    key: 'signature_request',
    label: 'Signature requests awaiting my signature',
    status: 'live',
    count: 0,
  },
]

function respondWith(body: Record<string, unknown>) {
  mockMyDecisions.mockResolvedValue({
    data: {
      items: [],
      total: 0,
      sources_complete: true,
      unavailable_sources: [],
      sources: LIVE_SOURCES,
      ...body,
    },
  })
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <NeedsMyDecisionPanel />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockMyDecisions.mockReset()
})

describe('NeedsMyDecisionPanel', () => {
  it('lists a decision with a link to the screen that records it', async () => {
    respondWith({
      items: [
        {
          key: 'investigation_review:41',
          source: 'investigation_review',
          source_label: 'Investigations awaiting my review',
          decision: 'review',
          title: 'Forklift near miss',
          reference: 'INV-0041',
          requested_at: '2026-08-01T09:00:00Z',
          requested_at_basis: 'last_updated',
          due_at: null,
          deep_link: '/investigations/41',
        },
      ],
      total: 1,
    })

    renderPanel()

    await waitFor(() => expect(screen.getByTestId('needs-my-decision')).toBeInTheDocument())
    expect(screen.getByText('Forklift near miss')).toBeInTheDocument()
    expect(screen.getByText('INV-0041')).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/investigations/41')
    expect(screen.getByTestId('needs-my-decision-count')).toHaveTextContent('1')
  })

  it('captions a date with what the record actually says it is', async () => {
    respondWith({
      items: [
        {
          key: 'investigation_review:41',
          source: 'investigation_review',
          source_label: 'Investigations awaiting my review',
          decision: 'review',
          title: 'Forklift near miss',
          requested_at: '2026-08-01T09:00:00Z',
          // The domain never timestamps the move into under_review, so this date
          // must not be presented as when the review was requested.
          requested_at_basis: 'last_updated',
          due_at: null,
          deep_link: '/investigations/41',
        },
      ],
      total: 1,
    })

    renderPanel()

    await waitFor(() =>
      expect(screen.getByTestId('decision-basis-investigation_review:41')).toHaveTextContent(
        /last updated/i,
      ),
    )
    expect(screen.getByText('No deadline')).toBeInTheDocument()
  })

  it('says so rather than linking when no screen reads the record', async () => {
    respondWith({
      items: [
        {
          key: 'signature_request:7',
          source: 'signature_request',
          source_label: 'Signature requests awaiting my signature',
          decision: 'sign',
          title: 'Annual policy pack',
          reference: 'SIG-0007',
          requested_at: '2026-08-01T09:00:00Z',
          requested_at_basis: 'raised',
          due_at: '2026-08-20T09:00:00Z',
          deep_link: null,
        },
      ],
      total: 1,
    })

    renderPanel()

    await waitFor(() =>
      expect(screen.getByTestId('decision-no-screen-signature_request:7')).toBeInTheDocument(),
    )
    // A guessed route would send someone holding real work to /signatures, which
    // renders a hardcoded empty list and would tell them they have none.
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('says you are clear only when every source answered', async () => {
    respondWith({ items: [], total: 0, sources_complete: true, unavailable_sources: [] })

    renderPanel()

    await waitFor(() => expect(screen.getByTestId('needs-my-decision-clear')).toBeInTheDocument())
    expect(screen.getByTestId('needs-my-decision-clear')).toHaveTextContent(
      'Investigations awaiting my review',
    )
  })

  it('refuses to call an empty list "clear" when a source could not be read', async () => {
    respondWith({
      items: [],
      total: 0,
      sources_complete: false,
      unavailable_sources: ['document_approval'],
      sources: [
        LIVE_SOURCES[0],
        {
          key: 'document_approval',
          label: 'Controlled documents naming me as approver',
          status: 'unavailable',
          count: null,
          reason: 'document_approval_instances is absent from this database.',
        },
        LIVE_SOURCES[2],
      ],
    })

    renderPanel()

    await waitFor(() => expect(screen.getByTestId('needs-my-decision-unknown')).toBeInTheDocument())
    expect(screen.queryByTestId('needs-my-decision-clear')).not.toBeInTheDocument()
    expect(screen.getByTestId('needs-my-decision-unknown')).toHaveTextContent(
      'Controlled documents naming me as approver',
    )
    expect(screen.getByTestId('needs-my-decision-unknown')).toHaveTextContent(
      'document_approval_instances is absent from this database.',
    )
  })

  it('reports a count as a floor when a source is missing from it', async () => {
    respondWith({
      items: [
        {
          key: 'investigation_review:41',
          source: 'investigation_review',
          source_label: 'Investigations awaiting my review',
          decision: 'review',
          title: 'Forklift near miss',
          deep_link: '/investigations/41',
        },
      ],
      total: 1,
      sources_complete: false,
      unavailable_sources: ['document_approval'],
      sources: [
        LIVE_SOURCES[0],
        {
          key: 'document_approval',
          label: 'Controlled documents naming me as approver',
          status: 'unavailable',
          count: null,
          reason: 'absent',
        },
      ],
    })

    renderPanel()

    await waitFor(() => expect(screen.getByTestId('needs-my-decision-partial')).toBeInTheDocument())
    expect(screen.getByTestId('needs-my-decision-count')).toHaveTextContent('at least 1')
  })

  it('names approvals that are in nobody\u2019s queue', async () => {
    respondWith({
      items: [
        {
          key: 'investigation_review:41',
          source: 'investigation_review',
          source_label: 'Investigations awaiting my review',
          decision: 'review',
          title: 'Forklift near miss',
          deep_link: '/investigations/41',
        },
      ],
      total: 1,
      sources: [
        LIVE_SOURCES[0],
        {
          key: 'document_approval',
          label: 'Controlled documents naming me as approver',
          status: 'live',
          count: 0,
          unattributed: 3,
        },
      ],
    })

    renderPanel()

    await waitFor(() =>
      expect(screen.getByTestId('needs-my-decision-unattributed')).toHaveTextContent('3'),
    )
  })

  it('shows a failure with a retry instead of an empty panel', async () => {
    mockMyDecisions.mockRejectedValueOnce(new Error('network'))

    renderPanel()

    await waitFor(() => expect(screen.getByTestId('needs-my-decision-error')).toBeInTheDocument())
    expect(screen.getByTestId('needs-my-decision-error')).toHaveTextContent(
      'not a report that nothing does',
    )

    respondWith({ items: [], total: 0 })
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() => expect(screen.getByTestId('needs-my-decision-clear')).toBeInTheDocument())
  })
})
