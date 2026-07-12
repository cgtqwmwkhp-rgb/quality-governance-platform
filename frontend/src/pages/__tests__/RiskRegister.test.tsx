import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RiskRegister from '../RiskRegister'

const { mockRiskList, mockAuditRuns, mockAuditFindings } = vi.hoisted(() => ({
  mockRiskList: vi.fn(),
  mockAuditRuns: vi.fn(),
  mockAuditFindings: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  riskRegisterApi: {
    list: mockRiskList,
    getSummary: vi.fn().mockResolvedValue({ data: {} }),
    getHeatmap: vi.fn().mockResolvedValue({ data: { cells: [] } }),
    resolveSuggestionTriage: vi.fn(),
  },
  auditsApi: {
    listRuns: mockAuditRuns,
    listFindings: mockAuditFindings,
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('RiskRegister bow-tie gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    delete window.__FEATURE_FLAGS__
    mockRiskList.mockResolvedValue({ data: { items: [], total: 0 } })
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
              inherent_score: 12,
              residual_score: 8,
              category: 'compliance',
            },
          ],
          total: 1,
        },
      })
      .mockResolvedValueOnce({ data: { items: [], total: 0 } })
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
})
