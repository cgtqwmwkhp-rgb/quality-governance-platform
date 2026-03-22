import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockGetPendingApprovals = vi.fn()
const mockListInstances = vi.fn()
const mockListTemplates = vi.fn()
const mockGetStats = vi.fn()
const mockGetDelegations = vi.fn()
const mockApproveRequest = vi.fn()
const mockUsersList = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  workflowsApi: {
    getPendingApprovals: (...args: unknown[]) => mockGetPendingApprovals(...args),
    listInstances: (...args: unknown[]) => mockListInstances(...args),
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
    getStats: (...args: unknown[]) => mockGetStats(...args),
    getDelegations: (...args: unknown[]) => mockGetDelegations(...args),
    approveRequest: (...args: unknown[]) => mockApproveRequest(...args),
    bulkApprove: vi.fn(),
    rejectRequest: vi.fn(),
    setDelegation: vi.fn(),
    cancelDelegation: vi.fn(),
  },
  usersApi: {
    list: (...args: unknown[]) => mockUsersList(...args),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('WorkflowCenter', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockGetPendingApprovals.mockResolvedValue({
      data: {
        approvals: [
          {
            id: 'APR-1',
            workflow_id: 'WF-1',
            workflow_name: 'Document Approval',
            step_name: 'Quality Review',
            entity_type: 'document',
            entity_id: 'DOC-1',
            entity_title: 'Safety Policy',
            requested_at: '2026-03-10T08:00:00Z',
            due_at: '2026-03-11T08:00:00Z',
            priority: 'high',
            sla_status: 'warning',
          },
        ],
        total: 1,
      },
    })
    mockListInstances.mockResolvedValue({
      data: {
        instances: [
          {
            id: 'WF-1',
            template_code: 'DOCUMENT_APPROVAL',
            template_name: 'Document Approval',
            entity_type: 'document',
            entity_id: 'DOC-1',
            status: 'in_progress',
            priority: 'high',
            current_step: 1,
            current_step_name: 'Quality Review',
            total_steps: 3,
            started_at: '2026-03-10T08:00:00Z',
            sla_due_at: '2099-03-11T08:00:00Z',
            sla_breached: false,
          },
        ],
        total: 1,
      },
    })
    mockListTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            code: 'DOCUMENT_APPROVAL',
            name: 'Document Approval',
            description: 'Review and approve documents',
            category: 'documents',
            trigger_entity_type: 'document',
            steps_count: 3,
          },
        ],
      },
    })
    mockGetStats.mockResolvedValue({
      data: {
        pending_approvals: 1,
        active_workflows: 1,
        overdue: 0,
        completed_today: 2,
      },
    })
    mockGetDelegations.mockResolvedValue({
      data: {
        delegations: [
          {
            id: 'DEL-1',
            delegate_id: 7,
            delegate_name: 'Jane Smith',
            start_date: '2026-03-15T00:00:00Z',
            end_date: '2026-03-20T23:59:59Z',
            reason: 'Annual leave',
            status: 'scheduled',
          },
        ],
      },
    })
    mockUsersList.mockResolvedValue({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
      },
    })
    mockApproveRequest.mockResolvedValue({ data: { status: 'approved' } })
  })

  it('renders workflow data from live API clients and approves an item', async () => {
    const WorkflowCenter = (await import('../WorkflowCenter')).default

    render(<WorkflowCenter />)

    expect(await screen.findByText('Safety Policy')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() => {
      expect(mockApproveRequest).toHaveBeenCalledWith('APR-1')
    })

    const workflowTab = screen
      .getAllByRole('button')
      .find((button) => button.textContent?.includes('workflows.active_workflows'))
    expect(workflowTab).toBeTruthy()
    fireEvent.click(workflowTab!)
    expect(await screen.findByText(/Current Step: Quality Review/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Delegation' }))
    expect(await screen.findByText('Jane Smith')).toBeInTheDocument()
  })
})
