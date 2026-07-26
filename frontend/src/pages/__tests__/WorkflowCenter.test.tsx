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

  describe('KPI honesty', () => {
    it('cannot show pending approvals while the panel says the queue is empty', async () => {
      // PX-286: the tile read a fabricated organisation-wide constant while the panel
      // listed the caller's own queue, so "12 pending" sat above "none assigned to you".
      mockGetPendingApprovals.mockResolvedValue({ data: { approvals: [], total: 0 } })
      mockGetStats.mockResolvedValue({
        data: {
          pending_approvals: 0,
          pending_approvals_scope: 'assigned_to_me',
          active_workflows: null,
          overdue: null,
          completed_today: null,
        },
      })
      const WorkflowCenter = (await import('../WorkflowCenter')).default

      render(<WorkflowCenter />)

      expect(
        await screen.findByText('No pending approvals are assigned to you right now.'),
      ).toBeInTheDocument()
      expect(screen.getByTestId('workflow-stat-pending')).toHaveTextContent('0')
    })

    it('reconciles a divergent stats payload to the loaded pending list (PX-286)', async () => {
      // Belt-and-suspenders: even if /stats still returns a stale org-wide total,
      // the tile must match the list rendered beneath it.
      mockGetPendingApprovals.mockResolvedValue({ data: { approvals: [], total: 0 } })
      mockGetStats.mockResolvedValue({
        data: {
          pending_approvals: 12,
          pending_approvals_scope: 'organisation',
          active_workflows: 23,
          overdue: 3,
          completed_today: 8,
        },
      })
      const WorkflowCenter = (await import('../WorkflowCenter')).default

      render(<WorkflowCenter />)

      expect(
        await screen.findByText('No pending approvals are assigned to you right now.'),
      ).toBeInTheDocument()
      expect(screen.getByTestId('workflow-stat-pending')).toHaveTextContent('0')
    })

    it('labels the pending tile as the caller’s own queue, not a global total', async () => {
      const WorkflowCenter = (await import('../WorkflowCenter')).default

      render(<WorkflowCenter />)

      expect(await screen.findByTestId('workflow-stat-pending')).toBeInTheDocument()
      expect(screen.getByText('workflows.pending_approvals_mine')).toBeInTheDocument()
    })

    it('withholds unmeasured stats as em dashes and explains why', async () => {
      mockGetStats.mockResolvedValue({
        data: {
          pending_approvals: 1,
          pending_approvals_scope: 'assigned_to_me',
          active_workflows: null,
          overdue: null,
          completed_today: null,
        },
      })
      const WorkflowCenter = (await import('../WorkflowCenter')).default

      render(<WorkflowCenter />)

      expect(await screen.findByTestId('workflow-stat-active')).toHaveTextContent('—')
      expect(screen.getByTestId('workflow-stat-overdue')).toHaveTextContent('—')
      expect(screen.getByTestId('workflow-stat-completed-today')).toHaveTextContent('—')
      expect(screen.getByTestId('workflow-stats-unmeasured')).toBeInTheDocument()
      // The measured figure is still shown; withholding is per-metric, not blanket.
      expect(screen.getByTestId('workflow-stat-pending')).toHaveTextContent('1')
    })

    it('withholds unmeasured stats when the stats call fails, but keeps list-backed pending', async () => {
      // PX-286: pending is sourced from the loaded approvals list when available.
      // Other KPIs have no list to fall back on, so they stay unmeasured (—).
      mockGetStats.mockRejectedValue(new Error('stats down'))
      const WorkflowCenter = (await import('../WorkflowCenter')).default

      render(<WorkflowCenter />)

      expect(await screen.findByTestId('workflow-stat-pending')).toHaveTextContent('1')
      expect(screen.getByTestId('workflow-stat-active')).toHaveTextContent('—')
      expect(screen.getByTestId('workflow-stats-unmeasured')).toBeInTheDocument()
    })

    it('withholds pending as an em dash when both stats and the approvals list fail', async () => {
      mockGetPendingApprovals.mockRejectedValue(new Error('approvals down'))
      mockGetStats.mockRejectedValue(new Error('stats down'))
      const WorkflowCenter = (await import('../WorkflowCenter')).default

      render(<WorkflowCenter />)

      expect(await screen.findByTestId('workflow-stat-pending')).toHaveTextContent('—')
      expect(screen.getByTestId('workflow-stat-active')).toHaveTextContent('—')
      expect(screen.getByTestId('workflow-stats-unmeasured')).toBeInTheDocument()
    })
  })
})
