import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : _key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const getRosterDelta = vi.fn()
const resolveRosterAction = vi.fn()
const upsertNameMap = vi.fn()

vi.mock('../../../api/client', () => ({
  trainingMatrixApi: {
    listNameMaps: vi.fn().mockResolvedValue([]),
    listRequirements: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listCourses: vi.fn().mockResolvedValue([]),
    uploadImport: vi.fn(),
    getLatestImport: vi.fn().mockRejectedValue(new Error('No training matrix import found')),
    upsertNameMap: (...args: unknown[]) => upsertNameMap(...args),
    autoMatchNameMaps: vi.fn().mockResolvedValue({
      people_considered: 0,
      already_mapped: 0,
      from_saved_maps: 0,
      from_auto_match: 0,
      still_unmatched: 0,
    }),
    seedRequirements: vi.fn(),
    upsertRequirementsMatrix: vi.fn(),
    proposeRequirementsMatrix: vi.fn(),
    listMatrixProposals: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      viewer_can_approve: false,
      approver_email: 'david.harris@plantexpand.com',
    }),
    approveMatrixProposal: vi.fn(),
    rejectMatrixProposal: vi.fn(),
    notify: vi.fn(),
    getRosterDelta: (...args: unknown[]) => getRosterDelta(...args),
    resolveRosterAction: (...args: unknown[]) => resolveRosterAction(...args),
    patchPersonBoardRole: vi.fn(),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({
      data: { items: [{ id: 9, display_name: 'Existing Person' }] },
    }),
  },
  getApiErrorMessage: (e: unknown, fallback?: string) =>
    e instanceof Error ? e.message : fallback || 'error',
  ATLAS_HUB_URL: 'https://www.atlas-hub.co.uk/o/98b88f4e-2c3f-44c1-a812-36ea66222c7d/',
}))

import { TrainingMatrixAdminPanel } from '../trainingMatrix/TrainingMatrixPanels'

const emptyDelta = {
  latest_import_id: 2,
  latest_import_filename: 'atlas.csv',
  latest_person_count: 2,
  appeared: [] as const,
  disappeared: [] as const,
  appeared_count: 0,
  appeared_new_this_import: 0,
  disappeared_count: 0,
  atlas_hub_url: 'https://atlas',
}

const joiner = {
  person_id: 11,
  atlas_name: 'An Example',
  department: 'Finance',
  first_seen_at: '2026-08-31T00:00:00Z',
  new_since_previous_import: true,
  last_seen_import_id: 2,
  reason: 'unmapped' as const,
  suggested_action: 'create_person' as const,
}

const leaver = {
  person_id: 22,
  atlas_name: 'Cameron Example',
  department: 'Workshop',
  first_seen_at: '2026-07-21T00:00:00Z',
  new_since_previous_import: false,
  last_seen_import_id: 1,
  last_seen_filename: 'old.csv',
  reason: 'left_roster' as const,
  suggested_action: 'archive' as const,
  engineer_id: 158,
  engineer_display_name: 'Cameron Example',
  engineer_is_active: true,
  engineer_pams_technician_id: 158,
  user_email: null,
}

describe('Training matrix roster delta admin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRosterDelta.mockResolvedValue({
      ...emptyDelta,
      appeared: [joiner],
      disappeared: [leaver],
      appeared_count: 1,
      appeared_new_this_import: 1,
      disappeared_count: 1,
    })
    resolveRosterAction.mockResolvedValue({
      person_id: 22,
      action: 'archive',
      engineer_id: 158,
      engineer_is_active: false,
      login_disabled: false,
      atlas_person_changed: false,
      message: 'Archived. Atlas row unchanged. PAMS and Entra were not written.',
    })
    upsertNameMap.mockResolvedValue({ atlas_name: 'An Example', engineer_id: 9, mapped: true })
  })

  it('asks whether to archive or create a person record after Atlas data arrives', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(
      <MemoryRouter>
        <TrainingMatrixAdminPanel />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-matrix-admin-roster')).toBeInTheDocument()
    expect(screen.getByTestId('training-matrix-roster-count')).toHaveTextContent('2 to review')
    expect(screen.getByTestId('training-matrix-roster-appeared')).toHaveTextContent('An Example')
    expect(screen.getByTestId('training-matrix-roster-disappeared')).toHaveTextContent(
      'Cameron Example',
    )
    expect(screen.queryByText(/create login/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/invite/i)).not.toBeInTheDocument()

    await user.click(screen.getByTestId('training-matrix-roster-archive'))
    expect(confirm).toHaveBeenCalled()
    const archivePrompt = String(confirm.mock.calls[0]?.[0] ?? '')
    expect(archivePrompt).toMatch(/Archive this QGP account/)
    expect(archivePrompt).toMatch(/Atlas: Cameron Example/)
    expect(archivePrompt).toMatch(/PAMS and Entra will not be changed/)
    await waitFor(() =>
      expect(resolveRosterAction).toHaveBeenCalledWith(22, 'archive'),
    )

    confirm.mockClear()
    await user.click(screen.getByTestId('training-matrix-roster-create'))
    const createPrompt = String(confirm.mock.calls[0]?.[0] ?? '')
    expect(createPrompt).toMatch(/Create a QGP person record/)
    expect(createPrompt).toMatch(/No login is created/)
    await waitFor(() =>
      expect(resolveRosterAction).toHaveBeenCalledWith(11, 'create_person'),
    )
    confirm.mockRestore()
  })

  it('reuses people-mapping link instead of a second employee directory', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(
      <MemoryRouter>
        <TrainingMatrixAdminPanel />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-matrix-admin-namemap')).toBeInTheDocument()
    await user.selectOptions(screen.getByTestId('training-matrix-roster-link-select'), '9')
    await user.click(screen.getByTestId('training-matrix-roster-link'))
    expect(upsertNameMap).toHaveBeenCalledWith('An Example', 9)
    confirm.mockRestore()
  })

  it('does not report an empty roster while the request is still loading', async () => {
    let resolveRoster = (_value: typeof emptyDelta) => {}
    getRosterDelta.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRoster = resolve
        }),
    )

    render(
      <MemoryRouter>
        <TrainingMatrixAdminPanel />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-matrix-roster-loading')).toBeInTheDocument()
    expect(screen.queryByTestId('training-matrix-roster-empty')).not.toBeInTheDocument()

    await act(async () => resolveRoster(emptyDelta))
    expect(await screen.findByTestId('training-matrix-roster-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('training-matrix-roster-loading')).not.toBeInTheDocument()
  })

  it('shows a retryable error instead of an empty roster when loading fails', async () => {
    const user = userEvent.setup()
    getRosterDelta
      .mockRejectedValueOnce(new Error('Atlas roster unavailable'))
      .mockResolvedValueOnce(emptyDelta)

    render(
      <MemoryRouter>
        <TrainingMatrixAdminPanel />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-matrix-roster-error')).toHaveTextContent(
      'Atlas roster unavailable',
    )
    expect(screen.queryByTestId('training-matrix-roster-empty')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('training-matrix-roster-retry'))
    expect(await screen.findByTestId('training-matrix-roster-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('training-matrix-roster-error')).not.toBeInTheDocument()
    expect(getRosterDelta).toHaveBeenCalledTimes(2)
  })
})
