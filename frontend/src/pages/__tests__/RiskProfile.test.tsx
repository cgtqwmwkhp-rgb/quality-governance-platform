import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  mockGetProfile,
  mockGetTrends,
  mockAssess,
  mockListNotes,
  mockListActivity,
  mockCreateNote,
  mockListActions,
  mockListUpstream,
  mockUpdateOwner,
} = vi.hoisted(() => ({
  mockGetProfile: vi.fn(),
  mockGetTrends: vi.fn(),
  mockAssess: vi.fn(),
  mockListNotes: vi.fn(),
  mockListActivity: vi.fn(),
  mockCreateNote: vi.fn(),
  mockListActions: vi.fn(),
  mockListUpstream: vi.fn(),
  mockUpdateOwner: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  riskRegisterApi: {
    getProfile: mockGetProfile,
    getTrends: mockGetTrends,
    assess: mockAssess,
    listNotes: mockListNotes,
    listActivity: mockListActivity,
    createNote: mockCreateNote,
    listActions: mockListActions,
    listUpstream: mockListUpstream,
    updateOwner: mockUpdateOwner,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../components/UserEmailSearch', () => ({
  UserEmailSearch: ({
    onChange,
    label,
  }: {
    onChange: (email: string, user?: { id: number; full_name: string; email: string }) => void
    label?: string
  }) => (
    <button
      type="button"
      data-testid="mock-owner-picker"
      onClick={() =>
        onChange('blake@example.com', {
          id: 9,
          full_name: 'Blake Owner',
          email: 'blake@example.com',
        })
      }
    >
      {label || 'Pick owner'}
    </button>
  ),
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

import RiskProfile from '../RiskProfile'

function renderProfile(path = '/risk-register/42') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/risk-register/:riskId" element={<RiskProfile />} />
      </Routes>
    </MemoryRouter>,
  )
}

const profileFixture = {
  id: 42,
  reference: 'RSK-00042',
  title: 'Supplier disruption',
  description: 'Key supplier failure',
  category: 'operational',
  status: 'active',
  treatment: 'treat',
  inherent_likelihood: 4,
  inherent_impact: 4,
  inherent_score: 16,
  inherent_level: 'high',
  residual_likelihood: 3,
  residual_impact: 3,
  residual_score: 9,
  residual_level: 'medium',
  trend: 'decreasing' as const,
  risk_owner_id: 7,
  risk_owner_name: 'Alex Owner',
  last_review_date: '2026-06-01T12:00:00',
  next_review_date: '2026-09-01T12:00:00',
  updated_at: '2026-07-01T08:30:00',
  created_at: '2026-01-15T09:00:00',
  assessment_history: [],
  linked_actions: [],
  review_notes: null,
}

const emptyPage = { items: [], total: 0, page: 1, page_size: 50, pages: 1 }

describe('RiskProfile', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockGetTrends.mockResolvedValue({
      data: [{ month: '2026-06', avg_residual: 9, assessment_count: 1 }],
    })
    mockListNotes.mockResolvedValue({ data: emptyPage })
    mockListActivity.mockResolvedValue({ data: emptyPage })
    mockListActions.mockResolvedValue({ data: emptyPage })
    mockListUpstream.mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('renders hero shell from profile API', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    renderProfile()

    expect(await screen.findByTestId('risk-profile-page')).toBeInTheDocument()
    expect(screen.getByTestId('risk-profile-ref')).toHaveTextContent('RSK-00042')
    expect(screen.getByTestId('risk-profile-title')).toHaveTextContent('Supplier disruption')
    expect(screen.getByTestId('risk-profile-owner')).toHaveTextContent('Alex Owner')
    expect(mockListActions).toHaveBeenCalledWith(42, { page_size: 50 })
    expect(mockListUpstream).toHaveBeenCalledWith(42)
    expect(screen.getByTestId('risk-profile-actions')).toBeInTheDocument()
    expect(screen.getByTestId('risk-profile-upstream')).toBeInTheDocument()
  })

  it('lists CAPA actions and create href with returnTo', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    mockListActions.mockResolvedValue({
      data: {
        items: [
          {
            id: 5,
            reference_number: 'CAPA-5',
            title: 'Mitigate supplier',
            status: 'open',
            priority: 'high',
            source_type: 'risk',
            source_id: 42,
            href: '/actions?sourceType=risk&sourceId=42',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      },
    })
    renderProfile()

    await screen.findByTestId('risk-profile-actions-list')
    expect(screen.getByText('CAPA-5')).toBeInTheDocument()
    const createLink = screen.getByTestId('risk-profile-create-action')
    const href = createLink.getAttribute('href') || ''
    expect(href).toContain('create=1')
    expect(href).toContain('sourceType=risk')
    expect(href).toContain('sourceId=42')
    expect(href).toContain(encodeURIComponent('/risk-register/42'))
  })

  it('lists upstream reverse links with deep hrefs', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    mockListUpstream.mockResolvedValue({
      data: {
        items: [
          {
            source_type: 'incident',
            source_id: 7,
            title: 'Spill',
            reference: 'INC-7',
            href: '/incidents/7',
          },
          {
            source_type: 'audit_finding',
            source_id: 501,
            title: 'Missing control',
            reference: 'AF-501',
            href: '/audits/41/execute',
            audit_run_id: 41,
          },
        ],
        total: 2,
      },
    })
    renderProfile()

    await screen.findByTestId('risk-profile-upstream-list')
    expect(screen.getByTestId('risk-profile-upstream-link-incident-7')).toHaveAttribute(
      'href',
      '/incidents/7',
    )
    expect(screen.getByTestId('risk-profile-upstream-link-audit_finding-501')).toHaveAttribute(
      'href',
      '/audits/41/execute',
    )
  })

  it('updates owner via picker and refreshes activity', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    mockUpdateOwner.mockResolvedValue({
      data: { id: 42, risk_owner_id: 9, risk_owner_name: 'Blake Owner' },
    })
    mockListActivity
      .mockResolvedValueOnce({ data: emptyPage })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 3,
              risk_id: 42,
              event_type: 'owner_changed',
              summary: 'Owner changed: Alex Owner → Blake Owner',
              actor_id: 1,
              created_at: '2026-07-17T12:00:00',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
          pages: 1,
        },
      })
    renderProfile()

    await screen.findByTestId('risk-profile-page')
    fireEvent.click(screen.getByTestId('mock-owner-picker'))

    await waitFor(() => {
      expect(mockUpdateOwner).toHaveBeenCalledWith(42, {
        risk_owner_id: 9,
        risk_owner_name: 'Blake Owner',
      })
    })
    expect(await screen.findByTestId('risk-profile-owner-name')).toHaveTextContent('Blake Owner')
  })

  it('submits assess and reloads profile', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    mockAssess.mockResolvedValue({ data: { message: 'ok', trend: 'stable' } })
    renderProfile()

    await screen.findByTestId('risk-profile-page')
    fireEvent.change(screen.getByTestId('risk-profile-assess-residual-likelihood'), {
      target: { value: '2' },
    })
    fireEvent.click(screen.getByTestId('risk-profile-assess-submit'))

    await waitFor(() => {
      expect(mockAssess).toHaveBeenCalledWith(
        42,
        expect.objectContaining({ residual_likelihood: 2 }),
      )
    })
    expect(mockGetProfile).toHaveBeenCalledTimes(2)
  })

  it('posts a note and refreshes activity', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    mockCreateNote.mockResolvedValue({
      data: {
        id: 1,
        risk_id: 42,
        body: 'Follow up with supplier',
        created_by_id: 7,
        created_by_email: 'owner@example.com',
        created_at: '2026-07-10T12:00:00',
      },
    })
    mockListActivity.mockResolvedValueOnce({ data: emptyPage }).mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 9,
            risk_id: 42,
            event_type: 'note_added',
            summary: 'Note added: Follow up with supplier',
            actor_id: 7,
            created_at: '2026-07-10T12:00:00',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      },
    })
    renderProfile()

    await screen.findByTestId('risk-profile-page')
    fireEvent.change(screen.getByTestId('risk-profile-note-input'), {
      target: { value: 'Follow up with supplier' },
    })
    fireEvent.click(screen.getByTestId('risk-profile-note-submit'))

    await waitFor(() => {
      expect(mockCreateNote).toHaveBeenCalledWith(42, 'Follow up with supplier')
    })
  })

  it('shows not-found honesty for 404', async () => {
    mockGetProfile.mockRejectedValue({ response: { status: 404 } })
    renderProfile()
    expect(await screen.findByTestId('risk-profile-not-found')).toBeInTheDocument()
  })

  it('keeps profile when secondary panels 404 (does not false not-found)', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    mockListNotes.mockRejectedValue({ response: { status: 404 } })
    mockListActions.mockRejectedValue({ response: { status: 404 } })
    mockListUpstream.mockRejectedValue({ response: { status: 404 } })
    renderProfile()

    expect(await screen.findByTestId('risk-profile-page')).toBeInTheDocument()
    expect(screen.getByTestId('risk-profile-title')).toHaveTextContent('Supplier disruption')
    expect(screen.queryByTestId('risk-profile-not-found')).not.toBeInTheDocument()
  })

  it('shows error honesty with retry', async () => {
    mockGetProfile.mockRejectedValue(new Error('network down'))
    renderProfile()
    expect(await screen.findByTestId('risk-profile-error')).toBeInTheDocument()
  })

  it('treats invalid riskId as not found without API call', async () => {
    renderProfile('/risk-register/abc')
    expect(await screen.findByTestId('risk-profile-not-found')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockGetProfile).not.toHaveBeenCalled()
    })
  })
})
