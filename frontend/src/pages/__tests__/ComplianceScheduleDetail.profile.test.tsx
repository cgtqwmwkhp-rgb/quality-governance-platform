import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ComplianceScheduleDetail from '../ComplianceScheduleDetail'

const { mockGetRequirement, mockListRecords, mockCurrentUserId } = vi.hoisted(() => ({
  mockGetRequirement: vi.fn(),
  mockListRecords: vi.fn(),
  mockCurrentUserId: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  complianceScheduleApi: {
    getRequirement: mockGetRequirement,
    listRecords: mockListRecords,
  },
}))

vi.mock('../../utils/auth', () => ({
  getCurrentUserId: mockCurrentUserId,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../compliance/RecordCompletionSheet', () => ({
  RecordCompletionSheet: () => null,
}))

function requirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    external_id: 'ext-7',
    tenant_id: 1,
    reference_number: 'CSR-2026-0001',
    title: 'Fire Risk Assessment',
    taxonomy_id: 'CS.01',
    description: null,
    regulatory_basis: 'Regulatory Reform (Fire Safety) Order 2005',
    frequency_months: 12,
    frequency_days: null,
    anchor: 'schedule',
    statutory: true,
    next_due_date: '2026-09-06',
    last_completed_at: null,
    owner_id: null,
    location_id: null,
    is_active: true,
    status: 'current',
    created_at: '2026-08-05T09:00:00Z',
    ...overrides,
  }
}

function renderDetail(overrides: Record<string, unknown> = {}) {
  mockGetRequirement.mockResolvedValue({ data: requirement(overrides) })
  mockListRecords.mockResolvedValue({ data: { items: [] } })
  return render(
    <MemoryRouter initialEntries={['/compliance-schedule/7']}>
      <Routes>
        <Route path="/compliance-schedule/:id" element={<ComplianceScheduleDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function waitForLoad() {
  await waitFor(() =>
    expect(screen.getByTestId('compliance-schedule-detail')).toBeInTheDocument(),
  )
}

describe('ComplianceScheduleDetail: the record says how the obligation actually works', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCurrentUserId.mockReturnValue(42)
  })

  it('states the recurrence interval, which the API returns but the page used to drop', async () => {
    renderDetail({ frequency_months: 12 })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-frequency')).toHaveTextContent(
      'Every 12 months',
    )
  })

  it('reports both parts of a combined interval', async () => {
    renderDetail({ frequency_months: 6, frequency_days: 15 })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-frequency')).toHaveTextContent(
      'Every 6 months and 15 days',
    )
  })

  it('says there is no fixed interval rather than leaving the field blank', async () => {
    renderDetail({ frequency_months: null, frequency_days: null })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-frequency')).toHaveTextContent(
      'No fixed interval',
    )
  })

  it('renders the anchor as which date the next one is measured from, not the raw enum', async () => {
    renderDetail({ anchor: 'schedule' })
    await waitForLoad()
    const anchor = screen.getByTestId('compliance-schedule-detail-anchor')
    expect(anchor).toHaveTextContent('Fixed schedule')
    // "schedule" on its own told the reader nothing about the behaviour.
    expect(anchor).not.toHaveTextContent(/^schedule$/)
  })

  it('distinguishes a statutory obligation from a voluntary one, in both directions', async () => {
    renderDetail({ statutory: true })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-statutory')).toHaveTextContent(
      'Required by law',
    )
  })

  it('says explicitly when an obligation is not statutory', async () => {
    renderDetail({ statutory: false })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-statutory')).toHaveTextContent(
      'Not a statutory obligation',
    )
  })

  it('shows who owns it, including when nobody does', async () => {
    renderDetail({ owner_id: null })
    await waitForLoad()
    // An unowned obligation is the case where reminders reach nobody, so the
    // record has to say so rather than show an empty field.
    expect(screen.getByTestId('compliance-schedule-detail-owner')).toHaveTextContent('Unassigned')
  })

  it('recognises the signed-in user as the owner', async () => {
    renderDetail({ owner_id: 42 })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-owner')).toHaveTextContent('Owned by you')
  })

  it('renders the description when the template carries one', async () => {
    renderDetail({ description: 'Assess fire risk across all occupied buildings.' })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-description')).toHaveTextContent(
      'Assess fire risk across all occupied buildings.',
    )
  })

  it('omits the description block entirely when there is none', async () => {
    renderDetail({ description: null })
    await waitForLoad()
    expect(screen.queryByTestId('compliance-schedule-detail-description')).toBeNull()
  })

  it('shows a site-scoped obligation as scoped, and omits the field when it is not', async () => {
    renderDetail({ location_id: 3 })
    await waitForLoad()
    expect(screen.getByTestId('compliance-schedule-detail-location')).toHaveTextContent('#3')
  })

  it('omits location for an organisation-wide obligation', async () => {
    renderDetail({ location_id: null })
    await waitForLoad()
    expect(screen.queryByTestId('compliance-schedule-detail-location')).toBeNull()
  })
})
