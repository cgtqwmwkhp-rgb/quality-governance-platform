import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { CampaignComplianceRow } from '../../api/documentCampaignClient'
import { CampaignRing } from '../CampaignRing'

function complianceRow(overrides: Partial<CampaignComplianceRow> = {}): CampaignComplianceRow {
  return {
    campaign_id: 9,
    document_id: 11,
    document_title: 'Safety Policy',
    status: 'active',
    assigned: 10,
    completed: 7,
    pending: 2,
    overdue: 1,
    completion_rate: 70,
    reminder_offsets_hours: [24],
    launched_at: '2026-07-01T00:00:00Z',
    due_within_days: 14,
    ...overrides,
  }
}

describe('CampaignRing', () => {
  it('renders an accessible progressbar linking to campaign results and stops row click propagation', () => {
    const onRowClick = vi.fn()
    render(
      <MemoryRouter>
        {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- test stand-in for a real row's onClick */}
        <div onClick={onRowClick}>
          <CampaignRing documentId={11} row={complianceRow()} />
        </div>
      </MemoryRouter>,
    )

    const ring = screen.getByTestId('document-campaign-ring-11')
    expect(ring).toHaveAttribute('href', '/documents/11?tab=campaign-results&campaignId=9')

    const progressbar = screen.getByRole('progressbar')
    expect(progressbar).toHaveAttribute('aria-valuenow', '70')
    expect(progressbar).toHaveAttribute('aria-label', expect.stringContaining('70%'))
    expect(progressbar).toHaveAttribute('aria-label', expect.stringContaining('1 overdue'))

    fireEvent.click(ring)
    expect(onRowClick).not.toHaveBeenCalled()
  })

  it('omits the overdue clause from the label when nothing is overdue', () => {
    render(
      <MemoryRouter>
        <CampaignRing documentId={12} row={complianceRow({ overdue: 0, completion_rate: 100 })} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-label', 'Campaign 100% complete')
  })
})
