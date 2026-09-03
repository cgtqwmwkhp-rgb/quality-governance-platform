import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompetenceBoardResponse } from '../../../api/competenceBoardClient'

const getBoard = vi.fn()
const getEngineerMatrix = vi.fn()
const startAssessment = vi.fn()
const toastError = vi.fn()

vi.mock('../../../api/client', () => ({
  competenceBoardApi: {
    getBoard: (family: string) => getBoard(family),
  },
  // CB-UI-3. The only writer this page has, and it writes a QGP assessment run.
  competenceStartApi: {
    start: (payload: unknown) => startAssessment(payload),
  },
  competenceAssessmentExecutePath: (runId: string) => `/workforce/assessments/${runId}/execute`,
  workforceApi: {
    analytics: { getEngineerMatrix },
  },
  // A stub, not the real precedence. It reads whichever of the two shapes the
  // error carries so the fixtures below can use the ones the server really
  // sends. What it deliberately does NOT prove is that a coded 403 survives the
  // response interceptor's generic "You don't have permission" rewrite — that
  // rule lives in `forbiddenMessageFor` and is tested against the real function
  // in `api/__tests__/forbiddenMessage.test.ts`. The assertions here are about
  // this page's wiring: that a refusal is surfaced and nothing is navigated to.
  getApiErrorMessage: (error: unknown, fallback?: string) => {
    const data = (
      error as { response?: { data?: { detail?: string; error?: { message?: string } } } }
    )?.response?.data
    return data?.error?.message ?? data?.detail ?? fallback ?? 'API failed'
  },
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: {
    error: (message: string) => toastError(message),
    success: vi.fn(),
  },
}))

function httpError(status: number, detail?: string) {
  return { response: { status, data: detail ? { detail } : {} } }
}

