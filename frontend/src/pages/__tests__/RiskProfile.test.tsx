import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { mockGetProfile } = vi.hoisted(() => ({
  mockGetProfile: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  riskRegisterApi: {
    getProfile: mockGetProfile,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
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
  inherent_score: 16,
  inherent_level: 'high',
  residual_score: 9,
  residual_level: 'medium',
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

describe('RiskProfile', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders hero shell from profile API', async () => {
    mockGetProfile.mockResolvedValue({ data: profileFixture })
    renderProfile()

    expect(await screen.findByTestId('risk-profile-page')).toBeInTheDocument()
    expect(screen.getByTestId('risk-profile-ref')).toHaveTextContent('RSK-00042')
    expect(screen.getByTestId('risk-profile-title')).toHaveTextContent('Supplier disruption')
    expect(screen.getByTestId('risk-profile-status')).toHaveTextContent('active')
    expect(screen.getByTestId('risk-profile-category')).toHaveTextContent('operational')
    expect(screen.getByTestId('risk-profile-gross')).toHaveTextContent('16')
    expect(screen.getByTestId('risk-profile-net')).toHaveTextContent('9')
    expect(screen.getByTestId('risk-profile-owner')).toHaveTextContent('Alex Owner')
    expect(screen.getByTestId('risk-profile-back')).toHaveAttribute('href', '/risk-register')
    expect(mockGetProfile).toHaveBeenCalledWith(42)
  })

  it('shows not-found honesty for 404', async () => {
    mockGetProfile.mockRejectedValue({ response: { status: 404 } })
    renderProfile()

    expect(await screen.findByTestId('risk-profile-not-found')).toBeInTheDocument()
    expect(screen.getByText('risk_register.profile.not_found')).toBeInTheDocument()
  })

  it('shows error honesty with retry', async () => {
    mockGetProfile.mockRejectedValue(new Error('network down'))
    renderProfile()

    expect(await screen.findByTestId('risk-profile-error')).toBeInTheDocument()
    expect(screen.getByTestId('risk-profile-retry')).toBeInTheDocument()
  })

  it('treats invalid riskId as not found without API call', async () => {
    renderProfile('/risk-register/abc')
    expect(await screen.findByTestId('risk-profile-not-found')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockGetProfile).not.toHaveBeenCalled()
    })
  })
})
