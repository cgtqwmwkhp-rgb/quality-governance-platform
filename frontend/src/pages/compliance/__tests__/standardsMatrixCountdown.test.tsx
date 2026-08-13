/**
 * Standards matrix cert countdown strip (SG-D-03).
 *
 * Attribution is a backend concern (PAT must not set ISO days). The shell only
 * paints the payload: visible columns, unmatched honesty note, no invented %.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { AlignmentCatalogueResponse, AlignmentCatalogueRow } from '../../../api/standardsCellAggregateTypes'

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
import { countdownChipLabel } from '../FrameworkCountdownStrip'

const row = (overrides: Partial<AlignmentCatalogueRow> = {}): AlignmentCatalogueRow => ({
  id: 'annexsl-6.1.2',
  kind: 'standard',
  row_key: 'annexsl-6.1.2',
  clauseNumber: '6.1.2',
  title: 'Risks and opportunities',
  verdict: 'DIFFERENT',
  row_verdict: 'DIFFERENT',
  is_trap: true,
  has_unique: false,
  trap_pair_count: 10,
  pair_count: 10,
  rationale: 'Same number, five different requirements.',
  frameworks: {
    '9001': {
      clause_key: '9001-6.1.2',
      clause_number: '6.1.2',
      label: 'risks and opportunities',
      verdicts: ['DIFFERENT'],
    },
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
  ...overrides,
})

describe('countdownChipLabel', () => {
  it('treats missing and undated entries as none, not zero days', () => {
    expect(countdownChipLabel(undefined).status).toBe('none')
    expect(
      countdownChipLabel({
        status: 'none',
        next_expiry: null,
        days_remaining: null,
        name: null,
      }).status,
    ).toBe('none')
  })
})

describe('Standards matrix cert countdown (SG-D-03)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAlignmentCatalogue.mockResolvedValue({ data: catalogue() })
  })

  it('paints attributed days on 9001 and none on CHAS, and says PAT is unmatched', async () => {
    getMatrix.mockResolvedValue({
      data: {
        cells: [],
        framework_countdown: {
          due_soon_days: 30,
          unmatched_on_shelf: true,
          frameworks: {
            '9001': {
              status: 'due_soon',
              next_expiry: '2026-09-01',
              days_remaining: 19,
              name: 'ISO 9001:2015 Certificate',
            },
            '14001': {
              status: 'none',
              next_expiry: null,
              days_remaining: null,
              name: null,
            },
            '45001': {
              status: 'none',
              next_expiry: null,
              days_remaining: null,
              name: null,
            },
          },
        },
      },
    })

    render(<StandardsMatrixShell onSelectCell={() => {}} />)

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-countdown')).toBeInTheDocument()
    })
    expect(screen.getByTestId('standards-matrix-countdown-9001')).toHaveTextContent('19d')
    expect(screen.getByTestId('standards-matrix-countdown-9001')).toHaveAttribute('data-status', 'due_soon')
    expect(screen.getByTestId('standards-matrix-countdown-14001')).toHaveTextContent('No dated cert')
    expect(screen.getByTestId('standards-matrix-countdown-unmatched')).toHaveTextContent('PAT')
    expect(screen.queryByTestId('standards-matrix-countdown-chas')).not.toBeInTheDocument()
  })

  it('hides the strip when the matrix payload has no countdown', async () => {
    getMatrix.mockResolvedValue({ data: { cells: [] } })
    render(<StandardsMatrixShell onSelectCell={() => {}} />)

    await waitFor(() => {
      expect(screen.getByTestId('standards-matrix-live-badge')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('standards-matrix-countdown')).not.toBeInTheDocument()
  })
})
