import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ScheduleOpsStrip } from '../ScheduleOpsStrip'

const mockListRequirements = vi.fn()

vi.mock('../../../api/client', () => ({
  complianceScheduleApi: {
    listRequirements: (...args: unknown[]) => mockListRequirements(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'failed'),
}))

describe('ScheduleOpsStrip', () => {
  beforeEach(() => {
    mockListRequirements.mockReset()
  })

  it('renders owner, days-to-due, and notify band for the soonest matching obligation', async () => {
    mockListRequirements.mockResolvedValue({
      data: {
        items: [
          {
            reference_number: 'CSR-2026-0001',
            title: 'Legal register (ISO 9001 6.1.3)',
            regulatory_basis: 'ISO 9001',
            owner_name: 'Alex Owner',
            next_due_date: '2026-09-01',
            status: 'current',
          },
        ],
      },
    })

    render(<ScheduleOpsStrip clauseNumber="6.1.3" />)

    expect(await screen.findByTestId('workspace-schedule-ops')).toBeInTheDocument()
    expect(screen.getByTestId('workspace-schedule-ops-ref')).toHaveTextContent('CSR-2026-0001')
    expect(screen.getByTestId('workspace-schedule-ops-owner')).toHaveTextContent('Alex Owner')
    expect(screen.getByTestId('workspace-schedule-ops-notify')).toHaveAttribute('data-band')
  })

  it('does not invent an obligation when the register has no clause match', async () => {
    mockListRequirements.mockResolvedValue({
      data: {
        items: [
          {
            reference_number: 'CSR-2026-0099',
            title: 'Fire risk assessment',
            regulatory_basis: 'RRFSO',
            owner_name: 'Fire Owner',
            next_due_date: '2026-08-14',
            status: 'due_soon',
          },
        ],
      },
    })

    render(<ScheduleOpsStrip clauseNumber="6.1.3" />)

    expect(await screen.findByTestId('workspace-schedule-ops-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('workspace-schedule-ops')).not.toBeInTheDocument()
  })

  it('surfaces a load failure without crashing the workspace', async () => {
    mockListRequirements.mockRejectedValue(new Error('network'))

    render(<ScheduleOpsStrip clauseNumber="6.1.3" />)

    await waitFor(() => {
      expect(screen.getByTestId('workspace-schedule-ops-error')).toBeInTheDocument()
    })
  })
})
