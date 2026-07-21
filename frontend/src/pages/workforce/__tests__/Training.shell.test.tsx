import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : _key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../api/client', () => ({
  trainingMatrixApi: {
    listCompliance: vi.fn().mockResolvedValue({ items: [], total: 0, atlas_hub_url: 'https://atlas' }),
    getSummary: vi.fn().mockResolvedValue(null),
    myTraining: vi.fn().mockResolvedValue({ items: [], total: 0, atlas_hub_url: 'https://atlas' }),
    listNameMaps: vi.fn().mockResolvedValue([]),
    listRequirements: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listCourses: vi.fn().mockResolvedValue([]),
    uploadImport: vi.fn(),
    getLatestImport: vi.fn().mockRejectedValue(new Error('No training matrix import found')),
    upsertNameMap: vi.fn(),
    autoMatchNameMaps: vi.fn().mockResolvedValue({
      people_considered: 0,
      already_mapped: 0,
      from_saved_maps: 0,
      from_auto_match: 0,
      still_unmatched: 0,
    }),
    seedRequirements: vi.fn(),
    upsertRequirementsMatrix: vi.fn(),
    notify: vi.fn(),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({ data: { items: [] } }),
    listInductions: vi.fn().mockResolvedValue({ data: { items: [] } }),
    listAssetTypes: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  auditsApi: {
    listTemplates: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  getApiErrorMessage: (e: unknown) => (e instanceof Error ? e.message : 'error'),
  ATLAS_HUB_URL: 'https://www.atlas-hub.co.uk/o/98b88f4e-2c3f-44c1-a812-36ea66222c7d/',
}))

import { trainingMatrixApi } from '../../../api/client'
import Training from '../Training'

describe('Training shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders compliance tabs and switches to Admin', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('training-shell')).toBeInTheDocument()
    expect(screen.getByTestId('training-matrix-gap-board')).toBeInTheDocument()

    await user.click(screen.getByTestId('training-tab-admin'))
    expect(await screen.findByTestId('training-matrix-admin')).toBeInTheDocument()
  })

  it('keeps latest import provenance when compliance loading fails', async () => {
    vi.mocked(trainingMatrixApi.listCompliance).mockRejectedValueOnce(new Error('Compliance unavailable'))
    vi.mocked(trainingMatrixApi.getLatestImport).mockResolvedValueOnce({
      id: 7,
      filename: 'matrix.csv',
      status: 'complete',
      person_count: 10,
      course_count: 4,
      cell_count: 40,
      nonempty_cell_count: 36,
      expiry_without_passed_count: 0,
      created_at: '2026-07-21T11:00:00Z',
    })

    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-matrix-last-upload')).toHaveTextContent('matrix.csv')
  })
})
