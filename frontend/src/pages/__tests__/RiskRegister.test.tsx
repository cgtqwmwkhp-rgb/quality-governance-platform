import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RiskRegister from '../RiskRegister'
import { toast } from '../../contexts/ToastContext'

const {
  mockRiskList,
  mockGetSummary,
  mockGetHeatmap,
  mockAuditRuns,
  mockAuditFindings,
} = vi.hoisted(() => ({
  mockRiskList: vi.fn(),
  mockGetSummary: vi.fn(),
  mockGetHeatmap: vi.fn(),
  mockAuditRuns: vi.fn(),
  mockAuditFindings: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  riskRegisterApi: {
    list: mockRiskList,
    getSummary: mockGetSummary,
    getHeatmap: mockGetHeatmap,
    resolveSuggestionTriage: vi.fn(),
  },
  auditsApi: {
    listRuns: mockAuditRuns,
    listFindings: mockAuditFindings,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Something went wrong') =>
    err instanceof Error ? err.message : fallback,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('RiskRegister bow-tie gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
    mockRiskList.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetSummary.mockResolvedValue({
      data: {
        total_risks: 0,
        by_level: { critical: 0, high: 0, medium: 0, low: 0 },
        outside_appetite: 0,
        overdue_review: 0,
        escalated: 0,
      },
    })
    mockGetHeatmap.mockResolvedValue({ data: { cells: [] } })
    mockAuditRuns.mockResolvedValue({ data: { items: [] } })
    mockAuditFindings.mockResolvedValue({ data: { items: [] } })
  })

  it('hides unfinished bow-tie UI and fabricated labels by default', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Enterprise Risk Register' })

    expect(screen.queryByRole('button', { name: /bow-tie analysis/i })).not.toBeInTheDocument()
    expect(
      screen.queryByText(/equipment failure|financial loss|human error|preventive maintenance/i),
    ).not.toBeInTheDocument()
  })
})

describe('RiskRegister linked audit references', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
    mockRiskList
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 88,
              reference: 'RSK-00088',
              title: 'Inspection escalation',
              status: 'open',
              linked_audits: ['AUD-00041', 'AF-00501', 'AUD-00042', 'LEGACY-REF'],
              linked_actions: ['CAPA-00900'],
              inherent_score: 12,
              residual_score: 8,
              category: 'compliance',
            },
          ],
          total: 1,
        },
      })
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })
    mockGetSummary.mockResolvedValue({
      data: {
        total_risks: 1,
        by_level: { critical: 0, high: 1, medium: 0, low: 0 },
        outside_appetite: 0,
        overdue_review: 2,
        escalated: 0,
      },
    })
    mockGetHeatmap.mockResolvedValue({ data: { cells: [] } })
    mockAuditRuns.mockResolvedValue({
      data: {
        items: [
          { id: 41, reference_number: 'AUD-00041' },
          {
            id: 42,
            reference_number: 'AUD-00042',
            is_external_audit_import: true,
          },
        ],
      },
    })
    mockAuditFindings.mockResolvedValue({
      data: {
        items: [{ id: 501, reference_number: 'AF-00501' }],
      },
    })
  })

  it('renders resolvable finding and audit references as workspace links', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'Open finding AF-00501' })).toHaveAttribute(
      'href',
      '/audits?view=findings&findingId=501',
    )
    expect(screen.getByRole('link', { name: 'Open audit AUD-00041' })).toHaveAttribute(
      'href',
      '/audits/41/execute',
    )
    expect(screen.getByRole('link', { name: 'Open audit AUD-00042' })).toHaveAttribute(
      'href',
      '/audits/42/import-review',
    )
    expect(screen.getByText('LEGACY-REF').closest('a')).toBeNull()
  })

  it('deep-links CAPA via platform sourceType=risk pattern', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('risk-linked-action-CAPA-00900')).toHaveTextContent(
      'CAPA-00900',
    )
    expect(screen.getByRole('link', { name: 'Open CAPA for RSK-00088' })).toHaveAttribute(
      'href',
      '/actions?sourceType=risk&sourceId=88',
    )
  })

  it('reads nested by_level and overdue_review from summary API (no faux zeros)', async () => {
    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    await screen.findByText('Inspection escalation')
    expect(screen.getByTestId('risk-metric-high')).toHaveTextContent('1')
    expect(screen.getByTestId('risk-metric-overdue-review')).toHaveTextContent('2')
    expect(screen.getByTestId('risk-metric-overdue-review')).not.toHaveAttribute(
      'aria-label',
      'Overdue review unavailable',
    )
  })

  it('derives visible band counts from populated heatmap cells when a legacy summary omits them', async () => {
    mockRiskList
      .mockResolvedValueOnce({ data: { items: [], total: 125 } })
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })
    mockGetSummary.mockResolvedValue({
      data: { total_risks: 125, outside_appetite: 0, overdue_review: 0, escalated: 0 },
    })
    mockGetHeatmap.mockResolvedValue({
      data: {
        cells: [
          { likelihood: 5, impact: 5, count: 12 },
          { likelihood: 4, impact: 3, count: 20 },
          { likelihood: 3, impact: 2, count: 50 },
          { likelihood: 1, impact: 1, count: 43 },
        ],
      },
    })

    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Enterprise Risk Register' })
    expect(screen.getByTestId('risk-metric-total')).toHaveTextContent('125')
    expect(screen.getByTestId('risk-metric-critical')).toHaveTextContent('12')
    expect(screen.getByTestId('risk-metric-high')).toHaveTextContent('20')
    expect(screen.getByTestId('risk-metric-medium')).toHaveTextContent('50')
  })
})

describe('RiskRegister honesty — load and metric failures', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
    mockGetHeatmap.mockResolvedValue({ data: { cells: [] } })
    mockAuditRuns.mockResolvedValue({ data: { items: [] } })
    mockAuditFindings.mockResolvedValue({ data: { items: [] } })
  })

  it('toasts and shows unavailable empty state when list fails (not silent faux empty)', async () => {
    mockRiskList.mockRejectedValue(new Error('Risk register down'))
    mockGetSummary.mockRejectedValue(new Error('summary down'))
    mockGetHeatmap.mockRejectedValue(new Error('heatmap down'))

    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('risk-register-load-error')).toBeInTheDocument()
    expect(screen.getByTestId('risk-register-unavailable')).toHaveTextContent(
      /not an empty register/i,
    )
    expect(screen.queryByText('No risks found in the register')).not.toBeInTheDocument()
    expect(toast.error).toHaveBeenCalled()
    expect(screen.getByTestId('risk-metric-total')).toHaveTextContent('—')
    expect(screen.getByTestId('risk-metric-overdue-review')).toHaveAttribute(
      'aria-label',
      'Overdue review unavailable',
    )
  })

  it('marks summary metrics unavailable without inventing overdue_review=0', async () => {
    mockRiskList
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })
    mockGetSummary.mockRejectedValue(new Error('summary unavailable'))
    mockGetHeatmap.mockResolvedValue({ data: { cells: [] } })

    render(
      <MemoryRouter>
        <RiskRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('risk-register-partial-badge')).toBeInTheDocument()
    })
    expect(screen.getByTestId('risk-register-empty')).toHaveTextContent(
      'No risks found in the register',
    )
    expect(screen.getByTestId('risk-metric-overdue-review')).toHaveTextContent('—')
    expect(screen.getByText(/Overdue Review \(unavailable\)/i)).toBeInTheDocument()
    expect(toast.warning).toHaveBeenCalledWith(
      expect.stringMatching(/summary metrics unavailable/i),
    )
  })
})
