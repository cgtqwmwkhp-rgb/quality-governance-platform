import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

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

function renderPanel(data: RecentCasesData = makeData()) {
  return render(
    <MemoryRouter>
      <RecentCasesPanel data={data} />
    </MemoryRouter>,
  )
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-probe">{location.pathname}</div>
}

/** Panel plus a probe, so a row activation can be read as a real route change. */
function renderPanelWithLocation(data: RecentCasesData = makeData()) {
  return render(
    <MemoryRouter>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <RecentCasesPanel data={data} />
              <LocationProbe />
            </>
          }
        />
      </Routes>
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

/**
 * The reference cell was painted `text-primary` but was plain text, so the one
 * thing on the dashboard that looked like a route into a case was not one.
 */
describe('RecentCasesPanel case links (FR-DASH-RECENT-01)', () => {
  it('links each reference to its own case detail route, not the register', () => {
    renderPanel()

    const link = screen.getByRole('link', { name: 'INC-2026-0057' })
    expect(link).toHaveAttribute('href', '/incidents/57')
  })

  it.each([
    ['near_misses', 'NM-2026-0003', '/near-misses/3'],
    ['complaints', 'CMP-2026-0004', '/complaints/4'],
    ['rtas', 'RTA-2026-0005', '/rtas/5'],
  ])('uses the %s detail route for its own rows', (tab, reference, href) => {
    renderPanel()

    fireEvent.click(screen.getByTestId(`recent-cases-tab-${tab}`))

    expect(screen.getByRole('link', { name: reference })).toHaveAttribute('href', href)
  })

  it('keeps View All pointing at the register for the active tab', () => {
    renderPanel()

    expect(screen.getByTestId('recent-cases-view-all')).toHaveAttribute('href', '/incidents')

    fireEvent.click(screen.getByTestId('recent-cases-tab-rtas'))
    expect(screen.getByTestId('recent-cases-view-all')).toHaveAttribute('href', '/rtas')
  })

  it('opens the case when the row is clicked away from the reference cell', () => {
    renderPanelWithLocation()

    fireEvent.click(screen.getByText('Slip in yard'))

    expect(screen.getByTestId('location-probe')).toHaveTextContent('/incidents/57')
  })

  it.each(['Enter', ' '])('opens the focused row on %s', (key) => {
    renderPanelWithLocation()

    const row = screen.getByLabelText('View incident: INC-2026-0057')
    expect(row).toHaveAttribute('tabindex', '0')

    row.focus()
    fireEvent.keyDown(row, { key })

    expect(screen.getByTestId('location-probe')).toHaveTextContent('/incidents/57')
  })

  it('names the row by the kind of case it opens', () => {
    renderPanel()

    fireEvent.click(screen.getByTestId('recent-cases-tab-near_misses'))

    expect(screen.getByLabelText('View near miss: NM-2026-0003')).toBeInTheDocument()
  })

  it('does not navigate when a key is pressed inside a cell rather than on the row', () => {
    renderPanelWithLocation()

    fireEvent.keyDown(screen.getByText('Slip in yard'), { key: 'Enter' })

    expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
    expect(screen.getByTestId('location-probe')).not.toHaveTextContent('/incidents/57')
  })

  it('leaves a row inert when the feed gave it no usable id', () => {
    const data = makeData()
    data.incidents = ok([
      {
        id: 0,
        reference: 'INC-2026-0099',
        title: 'Row with no id',
        severity: 'low',
        status: 'open',
        date: '2026-07-25T12:00:00Z',
      },
    ])

    renderPanelWithLocation(data)

    // A guessed /incidents/0 would render as a case that cannot load.
    expect(screen.queryByRole('link', { name: 'INC-2026-0099' })).toBeNull()
    expect(screen.getByText('INC-2026-0099')).toBeInTheDocument()

    const row = screen.getByTestId('recent-cases-row')
    expect(row).not.toHaveAttribute('tabindex')

    fireEvent.click(screen.getByText('Row with no id'))
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
    expect(screen.getByTestId('location-probe')).not.toHaveTextContent('/incidents/0')
  })
})
