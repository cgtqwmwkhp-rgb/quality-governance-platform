import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import PortalTrack from '../PortalTrack'

const mockUsePortalAuth = vi.fn()

vi.mock('../../contexts/PortalAuthContext', () => ({
  usePortalAuth: () => mockUsePortalAuth(),
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'https://api.test',
}))

vi.mock('../../components/ReportChat', () => ({
  default: ({ isClosed }: { isClosed: boolean }) => (
    <div data-testid="report-chat" data-closed={String(isClosed)} />
  ),
}))

const REFERENCE = 'INC-2026-0001'
const TRACKING_CODE = 'a1b2c3d4e5f6a1b2c3d4e5f6'

const reportDetail = (overrides: Record<string, unknown> = {}) => ({
  reference_number: REFERENCE,
  // Lowercase on the wire, as the backend now emits for every portal read.
  report_type: 'Incident',
  title: 'Slip hazard in the yard',
  status: 'under_investigation',
  status_label: '🔍 Under Investigation',
  submitted_at: '2026-07-20T09:00:00Z',
  updated_at: '2026-07-21T09:00:00Z',
  priority: '🟠 High',
  timeline: [{ date: '2026-07-20T09:00:00Z', event: 'Report Submitted', icon: '📋' }],
  next_steps: 'Our team is reviewing your report.',
  assigned_to: 'Safety Team',
  ...overrides,
})

const okResponse = (body: unknown) => ({
  ok: true,
  status: 200,
  json: async () => body,
})

const errorResponse = (status: number) => ({
  ok: false,
  status,
  json: async () => ({}),
})

function renderTrack(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/portal/track" element={<PortalTrack />} />
        <Route path="/portal/track/:referenceNumber" element={<PortalTrack />} />
      </Routes>
    </MemoryRouter>,
  )
}

/** The single fetch call made against the report-detail endpoint. */
function detailCall(fetchMock: ReturnType<typeof vi.fn>) {
  const call = fetchMock.mock.calls.find((args) => String(args[0]).includes('/portal/reports/'))
  if (!call) throw new Error('report-detail endpoint was never called')
  return { url: new URL(String(call[0])), init: (call[1] ?? {}) as RequestInit }
}

describe('PortalTrack report lookup', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    mockUsePortalAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      platformToken: null,
    })
    fetchMock = vi.fn().mockResolvedValue(okResponse(reportDetail()))
    vi.stubGlobal('fetch', fetchMock)
  })

  // PX-315 -------------------------------------------------------------

  it('sends the tracking code stashed at submission time', async () => {
    sessionStorage.setItem(`tracking_${REFERENCE}`, TRACKING_CODE)

    renderTrack(`/portal/track/${REFERENCE}`)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(detailCall(fetchMock).url.searchParams.get('tracking_code')).toBe(TRACKING_CODE)
    expect(await screen.findByText('Slip hazard in the yard')).toBeInTheDocument()
  })

  it('sends the tracking code carried by a QR / shared deep link', async () => {
    renderTrack(`/portal/track/${REFERENCE}?tracking_code=${TRACKING_CODE}`)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(detailCall(fetchMock).url.searchParams.get('tracking_code')).toBe(TRACKING_CODE)
    // Persisted so a later refresh or re-search still works.
    expect(sessionStorage.getItem(`tracking_${REFERENCE}`)).toBe(TRACKING_CODE)
  })

  it('sends the platform token when the user is signed in', async () => {
    mockUsePortalAuth.mockReturnValue({
      user: { name: 'Test Engineer', email: 'eng@example.com' },
      isAuthenticated: true,
      platformToken: 'platform-token-123',
    })
    fetchMock.mockImplementation(async (input: string) =>
      String(input).includes('/my-reports/')
        ? okResponse({ items: [] })
        : okResponse(reportDetail()),
    )

    renderTrack(`/portal/track/${REFERENCE}`)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const { init } = detailCall(fetchMock)
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer platform-token-123')
  })

  it('sends a tracking code typed in by the user', async () => {
    const user = userEvent.setup()
    renderTrack('/portal/track')

    await user.type(screen.getByTestId('portal-track-search'), REFERENCE)
    await user.type(screen.getByTestId('portal-track-code'), TRACKING_CODE)
    await user.click(screen.getByTestId('portal-track-search-submit'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(detailCall(fetchMock).url.searchParams.get('tracking_code')).toBe(TRACKING_CODE)
  })

  it('asks for a tracking code on 401 instead of claiming the report does not exist', async () => {
    fetchMock.mockResolvedValue(errorResponse(401))

    renderTrack(`/portal/track/${REFERENCE}`)

    expect(await screen.findByTestId('portal-track-error')).toHaveTextContent(
      'Tracking code needed',
    )
    expect(screen.queryByText('Report not found. Please check your reference number.')).toBeNull()
  })

  it('still reports a genuinely unknown reference as not found', async () => {
    sessionStorage.setItem(`tracking_${REFERENCE}`, TRACKING_CODE)
    fetchMock.mockResolvedValue(errorResponse(404))

    renderTrack(`/portal/track/${REFERENCE}`)

    expect(await screen.findByTestId('portal-track-error')).toHaveTextContent(
      'Report not found. Please check your reference number.',
    )
  })

  // PX-316 -------------------------------------------------------------

  it('renders lowercase wire statuses without the caller re-casing them', async () => {
    sessionStorage.setItem(`tracking_${REFERENCE}`, TRACKING_CODE)
    fetchMock.mockResolvedValue(okResponse(reportDetail({ status: 'closed' })))

    renderTrack(`/portal/track/${REFERENCE}`)

    await screen.findByText('Slip hazard in the yard')
    // A closed report closes the reporter chat; before normalisation this
    // compared against 'CLOSED' and never matched.
    expect(screen.getByTestId('report-chat')).toHaveAttribute('data-closed', 'true')
  })

  it('maps the display-cased report_type from the detail endpoint back to a known type', async () => {
    sessionStorage.setItem(`tracking_${'RTA-2026-0001'}`, TRACKING_CODE)
    fetchMock.mockResolvedValue(
      okResponse(
        reportDetail({ reference_number: 'RTA-2026-0001', report_type: 'Road Traffic Collision' }),
      ),
    )

    renderTrack('/portal/track/RTA-2026-0001')

    // Wait for the detail view specifically; the list view has a type filter
    // containing the same words, which would make a bare text query pass.
    await screen.findByText('Slip hazard in the yard')
    expect(screen.queryByTestId('portal-track-filters')).toBeNull()
    expect(screen.getAllByText('Road Traffic Collision').length).toBeGreaterThan(0)
  })
})
