import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompetenceBoardResponse } from '../../../api/competenceBoardClient'

const getBoard = vi.fn()
const getEngineerMatrix = vi.fn()

vi.mock('../../../api/client', () => ({
  competenceBoardApi: {
    getBoard: (family: string) => getBoard(family),
  },
  workforceApi: {
    analytics: { getEngineerMatrix },
  },
  getApiErrorMessage: (error: unknown, fallback?: string) => {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    return detail ?? fallback ?? 'API failed'
  },
}))

function httpError(status: number, detail?: string) {
  return { response: { status, data: detail ? { detail } : {} } }
}

const PAMS_BOARD: CompetenceBoardResponse = {
  family: 'pams',
  snapshot: {
    id: 12,
    status: 'complete',
    source_name: 'pams_competence_2026_09_01.csv',
    row_count: 340,
    completed_at: '2026-09-01T04:00:00Z',
    stale: false,
    stale_reason: null,
  },
  columns: [
    { key: 'COUNTERBALANCE_FLT', label: 'COUNTERBALANCE_FLT' },
    { key: 'MEWP_3A', label: 'MEWP_3A' },
  ],
  people: [
    {
      engineer_id: 10,
      pams_technician_id: 501,
      display_name: 'Alex Technician',
      depot: 'Bedford',
      mapped: true,
      cells: {
        COUNTERBALANCE_FLT: { issued: true, demonstrated: 'pass', assessed_at: '2026-07-02T09:00:00Z' },
        MEWP_3A: { issued: true, thorough_exam: true },
      },
    },
    {
      engineer_id: null,
      pams_technician_id: 777,
      display_name: 'Technician #777',
      depot: 'Rugby',
      mapped: false,
      cells: {
        MEWP_3A: { issued: true },
      },
    },
  ],
  unmapped_count: 1,
  banner: null,
}

const ATLAS_BOARD: CompetenceBoardResponse = {
  family: 'atlas',
  snapshot: {
    id: 4,
    status: 'complete',
    source_name: 'atlas_matrix.xlsx',
    row_count: 85,
    completed_at: '2026-08-28T10:00:00Z',
    stale: false,
    stale_reason: null,
  },
  columns: [
    { key: 'FIRE_MARSHAL', label: 'Fire Marshal' },
    { key: 'MANUAL_HANDLING', label: 'Manual Handling' },
  ],
  people: [
    {
      engineer_id: 10,
      atlas_person_id: 1,
      display_name: 'Alex Technician',
      department: 'Mobile Engineers',
      mapped: true,
      cells: {
        FIRE_MARSHAL: { issued: true, passed_on: '2026-02-01', expires_on: '2029-02-01' },
      },
    },
    {
      engineer_id: null,
      atlas_person_id: 2,
      display_name: 'Priya Office',
      department: 'Office',
      mapped: false,
      cells: {
        MANUAL_HANDLING: { issued: true, passed_on: '2021-05-05', expires_on: '2024-05-05' },
      },
    },
    {
      engineer_id: null,
      atlas_person_id: 3,
      display_name: 'Dana Director',
      department: 'Management',
      mapped: false,
      cells: {},
    },
  ],
  unmapped_count: 2,
  banner: null,
}

