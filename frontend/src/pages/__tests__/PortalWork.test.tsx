import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PortalWork from '../PortalWork'

const mockList = vi.fn()
const mockListMyPending = vi.fn()
const mockListMyAssignments = vi.fn()
const mockGetByUserMe = vi.fn()
const mockMyTraining = vi.fn()
const mockRecordOpen = vi.fn()
const mockToastError = vi.fn()
const mockAnnounce = vi.fn()

vi.mock('../../api/client', () => ({
  actionsApi: {
    list: (...args: unknown[]) => mockList(...args),
  },
  policyAcknowledgmentsApi: {
    listMyPending: (...args: unknown[]) => mockListMyPending(...args),
    recordOpen: (...args: unknown[]) => mockRecordOpen(...args),
  },
  documentCampaignApi: {
    listMyAssignments: (...args: unknown[]) => mockListMyAssignments(...args),
  },
  engineersApi: {
    getByUserMe: (...args: unknown[]) => mockGetByUserMe(...args),
  },
  trainingMatrixApi: {
    myTraining: (...args: unknown[]) => mockMyTraining(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Request failed',
}))

vi.mock('../../api/trainingMatrixClient', () => ({
  ATLAS_HUB_URL: 'https://www.atlas-hub.co.uk/o/test/',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}))

vi.mock('../../components/ui/LiveAnnouncer', () => ({
  useLiveAnnouncer: () => ({ announce: mockAnnounce }),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <PortalWork />
    </MemoryRouter>,
  )
}

describe('PortalWork CUJ-P10', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            title: 'Close CAPA',
            description: 'Do the thing',
            action_type: 'corrective',
            priority: 'high',
            status: 'open',
            display_status: 'open',
            action_key: 'capa:1',
            source_type: 'audit_finding',
            source_id: 9,
            due_date: '2020-01-01',
            created_at: '2026-07-01T10:00:00Z',
            reference_number: 'ACT-0001',
          },
        ],
        total: 1,
      },
    })
    mockListMyPending.mockResolvedValue({ data: { items: [], total: 0 } })
    mockListMyAssignments.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetByUserMe.mockResolvedValue({ data: { linked: false } })
    mockMyTraining.mockRejectedValue({
      isAxiosError: true,
      response: { status: 404 },
    })
  })

  it('requests assigned_to=me and renders action + unlinked passport', async () => {
    renderPage()

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 20, undefined, undefined, undefined, {
        assigned_to: 'me',
      })
    })

    expect(await screen.findByTestId('portal-work-actions')).toBeInTheDocument()
    expect(screen.getByText('Close CAPA')).toBeInTheDocument()
    expect(screen.getByTestId('portal-work-actions-filter-label')).toHaveTextContent(
      'assigned_to=me',
    )
    expect(screen.getByTestId('portal-work-reading')).toBeInTheDocument()
    expect(screen.getByText(/No pending reads/i)).toBeInTheDocument()
    expect(await screen.findByTestId('portal-work-training-unlinked')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByTestId('portal-work-passport-link-toggle'))
    expect(await screen.findByTestId('portal-work-passport-unlinked')).toBeInTheDocument()
    expect(screen.getByText(/Contact your supervisor/i)).toBeInTheDocument()
  })

  it('auto-collapses long assigned-actions lists and lets the user expand again', async () => {
    mockList.mockResolvedValue({
      data: {
        items: Array.from({ length: 5 }, (_, i) => ({
          id: i + 1,
          title: `Action ${i + 1}`,
          description: 'Do the thing',
          action_type: 'corrective',
          priority: 'high',
          status: 'open',
          display_status: 'open',
          action_key: `capa:${i + 1}`,
          source_type: 'audit_finding',
          source_id: 9,
          due_date: '2026-08-01',
          created_at: '2026-07-01T10:00:00Z',
          reference_number: `ACT-000${i + 1}`,
        })),
        total: 5,
      },
    })

    const user = userEvent.setup()
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('portal-work-actions-count')).toHaveTextContent('5')
    })
    expect(screen.queryByText('Action 1')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('portal-work-actions-toggle'))
    expect(await screen.findByText('Action 1')).toBeInTheDocument()
    expect(screen.getByText('Action 5')).toBeInTheDocument()
  })

  it('shows personal training gaps with Atlas CTA and compliant modules', async () => {
    mockGetByUserMe.mockResolvedValue({
      data: {
        linked: true,
        id: 10,
        external_id: 'eng-1',
        user_id: 42,
        job_title: 'Field Engineer',
        employee_number: 'E-42',
        is_active: true,
      },
    })
    mockMyTraining.mockResolvedValue({
      items: [
        {
          atlas_name: 'David Harris',
          course_key: 'info-sec',
          course_display_name: 'Information Security',
          frequency_years: 1,
          status: 'overdue',
          qgp_due_on: '2026-01-01',
          expires_on: '2026-06-01',
          passed_on: '2025-01-01',
          atlas_hub_url: 'https://www.atlas-hub.co.uk/o/test/',
          expiry_without_passed: false,
        },
        {
          atlas_name: 'David Harris',
          course_key: 'ladders',
          course_display_name: 'Ladders And Stepladders',
          frequency_years: 3,
          status: 'compliant',
          qgp_due_on: '2028-01-01',
          expires_on: '2028-01-01',
          passed_on: '2025-01-01',
          atlas_hub_url: 'https://www.atlas-hub.co.uk/o/test/',
          expiry_without_passed: false,
        },
      ],
      total: 2,
      atlas_hub_url: 'https://www.atlas-hub.co.uk/o/test/',
    })

    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    renderPage()

    expect(await screen.findByTestId('portal-work-training-summary')).toHaveTextContent('1/2 modules OK')
    expect(screen.getByTestId('portal-work-training-gaps')).toHaveTextContent('Information Security')
    expect(screen.getByRole('button', { name: /Complete in Atlas/i })).toBeInTheDocument()
    screen.getByRole('button', { name: /Complete in Atlas/i }).click()
    expect(openSpy).toHaveBeenCalledWith(
      'https://www.atlas-hub.co.uk/o/test/',
      '_blank',
      'noopener,noreferrer',
    )
    expect(screen.getByText(/Show 1 compliant module/i)).toBeInTheDocument()
    openSpy.mockRestore()
  })

  it('shows honest empty actions when server returns none', async () => {
    mockList.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetByUserMe.mockResolvedValue({
      data: {
        linked: true,
        id: 10,
        external_id: 'eng-1',
        user_id: 42,
        job_title: 'Field Engineer',
        employee_number: 'E-42',
        is_active: true,
      },
    })

    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText(/No actions assigned to you/i)).toBeInTheDocument()
    await user.click(screen.getByTestId('portal-work-passport-link-toggle'))
    expect(await screen.findByTestId('portal-work-passport-linked')).toBeInTheDocument()
    expect(screen.getByText('Field Engineer')).toBeInTheDocument()
  })

  it('surfaces actions filter failure without silent empty success', async () => {
    mockList.mockRejectedValue(new Error('Server filter failed'))
    mockGetByUserMe.mockResolvedValue({
      data: { linked: true, id: 10, external_id: 'e', user_id: 1, is_active: true },
    })

    renderPage()

    expect(await screen.findByTestId('portal-work-actions-error')).toBeInTheDocument()
    expect(mockToastError).toHaveBeenCalled()
  })

  it('shows pending campaign assignments with continue link', async () => {
    mockListMyAssignments.mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            document_id: 12,
            document_title: 'Fire Safety SOP',
            campaign_title: 'Annual refresh',
            status: 'pending',
            due_date: '2026-09-01',
          },
        ],
        total: 1,
      },
    })

    renderPage()

    expect(await screen.findByTestId('portal-work-campaigns')).toBeInTheDocument()
    expect(screen.getByText('Fire Safety SOP')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Continue reading/i })).toBeInTheDocument()
  })

  it('suppresses duplicate policy-ack cards when an active campaign covers the same document', async () => {
    mockListMyPending.mockResolvedValue({
      data: {
        items: [
          {
            id: 50,
            requirement_id: 1,
            policy_id: 99,
            user_id: 1,
            status: 'pending',
            assigned_at: '2026-07-01T10:00:00Z',
            due_date: '2026-09-01',
            quiz_attempts: 0,
            reminders_sent: 0,
          },
          {
            id: 51,
            requirement_id: 2,
            policy_id: 77,
            user_id: 1,
            status: 'pending',
            assigned_at: '2026-07-01T10:00:00Z',
            due_date: '2026-10-01',
            quiz_attempts: 0,
            reminders_sent: 0,
          },
        ],
        total: 2,
      },
    })
    mockListMyAssignments.mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            document_id: 501,
            linked_policy_id: 99,
            document_title: 'Fire Safety SOP',
            campaign_title: 'Annual refresh',
            status: 'pending',
            due_date: '2026-09-01',
          },
        ],
        total: 1,
      },
    })

    renderPage()

    expect(await screen.findByTestId('portal-work-campaigns')).toBeInTheDocument()
    expect(screen.getByText('Fire Safety SOP')).toBeInTheDocument()
    expect(screen.queryByText('Policy #99')).not.toBeInTheDocument()
    expect(screen.getByText('Policy #77')).toBeInTheDocument()
    expect(screen.getByTestId('portal-work-reading-count')).toHaveTextContent('2')
  })
})