/** The unified envelope the assessor gate actually returns on a 403. */
function gateRefusal(message: string) {
  return {
    response: { status: 403, data: { error: { code: 'ASSESSOR_NOT_ELIGIBLE', message } } },
  }
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

/**
 * The same board once CB-UI-2 has bound a template (CB-UI-3).
 *
 * `COUNTERBALANCE_FLT` carries both modes, `MEWP_3A` carries none, and the
 * viewer is Sam (`engineers.id` 22) who PAMS has issued the counterbalance to.
 * Alex on the row is a different person, so this is the one startable square on
 * the board and every other cell has to say why it is not.
 */
const BOUND_BOARD: CompetenceBoardResponse = {
  ...PAMS_BOARD,
  columns: [
    { key: 'COUNTERBALANCE_FLT', label: 'COUNTERBALANCE_FLT', bound_modes: ['field', 'induction'] },
    { key: 'MEWP_3A', label: 'MEWP_3A', bound_modes: [] },
  ],
  assessor: {
    engineer_id: 22,
    issued_characteristic_keys: ['COUNTERBALANCE_FLT'],
    blocked_reason: null,
  },
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
          <Route
            path="/workforce/assessments/:runId/execute"
            element={<div data-testid="assessment-execution-shell">Assessment execution</div>}
          />
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
    startAssessment.mockReset()
    toastError.mockReset()
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

/**
 * Every cell that offers a start, by `person-characteristic`.
 *
 * Asserted as a set rather than by querying one test id and expecting nothing:
 * `queryByTestId(...)).not.toBeInTheDocument()` passes just as happily when the
 * id is misspelled, which would make every refusal test below vacuous.
 */
function startableCells(): string[] {
  return Array.from(document.querySelectorAll('[data-start-cell]'))
    .map((node) => node.getAttribute('data-start-cell') ?? '')
    .sort()
}

describe('CompetenceBoard start-from-cell (CB-UI-3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getBoard.mockReset()
    startAssessment.mockReset()
    toastError.mockReset()
  })

  it('starts a field assessment from a bound cell and lands in the execution shell', async () => {
    const user = userEvent.setup()
    getBoard.mockResolvedValue({ data: BOUND_BOARD })
    startAssessment.mockResolvedValue({ data: { run_id: 'run-abc', reference_number: 'ASM-1' } })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    await user.click(screen.getByTestId('competence-start-eng-10-COUNTERBALANCE_FLT'))
    await user.click(screen.getByTestId('competence-start-submit'))

    await waitFor(() => {
      expect(startAssessment).toHaveBeenCalledWith({
        engineer_id: 10,
        characteristic_key: 'COUNTERBALANCE_FLT',
        mode: 'field',
        // An untouched evidence form sends nothing rather than four empty strings.
        plant_evidence: null,
      })
    })
    // A created run nobody is looking at would be worse than no run at all.
    expect(await screen.findByTestId('assessment-execution-shell')).toBeInTheDocument()
  })

  it('carries the induction mode and the plant evidence the assessor typed', async () => {
    const user = userEvent.setup()
    getBoard.mockResolvedValue({ data: BOUND_BOARD })
    startAssessment.mockResolvedValue({ data: { run_id: 'run-xyz', reference_number: 'ASM-2' } })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')
    await user.click(screen.getByTestId('competence-start-eng-10-COUNTERBALANCE_FLT'))

    await user.selectOptions(screen.getByLabelText('Mode'), 'induction')
    await user.type(screen.getByLabelText('Make'), '  Hyster  ')
    await user.type(screen.getByLabelText('Serial number'), 'H2-9981')
    await user.click(screen.getByTestId('competence-start-submit'))

    await waitFor(() => {
      expect(startAssessment).toHaveBeenCalledWith({
        engineer_id: 10,
        characteristic_key: 'COUNTERBALANCE_FLT',
        mode: 'induction',
        // Trimmed, and the boxes left alone stay absent.
        plant_evidence: { make: 'Hyster', serial: 'H2-9981' },
      })
    })
  })

  it('offers no start on an unbound characteristic and says a template is missing, not a person', async () => {
    getBoard.mockResolvedValue({ data: BOUND_BOARD })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    // Alex's bound cell is the only start on the board; nothing on MEWP_3A.
    expect(startableCells()).toEqual(['eng-10-COUNTERBALANCE_FLT'])
    const header = screen.getByTestId('competence-column-pams-MEWP_3A')
    expect(header).toHaveTextContent('No family template yet')
    expect(header).not.toHaveTextContent(/fail/i)

    // The column is still listed and its squares keep their PAMS colour.
    const cell = screen.getByTestId('competence-cell-pams-eng-10-MEWP_3A')
    expect(cell).toHaveAttribute('data-cell-state', 'issued')
    expect(cell.className).not.toMatch(/bg-destructive/)
    expect(cell.className).not.toMatch(/opacity-/)
  })

  it('offers no start on the assessor\u2019s own row', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...BOUND_BOARD,
        // Sam is now looking at a board that includes Sam.
        assessor: {
          engineer_id: 10,
          issued_characteristic_keys: ['COUNTERBALANCE_FLT'],
          blocked_reason: null,
        },
      },
    })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    expect(startableCells()).toEqual([])
  })

  it('says on the square why the assessor\u2019s own row cannot be started', async () => {
    // A square that is a button on every other row and inert on yours, with
    // nothing said about why, is indistinguishable from a broken board. The
    // reason is viewer-specific, so no surrounding copy carries it.
    getBoard.mockResolvedValue({
      data: {
        ...BOUND_BOARD,
        assessor: {
          engineer_id: 10,
          issued_characteristic_keys: ['COUNTERBALANCE_FLT'],
          blocked_reason: null,
        },
      },
    })

    await renderBoard()
    const table = await screen.findByTestId('competence-board-table-pams')

    expect(table).toHaveTextContent('You cannot assess yourself')
    // Said as an explanation of the square, not as a finding against Alex.
    expect(table).not.toHaveTextContent(/Alex Reid — .*failed/i)
  })

  it('does not repeat the unbound reason on every square in the column', async () => {
    // The header says it once. Twenty rows repeating it would bury the PAMS
    // state each square exists to convey.
    getBoard.mockResolvedValue({ data: BOUND_BOARD })

    await renderBoard()
    const table = await screen.findByTestId('competence-board-table-pams')

    expect(screen.getByTestId('competence-column-pams-MEWP_3A')).toHaveTextContent(
      'No family template yet',
    )
    expect(table.textContent ?? '').not.toMatch(/No family assessment template is mapped/)
  })

  it('offers no start where PAMS has not issued the characteristic to the viewer', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...BOUND_BOARD,
        assessor: { engineer_id: 22, issued_characteristic_keys: ['MEWP_3A'], blocked_reason: null },
      },
    })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    // Bound, someone else's row, and still not startable — issuance decides.
    // MEWP_3A being the issued one buys nothing either: it has no bind.
    expect(startableCells()).toEqual([])
  })

  it('fails closed when the server sends no assessor block at all', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...BOUND_BOARD,
        assessor: null,
      },
    })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    expect(startableCells()).toEqual([])
  })

  it('states the server\u2019s blocking reason once instead of leaving the board mute', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...BOUND_BOARD,
        assessor: {
          engineer_id: null,
          issued_characteristic_keys: [],
          blocked_reason: 'Your user account has no QGP employee record, so you cannot assess.',
        },
      },
    })

    await renderBoard()

    expect(await screen.findByTestId('competence-assessor-blocked')).toHaveTextContent(
      'no QGP employee record',
    )
    expect(startableCells()).toEqual([])
  })

  it('offers no start on an unlinked PAMS row, because a demonstration needs an employee record', async () => {
    getBoard.mockResolvedValue({
      data: {
        ...BOUND_BOARD,
        // The unmapped technician now has the bound characteristic issued.
        people: BOUND_BOARD.people.map((person) =>
          person.mapped
            ? person
            : { ...person, cells: { ...person.cells, COUNTERBALANCE_FLT: { issued: true } } },
        ),
      },
    })

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')

    // Alex's cell is startable; the unlinked technician's identical cell is not.
    expect(startableCells()).toEqual(['eng-10-COUNTERBALANCE_FLT'])
    // The row is still on the board — CB-UI-1 does not drop it.
    expect(screen.getByText('Technician #777')).toBeInTheDocument()
  })

  it('shows the server\u2019s refusal rather than pretending the start worked', async () => {
    const user = userEvent.setup()
    getBoard.mockResolvedValue({ data: BOUND_BOARD })
    startAssessment.mockRejectedValue(
      gateRefusal('PAMS has not issued COUNTERBALANCE_FLT to you, so you cannot assess it.'),
    )

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')
    await user.click(screen.getByTestId('competence-start-eng-10-COUNTERBALANCE_FLT'))
    await user.click(screen.getByTestId('competence-start-submit'))

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        'PAMS has not issued COUNTERBALANCE_FLT to you, so you cannot assess it.',
      )
    })
    // No navigation on a refusal, and the form stays open with what was typed.
    expect(screen.queryByTestId('assessment-execution-shell')).not.toBeInTheDocument()
    expect(screen.getByTestId('competence-start-panel')).toBeInTheDocument()
  })

  it('never offers a start on the People tab, where issuance comes from a course pass', async () => {
    const user = userEvent.setup()
    getBoard.mockImplementation((family: string) =>
      family === 'pams'
        ? Promise.resolve({ data: BOUND_BOARD })
        : Promise.resolve({
            data: {
              ...ATLAS_BOARD,
              columns: ATLAS_BOARD.columns.map((column) => ({
                ...column,
                bound_modes: ['field' as const],
              })),
              assessor: {
                engineer_id: 22,
                issued_characteristic_keys: ['FIRE_MARSHAL', 'MANUAL_HANDLING'],
                blocked_reason: null,
              },
            },
          }),
    )

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')
    await user.click(screen.getByTestId('competence-tab-people'))
    await screen.findByTestId('competence-board-table-atlas')

    expect(startableCells()).toEqual([])
    // And no "no family template yet" note either: an Atlas course is not
    // waiting on a bind, so saying so would invent a gap.
    expect(screen.queryByTestId('competence-column-unbound-FIRE_MARSHAL')).not.toBeInTheDocument()
    expect(screen.queryByTestId('competence-assessor-blocked')).not.toBeInTheDocument()
  })

  it('drops a half-filled start form when the tab changes', async () => {
    const user = userEvent.setup()
    getBoard.mockImplementation((family: string) =>
      family === 'pams' ? Promise.resolve({ data: BOUND_BOARD }) : Promise.resolve({ data: ATLAS_BOARD }),
    )

    await renderBoard()
    await screen.findByTestId('competence-board-table-pams')
    await user.click(screen.getByTestId('competence-start-eng-10-COUNTERBALANCE_FLT'))
    await user.type(screen.getByLabelText('Serial number'), 'H2-9981')

    await user.click(screen.getByTestId('competence-tab-people'))
    await user.click(screen.getByTestId('competence-tab-plant'))

    expect(screen.queryByTestId('competence-start-panel')).not.toBeInTheDocument()
    expect(startAssessment).not.toHaveBeenCalled()
  })
})