async function renderBoard(initialPath = '/workforce/dashboard') {
  const CompetenceBoard = (await import('../CompetenceBoard')).default
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/workforce/dashboard" element={<CompetenceBoard />} />
          <Route path="/workforce/dashboard/analytics" element={<div>Legacy analytics</div>} />
          <Route path="/workforce/engineers/:id" element={<div>Engineer profile</div>} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

describe('CompetenceBoard (CB-UI-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getBoard.mockReset()
    getEngineerMatrix.mockReset()
  })

  it('renders PAMS characteristics on the Plant tab and never asks WDP for the workshop matrix', async () => {
    getBoard.mockImplementation((family: string) =>
      family === 'pams' ? Promise.resolve({ data: PAMS_BOARD }) : Promise.resolve({ data: ATLAS_BOARD }),
    )

    await renderBoard()

    expect(await screen.findByTestId('competence-board-table-pams')).toBeInTheDocument()
    expect(screen.getByTestId('competence-column-pams-COUNTERBALANCE_FLT')).toHaveTextContent(
      'COUNTERBALANCE_FLT',
    )
    expect(screen.getByTestId('competence-column-pams-MEWP_3A')).toBeInTheDocument()
    expect(screen.getByText('Alex Technician')).toBeInTheDocument()

    // The workshop asset-type matrix is gone from this page, not merely hidden.
    expect(getEngineerMatrix).not.toHaveBeenCalled()
    expect(getBoard).toHaveBeenCalledWith('pams')
    // Atlas is not fetched until its tab is opened.
    expect(getBoard).not.toHaveBeenCalledWith('atlas')
  })

  it('does not paint an issued-but-unassessed plant cell as a fail or a grey block', async () => {
    getBoard.mockResolvedValue({ data: PAMS_BOARD })

    await renderBoard()

    const notAssessed = await screen.findByTestId('competence-cell-pams-eng-10-MEWP_3A')
    expect(notAssessed).toHaveAttribute('data-cell-state', 'issued')
    expect(notAssessed.className).not.toMatch(/bg-destructive/)
    expect(notAssessed.className).not.toMatch(/bg-muted-foreground/)

    // A characteristic PAMS holds no row for is absent, not failed.
    const noRecord = screen.getByTestId('competence-cell-pams-pams-777-COUNTERBALANCE_FLT')
    expect(noRecord).toHaveAttribute('data-cell-state', 'no_record')
    expect(noRecord.className).not.toMatch(/bg-destructive/)
    expect(noRecord.className).not.toMatch(/bg-muted-foreground/)

    // And the demonstrated cell is still allowed to say so.
    expect(screen.getByTestId('competence-cell-pams-eng-10-COUNTERBALANCE_FLT')).toHaveAttribute(
      'data-cell-state',
      'demonstrated_pass',
    )
  })

  it('shows unmapped plant rows instead of dropping them', async () => {
    getBoard.mockResolvedValue({ data: PAMS_BOARD })

    await renderBoard()

    expect(await screen.findByText('Technician #777')).toBeInTheDocument()
    expect(screen.getByTestId('competence-unmapped-pams-pams-777')).toBeInTheDocument()
    expect(screen.getByTestId('competence-snapshot-pams')).toHaveTextContent(
      'pams_competence_2026_09_01.csv',
    )
  })

  it('renders Atlas rows on the People tab, including office and management with no QGP record', async () => {
    const user = userEvent.setup()
    getBoard.mockImplementation((family: string) =>
      family === 'pams' ? Promise.resolve({ data: PAMS_BOARD }) : Promise.resolve({ data: ATLAS_BOARD }),
    )

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    await user.click(screen.getByTestId('competence-tab-people'))

    expect(await screen.findByTestId('competence-board-table-atlas')).toBeInTheDocument()
    expect(screen.getByTestId('competence-column-atlas-FIRE_MARSHAL')).toHaveTextContent(
      'Fire Marshal',
    )
    expect(screen.getByText('Priya Office')).toBeInTheDocument()
    expect(screen.getByText('Dana Director')).toBeInTheDocument()
    expect(screen.getByTestId('competence-unmapped-atlas-atlas-2')).toBeInTheDocument()
    expect(screen.getByTestId('competence-unmapped-atlas-atlas-3')).toBeInTheDocument()
    // A person with no cells at all still gets a row of honest no-record squares.
    expect(screen.getByTestId('competence-cell-atlas-atlas-3-FIRE_MARSHAL')).toHaveAttribute(
      'data-cell-state',
      'no_record',
    )
    expect(screen.getByTestId('competence-cell-atlas-atlas-2-MANUAL_HANDLING')).toHaveAttribute(
      'data-cell-state',
      'passed_expired',
    )
    expect(getBoard).toHaveBeenCalledWith('atlas')
  })

  it('opens the People tab directly from a bookmarked ?tab=people without fetching plant', async () => {
    getBoard.mockResolvedValue({ data: ATLAS_BOARD })

    await renderBoard('/workforce/dashboard?tab=people')

    expect(await screen.findByTestId('competence-board-table-atlas')).toBeInTheDocument()
    expect(getBoard).toHaveBeenCalledWith('atlas')
    expect(getBoard).not.toHaveBeenCalledWith('pams')
  })

  it('reports a flag-off 404 as not enabled and invents no zeros', async () => {
    getBoard.mockRejectedValue(
      httpError(404, 'Competence board is not enabled in this environment.'),
    )

    await renderBoard()

    const notice = await screen.findByTestId('competence-board-unavailable-pams')
    expect(notice).toHaveTextContent('Competence board is not enabled in this environment.')
    expect(screen.queryByTestId('competence-board-table-pams')).not.toBeInTheDocument()
    expect(screen.queryByTestId('competence-snapshot-pams')).not.toBeInTheDocument()
    expect(notice).not.toHaveTextContent('0')
    // The kill-switch bookmark is offered rather than a fabricated empty board.
    expect(screen.getByText('/workforce/dashboard/analytics')).toBeInTheDocument()
  })

  it('reports an empty snapshot in the server\u2019s own words rather than as zero coverage', async () => {
    getBoard.mockResolvedValue({
      data: {
        family: 'pams',
        snapshot: { row_count: 0, stale: true, stale_reason: 'No PAMS competence snapshot yet.' },
        columns: [],
        people: [],
        unmapped_count: 0,
        banner: 'No PAMS competence snapshot yet.',
      } satisfies CompetenceBoardResponse,
    })

    await renderBoard()

    const empty = await screen.findByTestId('competence-board-empty-pams')
    expect(empty).toHaveTextContent('No PAMS competence snapshot yet.')
    expect(screen.queryByTestId('competence-board-table-pams')).not.toBeInTheDocument()
  })

  it('does not call an Atlas import with no dated cells "not imported yet"', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...ATLAS_BOARD,
        columns: [],
        people: ATLAS_BOARD.people.map((person) => ({ ...person, cells: {} })),
      },
    })

    await renderBoard('/workforce/dashboard?tab=people')

    const empty = await screen.findByTestId('competence-board-empty-atlas')
    expect(empty).toHaveTextContent('3 people are in the source')
    expect(empty).not.toHaveTextContent('has been imported yet')
  })

  it('degrades to the empty panel rather than throwing when a list is missing', async () => {
    getBoard.mockResolvedValue({ data: { family: 'pams', snapshot: { row_count: 0, stale: true } } })

    await renderBoard()

    expect(await screen.findByTestId('competence-board-empty-pams')).toBeInTheDocument()
    expect(screen.queryByTestId('competence-board-error-pams')).not.toBeInTheDocument()
  })

  it('surfaces a stale banner beside the board it belongs to', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...PAMS_BOARD,
        snapshot: { ...PAMS_BOARD.snapshot, stale: true, stale_reason: 'Snapshot is 9 days old.' },
        banner: 'Snapshot is 9 days old.',
      },
    })

    await renderBoard()

    expect(await screen.findByTestId('competence-board-banner-pams')).toHaveTextContent(
      'Snapshot is 9 days old.',
    )
    expect(screen.getByTestId('competence-board-table-pams')).toBeInTheDocument()
  })

  it('offers a retry on a real failure and clears the notice when it succeeds', async () => {
    const user = userEvent.setup()
    let shouldFail = true
    getBoard.mockImplementation(() =>
      shouldFail
        ? Promise.reject(httpError(500, 'Board query failed.'))
        : Promise.resolve({ data: PAMS_BOARD }),
    )

    await renderBoard()

    expect(await screen.findByTestId('competence-board-error-pams')).toHaveTextContent(
      'Board query failed.',
    )
    shouldFail = false
    await user.click(screen.getByTestId('competence-board-error-pams-retry'))

    await waitFor(() => {
      expect(screen.getByTestId('competence-board-table-pams')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('competence-board-error-pams')).not.toBeInTheDocument()
  })
})
