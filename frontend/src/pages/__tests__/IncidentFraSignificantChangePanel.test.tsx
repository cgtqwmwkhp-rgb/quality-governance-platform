import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Incident } from '../../api/incidentsClient'
import { IncidentFraSignificantChangePanel } from '../IncidentFraSignificantChangePanel'

const mocks = vi.hoisted(() => ({
  listLocations: vi.fn(),
  getAsset: vi.fn(),
  getLocationCoverageGaps: vi.fn(),
  post: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'en' } }),
}))

vi.mock('../../api/client', () => ({
  default: { post: mocks.post },
  complianceScheduleApi: {
    getLocationCoverageGaps: mocks.getLocationCoverageGaps,
  },
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))

vi.mock('../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listLocations: mocks.listLocations,
    getAsset: mocks.getAsset,
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

function incident(id: number): Incident {
  return {
    id,
    reference_number: `INC-${id}`,
    title: `Incident ${id}`,
    description: 'Fire response',
    incident_type: 'injury',
    severity: 'low',
    status: 'closed',
    emergency_services: ['fire'],
    incident_date: '2026-08-06T12:00:00Z',
    reported_date: '2026-08-06T12:00:00Z',
    created_at: '2026-08-06T12:00:00Z',
  }
}

function panel(incidentId: number) {
  return (
    <MemoryRouter>
      <IncidentFraSignificantChangePanel
        key={incidentId}
        incident={incident(incidentId)}
        flagEnabled
      />
    </MemoryRouter>
  )
}

describe('IncidentFraSignificantChangePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mocks.listLocations.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 200, pages: 0 },
    })
    mocks.getLocationCoverageGaps.mockResolvedValue({ data: { items: [] } })
  })

  it('starts with fresh dismissal state when navigating to another incident', async () => {
    const view = render(panel(11))

    expect(await screen.findByTestId('incident-fra-significant-change')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('fra-sigchange-dismiss'))
    await waitFor(() => {
      expect(screen.queryByTestId('incident-fra-significant-change')).not.toBeInTheDocument()
    })

    view.rerender(panel(12))

    expect(await screen.findByTestId('incident-fra-significant-change')).toBeInTheDocument()
    expect(localStorage.getItem('incident_fra_sigchange_dismissed_11')).toBe('1')
    expect(localStorage.getItem('incident_fra_sigchange_dismissed_12')).toBeNull()
  })
})
