import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { RecentCasesPanel, type RecentCaseRow, type RecentCasesData } from '../RecentCasesPanel'

function ok(rows: RecentCaseRow[]) {
  return { status: 'ok' as const, value: rows }
}

const INCIDENT_ROWS: RecentCaseRow[] = [
  {
    id: 57,
    reference: 'INC-2026-0057',
    title: 'Slip in yard',
    severity: 'high',
    status: 'under_investigation',
    // Reported the day after it happened.
    date: '2026-07-24T12:00:00Z',
  },
  {
    id: 22,
    reference: 'inc-2026-0022',
    title: 'Historic backdated incident',
    severity: 'low',
    status: 'closed',
    // Reported in 2026; the incident itself occurred in October 2024.
    date: '2026-07-23T12:00:00Z',
  },
]

function makeData(): RecentCasesData {
  return {
    incidents: ok(INCIDENT_ROWS),
    nearMisses: ok([
      {
        id: 3,
        reference: 'NM-2026-0003',
        title: 'Dropped tool',
        severity: 'medium',
        status: 'open',
        date: '2026-07-20T12:00:00Z',
      },
    ]),
    complaints: ok([
      {
        id: 4,
        reference: 'CMP-2026-0004',
        title: 'Late attendance',
        severity: 'low',
        status: 'open',
        date: '2026-07-19T12:00:00Z',
      },
    ]),
    rtas: ok([
      {
        id: 5,
        reference: 'RTA-2026-0005',
        title: 'Kerb strike',
        severity: 'low',
        status: 'open',
        date: '2026-07-18T12:00:00Z',
      },
    ]),
  }
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <RecentCasesPanel data={makeData()} />
    </MemoryRouter>,
  )
}

describe('RecentCasesPanel date column (PX-122)', () => {
  /**
   * The dashboard binds a different date per tab (incidents -> reported_date,
   * near misses -> event_date, and so on) while /incidents shows incident_date.
   * Heading every one of them "Date" made the two surfaces look like they
   * disagreed about the same incident.
   */
  it('names the field each tab actually shows instead of a bare "Date"', () => {
    renderPanel()

    expect(screen.getByTestId('recent-cases-date-header')).toHaveTextContent('Reported')

    fireEvent.click(screen.getByTestId('recent-cases-tab-near_misses'))
    expect(screen.getByTestId('recent-cases-date-header')).toHaveTextContent('Occurred')

    fireEvent.click(screen.getByTestId('recent-cases-tab-complaints'))
    expect(screen.getByTestId('recent-cases-date-header')).toHaveTextContent('Received')

    fireEvent.click(screen.getByTestId('recent-cases-tab-rtas'))
    expect(screen.getByTestId('recent-cases-date-header')).toHaveTextContent('Logged')
  })

  it('never labels the column with an unqualified "Date"', () => {
    renderPanel()

    const header = screen.getByTestId('recent-cases-date-header')
    expect(header.textContent?.trim()).not.toBe('Date')
  })

  it('renders dates in UK order regardless of the browser locale', () => {
    renderPanel()

    const panel = screen.getByTestId('recent-cases-panel')
    expect(within(panel).getByText('24/07/2026')).toBeInTheDocument()
    expect(within(panel).getByText('23/07/2026')).toBeInTheDocument()
    // en-US ordering must not leak through from the host machine.
    expect(within(panel).queryByText('7/24/2026')).toBeNull()
  })

  it('renders reference codes in one canonical format', () => {
    renderPanel()

    const panel = screen.getByTestId('recent-cases-panel')
    expect(within(panel).getByText('INC-2026-0057')).toBeInTheDocument()
    // Supplied lowercase by the API fixture; must still read as a reference code.
    expect(within(panel).getByText('INC-2026-0022')).toBeInTheDocument()
    expect(within(panel).queryByText('inc-2026-0022')).toBeNull()
  })
})
