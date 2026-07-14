import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CompetenceGaps, {
  competenceGapActionHref,
  resolveEngineerLabel,
  resolveRequirementLabel,
} from '../CompetenceGaps'
import {
  competenceGapApi,
  competenceGapSourceLabelKey,
  engineerPickerLabel,
  requirementPickerLabel,
  type CompetenceGapAction,
} from '../../api/competenceGapClient'
import { toast } from '../../contexts/ToastContext'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      const map: Record<string, string> = {
        'competenceGaps.title': 'Competence gaps',
        'competenceGaps.subtitle': 'Closed-loop inbox',
        'competenceGaps.filter.label': 'Status',
        'competenceGaps.filter.all': 'All statuses',
        'competenceGaps.filter.open': 'Open',
        'competenceGaps.filter.linked': 'Linked',
        'competenceGaps.filter.capa_created': 'CAPA created',
        'competenceGaps.filter.resolved': 'Resolved',
        'competenceGaps.filter.dismissed': 'Dismissed',
        'competenceGaps.empty.title': 'No competence gaps',
        'competenceGaps.empty.description': 'Confirm Assessor signals to open actions here.',
        'competenceGaps.empty.filter_title': 'No competence gaps match this filter',
        'competenceGaps.empty.filter_description': 'Try another status, or clear the filter.',
        'competenceGaps.load_failed': 'Could not load competence gaps',
        'competenceGaps.row.id': `Gap #${opts?.id ?? ''}`,
        'competenceGaps.row.source': `${opts?.source ?? ''} #${opts?.id ?? ''}`,
        'competenceGaps.row.links': `Engineer ${opts?.engineer} · Requirement ${opts?.requirement} · CAPA ${opts?.capa}`,
        'competenceGaps.source.assessor_case': 'Assessor case',
        'competenceGaps.source.external_audit_finding': 'External audit finding',
        'competenceGaps.source.compliance_evidence_link': 'Compliance evidence',
        'competenceGaps.source.unknown': 'Source',
        'competenceGaps.signal.competence_gap': 'Competence gap',
        'competenceGaps.signal.nonconformity': 'Nonconformity',
        'competenceGaps.link.engineer': 'Engineer',
        'competenceGaps.link.engineer_placeholder': 'Select engineer',
        'competenceGaps.link.requirement': 'Requirement',
        'competenceGaps.link.requirement_optional': 'None (optional)',
        'competenceGaps.actions.link': 'Link engineer',
        'competenceGaps.actions.create_capa': 'Create CAPA',
        'competenceGaps.actions.resolve': 'Resolve',
        'competenceGaps.actions.dismiss': 'Dismiss',
        'competenceGaps.actions.golden_thread': 'Golden thread',
        'competenceGaps.actions.open_capa': 'Open CAPA',
        'competenceGaps.toast.engineer_required': 'Select an engineer to link',
        'competenceGaps.toast.linked': 'Engineer linked',
        'competenceGaps.toast.capa_created': `CAPA ${opts?.ref ?? ''} created`,
        'competenceGaps.toast.resolved': 'Competence gap resolved',
        'competenceGaps.toast.resolve_notes': 'Resolved from competence gaps inbox',
        'competenceGaps.toast.dismiss_notes': 'Dismissed from competence gaps inbox',
        'competenceGaps.toast.dismissed': 'Competence gap dismissed',
      }
      return map[key] || key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('../../api/competenceGapClient', async () => {
  const actual = await vi.importActual<typeof import('../../api/competenceGapClient')>(
    '../../api/competenceGapClient',
  )
  return {
    ...actual,
    competenceGapApi: {
      list: vi.fn(),
      get: vi.fn(),
      fromSignal: vi.fn(),
      link: vi.fn(),
      createCapa: vi.fn(),
      resolve: vi.fn(),
      goldenThread: vi.fn(),
      listPickerEngineers: vi.fn(),
      listPickerRequirements: vi.fn(),
    },
  }
})

