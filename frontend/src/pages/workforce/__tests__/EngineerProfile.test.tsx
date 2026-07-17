import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  listAssetTypes,
  getEngineer,
  getCompetencies,
  listTickets,
  createTicket,
  updateTicket,
  listRequirements,
  t,
} = vi.hoisted(() => {
  const t = (key: string, opts?: Record<string, unknown>) => {
    if (opts && typeof opts === 'object') {
      return `${key}:${JSON.stringify(opts)}`
    }
    return key
  }
  return {
    listAssetTypes: vi.fn(),
    getEngineer: vi.fn(),
    getCompetencies: vi.fn(),
    listTickets: vi.fn(),
    createTicket: vi.fn(),
    updateTicket: vi.fn(),
    listRequirements: vi.fn(),
    t,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listAssetTypes,
    getEngineer,
    getCompetencies,
    trainingTickets: {
      list: (...args: unknown[]) => listTickets(...args),
      create: (...args: unknown[]) => createTicket(...args),
      update: (...args: unknown[]) => updateTicket(...args),
    },
    competencyRequirements: {
      list: (...args: unknown[]) => listRequirements(...args),
    },
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'load failed',
}))

vi.mock('../../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

import EngineerProfile, {
  competenceGapsEngineerHref,
  computeRequirementsMatch,
} from '../EngineerProfile'

type CompetencyRequirement = {
  id: number
  asset_type_id: number
  template_id: number
  name: string
  is_mandatory: boolean
  reassessment_interval_days: number
  tenant_id: number
  created_at: string
  updated_at: string
}

type CompetencyRecord = {
  id: number
  engineer_id: number
  asset_type_id: number
  template_id: number
  state: string
  source_type: string
}

const engineer = {
  id: 7,
  external_id: 'ext-abcdef12',
  user_id: 1,
  employee_number: 'E-007',
  job_title: 'Field Engineer',
  department: 'Ops',
  site: 'North',
  is_active: true,
}

function req(
  partial: Partial<CompetencyRequirement> & Pick<CompetencyRequirement, 'id' | 'asset_type_id'>,
): CompetencyRequirement {
  return {
    template_id: 1,
    name: `Req ${partial.id}`,
    is_mandatory: true,
    reassessment_interval_days: 365,
    tenant_id: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...partial,
  }
}

function comp(
  partial: Partial<CompetencyRecord> & Pick<CompetencyRecord, 'id' | 'asset_type_id' | 'state'>,
): CompetencyRecord {
  return {
    engineer_id: 7,
    template_id: 1,
    source_type: 'assessment',
    ...partial,
  }
}

describe('computeRequirementsMatch', () => {
  it('returns null percent when there are no mandatory requirements (empty)', () => {
    expect(computeRequirementsMatch([], [])).toEqual({
      mandatoryTotal: 0,
      mandatoryMet: 0,
      percent: null,
    })
  })

  it('computes percent as mandatory met / mandatory total', () => {
    const requirements = [
      req({ id: 1, asset_type_id: 10 }),
      req({ id: 2, asset_type_id: 20 }),
    ]
    const competencies = [
      comp({ id: 1, asset_type_id: 10, state: 'active' }),
      comp({ id: 2, asset_type_id: 20, state: 'expired' }),
    ]
    expect(computeRequirementsMatch(requirements, competencies)).toEqual({
      mandatoryTotal: 2,
      mandatoryMet: 1,
      percent: 50,
    })
  })

  it('ignores non-mandatory and inactive competencies', () => {
    const requirements = [
      req({ id: 1, asset_type_id: 10 }),
      req({ id: 2, asset_type_id: 20, is_mandatory: false }),
    ]
    const competencies = [
      comp({ id: 1, asset_type_id: 10, state: 'expired' }),
      comp({ id: 2, asset_type_id: 20, state: 'active' }),
    ]
    expect(computeRequirementsMatch(requirements, competencies)).toEqual({
      mandatoryTotal: 1,
      mandatoryMet: 0,
      percent: 0,
    })
  })
})

describe('competenceGapsEngineerHref', () => {
  it('deep-links competence gaps filtered by engineer', () => {
    expect(competenceGapsEngineerHref(7)).toBe('/workforce/competence-gaps?engineer_id=7')
  })
})

describe('EngineerProfile', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    listAssetTypes.mockReset()
    getEngineer.mockReset()
    getCompetencies.mockReset()
    listTickets.mockReset()
    createTicket.mockReset()
    updateTicket.mockReset()
    listRequirements.mockReset()

    listAssetTypes.mockResolvedValue({
      data: { items: [{ id: 10, name: 'MEWP', category: 'plant', is_active: true }] },
    })
    getEngineer.mockResolvedValue({ data: engineer })
    getCompetencies.mockResolvedValue({
      data: [comp({ id: 1, asset_type_id: 10, state: 'active' })],
    })
    listTickets.mockResolvedValue({
      data: {
        items: [
          {
            id: 91,
            engineer_id: 7,
            scheme: 'IPAF',
            ticket_number: 'IP-100',
            expires_at: '2027-01-15T00:00:00Z',
            verify_state: 'verified',
            evidence_id: 55,
            tenant_id: 1,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
    listRequirements.mockResolvedValue({
      data: {
        items: [req({ id: 1, asset_type_id: 10, name: 'MEWP competent' })],
        total: 1,
        page: 1,
        page_size: 200,
        pages: 1,
      },
    })
  })

  it('shows not found state for invalid engineer ids without loading forever', async () => {
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/abc']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('workforce.engineers.not_found')).toBeInTheDocument()
    expect(getEngineer).not.toHaveBeenCalled()
    expect(getCompetencies).not.toHaveBeenCalled()
  })

  it('renders training ticket list with scheme number expiry verify_state and evidence', async () => {
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('tickets-table')).toBeInTheDocument()
    expect(screen.getByText('IPAF')).toBeInTheDocument()
    expect(screen.getByText('IP-100')).toBeInTheDocument()
    expect(screen.getByText('verified')).toBeInTheDocument()
    expect(
      screen.getByText('workforce.engineers.tickets.evidence_id:{"id":55}'),
    ).toBeInTheDocument()
    expect(listTickets).toHaveBeenCalledWith(expect.objectContaining({ engineer_id: 7 }))
  })

  it('shows requirements % match when mandatory requirements exist', async () => {
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('engineer-identity')).toBeInTheDocument()
    })
    expect(screen.getByTestId('engineer-user-link-linked')).toHaveTextContent(
      'workforce.engineers.user_link.linked:{"id":1}',
    )
    expect(await screen.findByTestId('requirements-match-percent')).toHaveTextContent('100%')
    expect(
      screen.getByText('workforce.engineers.requirements.match_detail:{"met":1,"total":1}'),
    ).toBeInTheDocument()
  })

  it('shows honest unlinked user state when engineer has no user_id (EMP-06)', async () => {
    getEngineer.mockResolvedValue({ data: { ...engineer, user_id: null } })
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('engineer-user-link-unlinked')).toBeInTheDocument()
    expect(screen.getByText('workforce.engineers.user_link.unlinked')).toBeInTheDocument()
    expect(screen.getByText('workforce.engineers.user_link.unlinked_hint')).toBeInTheDocument()
    expect(screen.queryByTestId('engineer-user-link-linked')).not.toBeInTheDocument()
  })

  it('shows empty match state when there are no mandatory requirements', async () => {
    listRequirements.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 200, pages: 0 },
    })
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('requirements-match-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('requirements-match-percent')).not.toBeInTheDocument()
  })

  it('surfaces requirements load error instead of silent zero percent', async () => {
    listRequirements.mockRejectedValue(new Error('requirements down'))
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('requirements-match-error')).toBeInTheDocument()
    expect(screen.getByText(/requirements down/)).toBeInTheDocument()
    expect(screen.queryByTestId('requirements-match-percent')).not.toBeInTheDocument()
  })

  it('does not silently ignore asset type map failures', async () => {
    listAssetTypes.mockRejectedValue(new Error('asset types down'))
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('asset-type-map-error')).toBeInTheDocument()
    expect(screen.getByText(/asset types down/)).toBeInTheDocument()
  })

  it('links to competence gaps filtered by engineer', async () => {
    render(
      <MemoryRouter initialEntries={['/workforce/engineers/7']}>
        <Routes>
          <Route path="/workforce/engineers/:id" element={<EngineerProfile />} />
        </Routes>
      </MemoryRouter>,
    )

    const link = await screen.findByTestId('engineer-competence-gaps-link')
    expect(link).toHaveAttribute('href', '/workforce/competence-gaps?engineer_id=7')
  })
})
