import { render, screen, waitFor, within } from '@testing-library/react'
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

  it('scopes status briefings to the selected training group', async () => {
    const user = userEvent.setup()
    const baseRow = {
      engineer_id: 1,
      engineer_display_name: 'Alice',
      frequency_years: 1,
      status: 'overdue',
      atlas_status: 'Expired',
      passed_on: null,
      expires_on: null,
      qgp_due_on: '2026-07-01',
      expiry_without_passed: false,
      atlas_hub_url: 'https://atlas',
    }
    vi.mocked(trainingMatrixApi.listCompliance).mockResolvedValueOnce({
      items: [
        {
          ...baseRow,
          atlas_name: 'Alice',
          department: 'Mobile Engineers',
          course_key: 'engineer-safety',
          course_display_name: 'Engineer Safety',
        },
        {
          ...baseRow,
          atlas_name: 'Bob',
          engineer_id: 2,
          engineer_display_name: 'Bob',
          department: 'Mobile Engineers',
          course_key: 'engineer-safety',
          course_display_name: 'Engineer Safety',
        },
        {
          ...baseRow,
          atlas_name: 'Casey',
          engineer_id: 3,
          engineer_display_name: 'Casey',
          department: 'Workshop',
          course_key: 'workshop-safety',
          course_display_name: 'Workshop Safety',
        },
      ],
      total: 3,
      atlas_hub_url: 'https://atlas',
    })

    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-matrix-briefing')).toHaveTextContent(
      'Engineer Safety',
    )
    await user.click(screen.getByTestId('training-matrix-hero-Workshop'))
    await waitFor(() =>
      expect(screen.getByTestId('training-matrix-briefing')).toHaveTextContent('Workshop Safety'),
    )
    expect(screen.getByTestId('training-matrix-briefing')).not.toHaveTextContent(
      'Engineer Safety',
    )
  })

  it('keeps entity Sheet email recipients aligned when the horizon changes', async () => {
    const user = userEvent.setup()
    const baseRow = {
      department: 'Mobile Engineers',
      course_key: 'shared-course',
      course_display_name: 'Shared Course',
      frequency_years: 1,
      atlas_status: null,
      passed_on: null,
      expires_on: null,
      qgp_due_on: null,
      expiry_without_passed: false,
      atlas_hub_url: 'https://atlas',
    }
    vi.mocked(trainingMatrixApi.listCompliance).mockResolvedValueOnce({
      items: [
        {
          ...baseRow,
          engineer_id: 1,
          engineer_display_name: 'Alice',
          atlas_name: 'Alice',
          status: 'compliant',
        },
        {
          ...baseRow,
          engineer_id: 2,
          engineer_display_name: 'Bob',
          atlas_name: 'Bob',
          status: 'overdue',
        },
      ],
      total: 2,
      atlas_hub_url: 'https://atlas',
    })
    vi.mocked(trainingMatrixApi.notify).mockResolvedValue({
      sent: 2,
      skipped: 0,
      failed: 0,
    })

    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    await user.click(await screen.findByTestId('training-matrix-view-course'))
    const courseTable = await screen.findByTestId('training-matrix-course-table')
    await user.click(within(courseTable).getByText('Shared Course'))

    const emailButton = screen.getByTestId('training-matrix-entity-email')
    await user.click(emailButton)
    await waitFor(() => expect(trainingMatrixApi.notify).toHaveBeenCalledWith(['Bob']))
    await waitFor(() => expect(emailButton).toBeEnabled())

    vi.mocked(trainingMatrixApi.notify).mockClear()
    await user.click(screen.getByTestId('training-matrix-horizon-all'))
    expect(screen.getByTestId('training-matrix-entity-sheet')).toBeInTheDocument()

    await user.click(emailButton)
    await waitFor(() =>
      expect(trainingMatrixApi.notify).toHaveBeenCalledWith(['Alice', 'Bob']),
    )
  })

  it('keeps latest import provenance when compliance loading fails', async () => {
    vi.mocked(trainingMatrixApi.listCompliance).mockRejectedValueOnce(new Error('Compliance unavailable'))
    vi.mocked(trainingMatrixApi.getSummary).mockResolvedValueOnce({
      module_ok: [{ role: 'Overall', ok: 8, total: 10, pct: 80, metric: 'module_ok' }],
      people_fully_ok: [
        { role: 'Overall', ok: 4, total: 5, pct: 80, metric: 'people_fully_ok' },
      ],
      horizons: {},
      top_overdue_courses: [],
      required_row_count: 10,
      person_count: 5,
      atlas_hub_url: 'https://atlas',
    })
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
    expect(await screen.findByText('Compliance unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('training-matrix-hero-Overall')).toHaveTextContent('0%')
    expect(screen.getByTestId('training-matrix-hero-Overall')).not.toHaveTextContent('80%')
  })
})