vi.mock('../../api/client', () => ({
  getApiErrorMessage: (err: { message?: string }) => err?.message || 'Unknown error',
}))

const openGap = (overrides: Partial<CompetenceGapAction> = {}): CompetenceGapAction => ({
  id: 1,
  tenant_id: 1,
  source_type: 'assessor_case',
  source_id: 99,
  signal_type: 'competence_gap',
  engineer_id: null,
  requirement_id: null,
  ticket_scheme: null,
  capa_action_id: null,
  status: 'open',
  rationale: 'Missing IPAF',
  confidence: 0.9,
  created_by_id: 1,
  resolved_at: null,
  resolved_by_id: null,
  created_at: '2026-07-14T00:00:00Z',
  updated_at: '2026-07-14T00:00:00Z',
  action_key: null,
  ...overrides,
})

function renderPage(path = '/workforce/competence-gaps') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CompetenceGaps />
    </MemoryRouter>,
  )
}

describe('competenceGapActionHref', () => {
  it('deep-links to workforce competence gaps inbox with id', () => {
    expect(competenceGapActionHref(42)).toBe('/workforce/competence-gaps?id=42')
  })
})

describe('label helpers', () => {
  it('maps source types to human i18n keys (not type:id)', () => {
    expect(competenceGapSourceLabelKey('assessor_case')).toBe(
      'competenceGaps.source.assessor_case',
    )
    expect(competenceGapSourceLabelKey('mystery')).toBe('competenceGaps.source.unknown')
  })

  it('formats engineer and requirement picker labels', () => {
    expect(engineerPickerLabel({ id: 7, employee_number: 'E-007' })).toBe('E-007')
    expect(engineerPickerLabel({ id: 8, job_title: 'Joiner' })).toBe('Joiner')
    expect(requirementPickerLabel({ id: 3, name: 'IPAF 3a' })).toBe('IPAF 3a')
    expect(resolveEngineerLabel(7, [{ id: 7, employee_number: 'E-007' }])).toBe('E-007')
    expect(resolveRequirementLabel(3, [{ id: 3, name: 'IPAF 3a' }])).toBe('IPAF 3a')
    expect(resolveEngineerLabel(null, [])).toBe('—')
  })
})

