/**
 * Standards matrix alignment wire-up (Wave 2 PR-C).
 *
 * The matrix shell shipped in PR-A with a hardcoded nine-clause axis. PR-C serves
 * that axis from the imported PEL-HSEQ-5064 edition, which introduces a failure
 * mode worth testing directly: if the catalogue read is empty or fails, an
 * unguarded implementation renders an empty grid, which reads as "no clauses
 * apply" — a false claim rather than a missing one.
 *
 * So these tests hold three things:
 *   1. imported rows replace the built-in axis, and the shell says which is in use;
 *   2. an empty or failing read falls back to the built-in axis and says so;
 *   3. a DIFFERENT / UNIQUE row is visibly flagged, because an unflagged trap row
 *      is the specific way this feature would mislead somebody.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type {
  AlignmentCatalogueResponse,
  AlignmentCatalogueRow,
} from '../../../api/standardsCellAggregateTypes'

const getAlignmentCatalogue = vi.fn()
const getMatrix = vi.fn()

vi.mock('../../../api/client', () => ({
  standardsCellAggregateApi: {
    getAlignmentCatalogue: (...args: unknown[]) => getAlignmentCatalogue(...args),
    getMatrix: (...args: unknown[]) => getMatrix(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message || 'error',
}))

import { StandardsMatrixShell } from '../StandardsMatrixShell'

const row = (overrides: Partial<AlignmentCatalogueRow> = {}): AlignmentCatalogueRow => ({
  id: 'annexsl-6.1.2',
  kind: 'standard',
  row_key: 'annexsl-6.1.2',
  clauseNumber: '6.1.2',
  title: 'Risk assessment',
  verdict: 'DIFFERENT',
  row_verdict: 'DIFFERENT',
  is_trap: true,
  has_unique: false,
  pair_count: 10,
  trap_pair_count: 10,
  rationale: 'Same number, five different requirements.',
  frameworks: {
    '9001': { clause_key: '9001-6.1.2', clause_number: '6.1.2', label: 'risks and opportunities', verdicts: ['DIFFERENT'] },
    '14001': { clause_key: '14001-6.1.2', clause_number: '6.1.2', label: 'environmental aspects', verdicts: ['DIFFERENT'] },
  },
  ...overrides,
})

const catalogue = (
  overrides: Partial<AlignmentCatalogueResponse> = {},
): AlignmentCatalogueResponse => ({
  matrix_loaded: true,
  matrix_version: 'PEL-HSEQ-5064 v1.0',
  rows: [row()],
  frameworks: ['9001', '14001', '45001'],
  excluded_frameworks: ['constructionline'],
  unresolvable_frameworks: [],
  ...overrides,
})

function renderShell() {
  return render(<StandardsMatrixShell onSelectCell={() => {}} />)
}

describe('Standards matrix alignment axis (PR-C)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getMatrix.mockResolvedValue({ data: { cells: [] } })
  })

  it('replaces the built-in axis with imported clause rows and names the edition', async () => {
    getAlignmentCatalogue.mockResolvedValue({ data: catalogue() })
    renderShell()

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-axis-imported')).toBeInTheDocument()
    })
    expect(screen.getByTestId('standards-matrix-axis-imported')).toHaveTextContent(
      'PEL-HSEQ-5064 v1.0',
    )

    // The imported row is present, and a built-in-only row is not.
    expect(screen.getByText('6.1.2')).toBeInTheDocument()
    expect(screen.queryByText('10.2')).not.toBeInTheDocument()
  })

  it('flags a DIFFERENT row so a trap cannot be skimmed past', async () => {
    getAlignmentCatalogue.mockResolvedValue({ data: catalogue() })
    renderShell()

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-verdict-6.1.2')).toBeInTheDocument()
    })
    expect(screen.getByTestId('standards-matrix-verdict-6.1.2')).toHaveTextContent('DIFFERENT')
  })

  it('shows a UNIQUE row with its own verdict rather than as a gap', async () => {
    getAlignmentCatalogue.mockResolvedValue({
      data: catalogue({
        rows: [
          row({
            id: 'annexsl-5.4',
            row_key: 'annexsl-5.4',
            clauseNumber: '5.4',
            title: 'Consultation and participation of workers',
            verdict: 'UNIQUE',
            row_verdict: 'UNIQUE',
            has_unique: true,
            trap_pair_count: 0,
            pair_count: 1,
          }),
        ],
      }),
    })
    renderShell()

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-verdict-5.4')).toHaveTextContent('UNIQUE')
    })
  })

  it('falls back to the built-in axis and says so when nothing is imported', async () => {
    getAlignmentCatalogue.mockResolvedValue({
      data: catalogue({ matrix_loaded: false, matrix_version: null, rows: [] }),
    })
    renderShell()

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-axis-fallback')).toBeInTheDocument()
    })
    // The built-in axis is rendered rather than an empty grid.
    expect(screen.getByText('4.1')).toBeInTheDocument()
    expect(screen.getByTestId('standards-matrix-axis-fallback')).toHaveTextContent(
      'no matrix imported',
    )
  })

  it('falls back to the built-in axis when the catalogue read fails', async () => {
    getAlignmentCatalogue.mockRejectedValue(new Error('boom'))
    renderShell()

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-axis-fallback')).toBeInTheDocument()
    })
    expect(screen.getByText('4.1')).toBeInTheDocument()
    expect(screen.getByTestId('standards-matrix-table')).toBeInTheDocument()
  })

  it('quarantines scheme identity shells from the imported clause axis', async () => {
    getAlignmentCatalogue.mockResolvedValue({
      data: catalogue({
        rows: [
          row(),
          row({
            id: 'pm-shell',
            row_key: 'pm-shell',
            kind: 'scheme',
            clauseNumber: 'PM',
            title: 'Planet Mark scheme shell',
          }),
        ],
      }),
    })
    renderShell()

    await waitFor(() => {
      expect(screen.getByText('6.1.2')).toBeInTheDocument()
    })
    expect(screen.queryByText('Planet Mark scheme shell')).not.toBeInTheDocument()
  })
})
