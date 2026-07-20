import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockList = vi.fn()

vi.mock('../../api/client', () => ({
  auditTrailApi: {
    list: (...args: unknown[]) => mockList(...args),
  },
}))

vi.mock('../admin/adminLoadHelpers', () => ({
  AdminLoadUnavailable: ({
    testId,
    title,
    description,
  }: {
    testId?: string
    title: string
    description: string
  }) => (
    <div data-testid={testId}>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  ),
  captureAdminLoadError: (_err: unknown, _ctx: unknown, message: string) => message,
}))

import AuditTrail from '../AuditTrail'

describe('AuditTrail honesty (PX-006)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { items: [] } })
  })

  it('shows honest empty state when API returns no events', async () => {
    render(<AuditTrail />)

    await waitFor(() => {
      expect(screen.getByTestId('audit-trail-empty')).toBeInTheDocument()
    })

    expect(screen.getByText('No activity logged yet')).toBeInTheDocument()
    expect(
      screen.getByText(/not recording login, create, update, or delete activity yet/i),
    ).toBeInTheDocument()
  })

  it('disables export with honest affordance', async () => {
    render(<AuditTrail />)

    await waitFor(() => {
      expect(screen.getByTestId('audit-trail-export-disabled')).toBeDisabled()
    })
  })

  it('shows filter-empty copy when filters hide all rows', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            timestamp: '2026-01-01T12:00:00Z',
            user_name: 'Alex',
            user_email: 'alex@example.com',
            action: 'create',
            entity_type: 'incident',
            entity_id: '9',
            entity_name: 'Created incident',
          },
        ],
      },
    })

    render(<AuditTrail />)

    await waitFor(() => {
      expect(screen.getByText('Created incident')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Search audit trail'), {
      target: { value: 'does-not-match' },
    })

    expect(screen.getByText('No audit entries match your filters')).toBeInTheDocument()
  })
})