describe('CompetenceGaps inbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(competenceGapApi.listPickerEngineers).mockResolvedValue({
      data: {
        items: [
          { id: 10, employee_number: 'ENG-10', job_title: 'Tech' },
          { id: 11, employee_number: 'ENG-11', job_title: 'Lead' },
        ],
        total: 2,
      },
    } as never)
    vi.mocked(competenceGapApi.listPickerRequirements).mockResolvedValue({
      data: {
        items: [
          { id: 20, name: 'IPAF 3a' },
          { id: 21, name: 'CSCS' },
        ],
        total: 2,
      },
    } as never)
  })

  it('shows global empty copy when inbox has no gaps', async () => {
    vi.mocked(competenceGapApi.list).mockResolvedValue({ data: [] } as never)
    renderPage()
    expect(await screen.findByText('No competence gaps')).toBeInTheDocument()
    expect(
      screen.getByText('Confirm Assessor signals to open actions here.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('No competence gaps match this filter')).not.toBeInTheDocument()
  })

  it('shows filter-empty copy when a status filter returns no rows', async () => {
    const user = userEvent.setup()
    vi.mocked(competenceGapApi.list).mockResolvedValue({ data: [] } as never)
    renderPage()
    await screen.findByText('No competence gaps')

    await user.selectOptions(screen.getByTestId('competence-gap-status-filter'), 'open')

    await waitFor(() => {
      expect(competenceGapApi.list).toHaveBeenCalledWith({ status: 'open' })
    })
    expect(await screen.findByText('No competence gaps match this filter')).toBeInTheDocument()
    expect(screen.getByText('Try another status, or clear the filter.')).toBeInTheDocument()
    expect(screen.queryByText('No competence gaps')).not.toBeInTheDocument()
  })

  it('renders human source/engineer/requirement labels instead of type:id', async () => {
    vi.mocked(competenceGapApi.list).mockResolvedValue({
      data: [
        openGap({
          id: 5,
          engineer_id: 10,
          requirement_id: 20,
          status: 'linked',
        }),
      ],
    } as never)
    renderPage()
    expect(await screen.findByText(/Assessor case #99/)).toBeInTheDocument()
    expect(screen.getByText(/Engineer ENG-10 · Requirement IPAF 3a · CAPA —/)).toBeInTheDocument()
    expect(screen.queryByText('assessor_case:99')).not.toBeInTheDocument()
  })

  it('keeps engineer/requirement pickers independent per row', async () => {
    const user = userEvent.setup()
    vi.mocked(competenceGapApi.list).mockResolvedValue({
      data: [openGap({ id: 1 }), openGap({ id: 2, source_id: 100 })],
    } as never)
    renderPage()

    const eng1 = await screen.findByTestId('competence-gap-engineer-1')
    const eng2 = await screen.findByTestId('competence-gap-engineer-2')
    await user.selectOptions(eng1, '10')
    await user.selectOptions(eng2, '11')

    expect(eng1).toHaveValue('10')
    expect(eng2).toHaveValue('11')
  })

  it('CUJ: list → link → create CAPA → resolve', async () => {
    const user = userEvent.setup()
    let gap = openGap({ id: 42 })

    vi.mocked(competenceGapApi.list).mockImplementation(async () => ({ data: [gap] }) as never)
    vi.mocked(competenceGapApi.link).mockImplementation(async () => {
      gap = {
        ...gap,
        engineer_id: 10,
        requirement_id: 20,
        status: 'linked',
      }
      return { data: gap } as never
    })
    vi.mocked(competenceGapApi.createCapa).mockImplementation(async () => {
      gap = {
        ...gap,
        capa_action_id: 77,
        action_key: 'capa:77',
        status: 'capa_created',
      }
      return {
        data: {
          gap,
          action: {
            id: 77,
            reference_number: 'CAPA-77',
            title: 'Gap CAPA',
            status: 'open',
            priority: 'medium',
            owner_id: null,
            due_date: null,
            source_type: 'competence_gap',
            source_id: 42,
            action_key: 'capa:77',
          },
        },
      } as never
    })
    vi.mocked(competenceGapApi.resolve).mockImplementation(async () => {
      gap = { ...gap, status: 'resolved', resolved_at: '2026-07-14T12:00:00Z' }
      return { data: gap } as never
    })

    renderPage()

    const row = await screen.findByTestId('competence-gap-row-42')
    expect(within(row).getByText('Gap #42')).toBeInTheDocument()
    expect(within(row).getByText(/Assessor case #99/)).toBeInTheDocument()

    await user.selectOptions(within(row).getByTestId('competence-gap-engineer-42'), '10')
    await user.selectOptions(within(row).getByTestId('competence-gap-requirement-42'), '20')
    await user.click(within(row).getByRole('button', { name: 'Link engineer' }))

    await waitFor(() => {
      expect(competenceGapApi.link).toHaveBeenCalledWith(42, {
        engineer_id: 10,
        requirement_id: 20,
      })
    })
    expect(toast.success).toHaveBeenCalledWith('Engineer linked')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create CAPA' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Create CAPA' }))
    await waitFor(() => {
      expect(competenceGapApi.createCapa).toHaveBeenCalledWith(42)
    })
    expect(toast.success).toHaveBeenCalledWith('CAPA CAPA-77 created')

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Open CAPA' })).toHaveAttribute(
        'href',
        '/actions?action_key=capa%3A77',
      )
    })

    await user.click(screen.getByRole('button', { name: 'Resolve' }))
    await waitFor(() => {
      expect(competenceGapApi.resolve).toHaveBeenCalledWith(42, {
        dismiss: false,
        notes: 'Resolved from competence gaps inbox',
      })
    })
    expect(toast.success).toHaveBeenCalledWith('Competence gap resolved')
  })
})
