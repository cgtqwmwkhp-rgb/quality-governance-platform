import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ComplianceSchedule from '../ComplianceSchedule'

const mockListRequirements = vi.fn()
const mockGetStats = vi.fn()
const mockListCatalogue = vi.fn()
const mockGetLocationCoverageGaps = vi.fn()
const mockGetAssuranceCertShelf = vi.fn()

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    listRequirements: (...args: unknown[]) => mockListRequirements(...args),
    getStats: (...args: unknown[]) => mockGetStats(...args),
    listCatalogue: (...args: unknown[]) => mockListCatalogue(...args),
    getLocationCoverageGaps: (...args: unknown[]) => mockGetLocationCoverageGaps(...args),
  },
  complianceAutomationApi: {
    getAssuranceCertShelf: (...args: unknown[]) => mockGetAssuranceCertShelf(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

vi.mock('../../utils/auth', () => ({
  getCurrentUserId: () => 1,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_k: string, fallback?: string) => fallback ?? _k,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../compliance/useOwnershipLabel', () => ({
  useOwnershipLabel: () => (ownership: unknown) => String(ownership ?? ''),
}))

vi.mock('../compliance/RequirementFormDialog', () => ({
  RequirementFormDialog: () => null,
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/compliance-schedule" element={<ComplianceSchedule />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ComplianceSchedule certificates view', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListRequirements.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetStats.mockResolvedValue({
      data: { total_active: 0, current: 0, due_soon: 0, overdue: 0 },
    })
    mockListCatalogue.mockResolvedValue({ data: { items: [] } })
    mockGetLocationCoverageGaps.mockResolvedValue({
      data: {
        total_locations: 0,
        missing_fra: 0,
        missing_fire_drill: 0,
        missing_both: 0,
        items: [],
      },
    })
    mockGetAssuranceCertShelf.mockResolvedValue({
      data: { items: [], total: 0, summary: { valid: 0, due_soon: 0, expired: 0, unknown: 0 }, due_soon_days: 30 },
    })
  })

  it('defaults to obligations and does not call the shelf API', async () => {
    renderAt('/compliance-schedule')
    await waitFor(() => {
      expect(screen.getByTestId('compliance-schedule-view-switcher')).toBeInTheDocument()
    })
    expect(screen.getByTestId('compliance-schedule-view-obligations')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(mockListRequirements).toHaveBeenCalled()
    expect(mockGetAssuranceCertShelf).not.toHaveBeenCalled()
  })

  it('opens certificates view from ?view=certificates without loading obligations', async () => {
    renderAt('/compliance-schedule?view=certificates')
    await waitFor(() => {
      expect(screen.getByTestId('compliance-schedule-view-certificates')).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    })
    await waitFor(() => {
      expect(mockGetAssuranceCertShelf).toHaveBeenCalled()
    })
    expect(mockListRequirements).not.toHaveBeenCalled()
  })

  it('switches to certificates via the view switcher', async () => {
    const user = userEvent.setup()
    renderAt('/compliance-schedule')
    await waitFor(() => {
      expect(screen.getByTestId('compliance-schedule-view-switcher')).toBeInTheDocument()
    })
    await user.click(screen.getByTestId('compliance-schedule-view-certificates'))
    await waitFor(() => {
      expect(mockGetAssuranceCertShelf).toHaveBeenCalled()
    })
  })
})
