import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listAssessments = vi.fn()
const listInductions = vi.fn()
const listEngineers = vi.fn()
const listAssetTypes = vi.fn()
const listTemplates = vi.fn()
const getAssessment = vi.fn()
const startAssessment = vi.fn()
const getInduction = vi.fn()
const startInduction = vi.fn()
const getEngineer = vi.fn()
const getTemplate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
  I18nextProvider: ({ children }: { children: unknown }) => children,
}))

vi.mock('../../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listAssessments,
    listInductions,
    listEngineers,
    listAssetTypes,
    createAssessment: vi.fn(),
    getAssessment,
    startAssessment,
    getInduction,
    startInduction,
    getEngineer,
  },
  auditsApi: {
    listTemplates,
    getTemplate,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Request failed') => {
    if (err && typeof err === 'object' && 'response' in err) {
      const data = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data
      if (data?.error?.message) return data.error.message
    }
    return fallback
  },
}))

vi.mock('../../builderMapAssistApi', () => ({
  fetchTemplateStandardsCoverage: vi.fn(),
}))

describe('WF-GATE Assessments filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listAssetTypes.mockResolvedValue({ data: { items: [{ id: 9, name: 'MEWP' }] } })
    listEngineers.mockResolvedValue({
      data: { items: [{ id: 42, employee_number: 'E-42', job_title: 'Tech' }] },
    })
    listTemplates.mockResolvedValue({ data: { items: [{ id: 1, name: 'Template A' }] } })
    listAssessments.mockResolvedValue({
      data: {
        items: [
          {
            id: 'a1',
            reference_number: 'ASS-0001',
            engineer_id: 42,
            template_id: 1,
            asset_type_id: 9,
            status: 'draft',
            scheduled_date: '2026-07-01',
          },
        ],
      },
    })
  })

  it('does not send unsupported search param and wires engineer_id', async () => {
    const Assessments = (await import('../Assessments')).default
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Assessments />
      </MemoryRouter>,
    )

    await waitFor(() => expect(listAssessments).toHaveBeenCalled())
    const firstParams = listAssessments.mock.calls[0][0] as Record<string, string>
    expect(firstParams.search).toBeUndefined()

    await waitFor(() =>
      expect(listEngineers).toHaveBeenCalledWith(
        expect.objectContaining({ is_active: 'true', page_size: '500' }),
      ),
    )

    const engineerSelect = await screen.findByLabelText('workforce.common.engineer')
    await user.selectOptions(engineerSelect, '42')

    await waitFor(() => {
      const last = listAssessments.mock.calls.at(-1)?.[0] as Record<string, string>
      expect(last.engineer_id).toBe('42')
      expect(last.search).toBeUndefined()
    })

    const filtersBtn = screen.getByRole('button', { name: /workforce\.common\.filters/i })
    expect(filtersBtn).toBeDisabled()
  })

  it('shows honest empty roster guidance when no active employees', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listAssessments.mockResolvedValue({ data: { items: [] } })

    const Assessments = (await import('../Assessments')).default
    render(
      <MemoryRouter>
        <Assessments />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('assessments-employees-empty')).toBeInTheDocument(),
    )
    expect(screen.getByLabelText('workforce.common.engineer')).toBeDisabled()
  })

  it('does not present a failed employee lookup as an empty roster', async () => {
    listEngineers.mockRejectedValue(new Error('engineers unavailable'))

    const Assessments = (await import('../Assessments')).default
    render(
      <MemoryRouter>
        <Assessments />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('assessments-employees-unavailable')).toHaveTextContent(
      /could not be loaded/i,
    )
    expect(screen.queryByTestId('assessments-employees-empty')).not.toBeInTheDocument()
    expect(screen.getByTestId('assessments-lookup-warning')).toHaveTextContent(
      /labels could not be loaded/i,
    )
  })
})

describe('WF-GATE AssessmentCreate required lookups', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listAssetTypes.mockResolvedValue({ data: { items: [] } })
    listEngineers.mockResolvedValue({ data: { items: [{ id: 42, employee_number: 'E-42' }] } })
    listTemplates.mockResolvedValue({ data: { items: [{ id: 1, name: 'Template A' }] } })
  })

  it('fails closed and identifies unavailable required form data', async () => {
    listTemplates.mockRejectedValue(new Error('templates unavailable'))
    listEngineers.mockRejectedValue(new Error('engineers unavailable'))

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('assessment-create-templates-unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('assessment-create-employees-unavailable')).toBeInTheDocument()
    expect(screen.getByLabelText(/workforce\.common\.template/i)).toBeDisabled()
    expect(screen.getByLabelText(/workforce\.common\.engineer/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /workforce\.assessments\.create_start/i })).toBeDisabled()
  })
})

describe('WF-GATE Training filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listAssetTypes.mockResolvedValue({ data: { items: [] } })
    listEngineers.mockResolvedValue({
      data: { items: [{ id: 7, employee_number: 'E-7' }] },
    })
    listTemplates.mockResolvedValue({ data: { items: [{ id: 2, name: 'Induct' }] } })
    listInductions.mockResolvedValue({
      data: {
        items: [
          {
            id: 'i1',
            reference_number: 'IND-0001',
            engineer_id: 7,
            template_id: 2,
            stage: 'stage_1_onsite',
            status: 'draft',
            scheduled_date: '2026-07-02',
          },
          {
            id: 'i2',
            reference_number: 'IND-0002',
            engineer_id: 7,
            template_id: 2,
            stage: 'stage_2_field',
            status: 'draft',
            scheduled_date: '2026-07-03',
          },
        ],
      },
    })
  })

  it('does not send stage or search to list API; stage filters client-side', async () => {
    const Training = (await import('../Training')).default
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    await waitFor(() => expect(listInductions).toHaveBeenCalled())
    const params = listInductions.mock.calls[0][0] as Record<string, string>
    expect(params.stage).toBeUndefined()
    expect(params.search).toBeUndefined()

    expect(await screen.findByText('IND-0001')).toBeInTheDocument()
    expect(screen.getByText('IND-0002')).toBeInTheDocument()

    const stageSelect = screen.getByLabelText('workforce.common.stage')
    await user.selectOptions(stageSelect, 'stage_1_onsite')

    expect(screen.getByText('IND-0001')).toBeInTheDocument()
    expect(screen.queryByText('IND-0002')).not.toBeInTheDocument()

    // Still no unsupported params on subsequent loads
    for (const call of listInductions.mock.calls) {
      const p = call[0] as Record<string, string>
      expect(p.stage).toBeUndefined()
      expect(p.search).toBeUndefined()
    }

    expect(screen.getByRole('button', { name: /workforce\.common\.filters/i })).toBeDisabled()
  })

  it('warns when lookup labels fail instead of silently showing raw IDs', async () => {
    listEngineers.mockRejectedValue(new Error('engineers unavailable'))

    const Training = (await import('../Training')).default
    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('training-lookup-warning')).toHaveTextContent(
      /labels could not be loaded/i,
    )
    expect(screen.getAllByText('#7')).not.toHaveLength(0)
  })
})

describe('WF-GATE AssessmentExecution start-gate honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getEngineer.mockResolvedValue({ data: { employee_number: 'E-42' } })
    getTemplate.mockResolvedValue({
      data: {
        name: 'Template A',
        sections: [
          {
            title: 'S1',
            questions: [{ id: 1, question_text: 'Q1?', help_text: null, criticality: 'essential' }],
          },
        ],
      },
    })
  })

  it('surfaces soft-gate warning from start response fields', async () => {
    getAssessment.mockResolvedValue({
      data: {
        id: 'a1',
        reference_number: 'ASS-0001',
        engineer_id: 42,
        template_id: 1,
        status: 'draft',
        title: 'Run',
      },
    })
    startAssessment.mockResolvedValue({
      data: {
        id: 'a1',
        reference_number: 'ASS-0001',
        engineer_id: 42,
        template_id: 1,
        status: 'in_progress',
        competency_gate_cleared: false,
        competency_gate_reason: 'Reassessment overdue',
        competency_gate_mode: 'soft',
      },
    })

    const AssessmentExecution = (await import('../AssessmentExecution')).default

    render(
      <MemoryRouter initialEntries={['/workforce/assessments/a1/execute']}>
        <Routes>
          <Route path="/workforce/assessments/:id/execute" element={<AssessmentExecution />} />
        </Routes>
      </MemoryRouter>,
    )

    const banner = await screen.findByTestId('competency-gate-soft-warning')
    expect(within(banner).getByText(/Reassessment overdue/)).toBeInTheDocument()
    expect(within(banner).getByText(/Competency gate warning \(soft\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View competencies/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View tickets \/ passport/i })).toBeInTheDocument()
    expect(await screen.findByText('Q1?')).toBeInTheDocument()
  })

  it('shows hard-gate remediation when start is blocked', async () => {
    getAssessment.mockResolvedValue({
      data: {
        id: 'a1',
        reference_number: 'ASS-0001',
        engineer_id: 42,
        template_id: 1,
        status: 'draft',
        title: 'Run',
      },
    })
    startAssessment.mockRejectedValue({
      response: {
        status: 403,
        data: {
          error: {
            code: 'COMPETENCY_GATE_BLOCKED',
            message: 'Competency gate blocked start',
            details: { cleared: false, mode: 'hard' },
          },
        },
      },
    })

    const AssessmentExecution = (await import('../AssessmentExecution')).default

    render(
      <MemoryRouter initialEntries={['/workforce/assessments/a1/execute']}>
        <Routes>
          <Route path="/workforce/assessments/:id/execute" element={<AssessmentExecution />} />
        </Routes>
      </MemoryRouter>,
    )

    const blocked = await screen.findByTestId('competency-gate-blocked')
    expect(within(blocked).getByText(/Competency gate blocked start/)).toBeInTheDocument()
    expect(within(blocked).getByText(/Remediation/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View competencies/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View tickets \/ passport/i })).toBeInTheDocument()
    expect(screen.queryByText('Q1?')).not.toBeInTheDocument()
  })
})

describe('WF-GATE TrainingExecution start-gate honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getEngineer.mockResolvedValue({ data: { employee_number: 'E-7' } })
    getTemplate.mockResolvedValue({
      data: {
        name: 'Induct',
        sections: [
          {
            title: 'S1',
            questions: [{ id: 1, question_text: 'Show item?', criticality: 'essential' }],
          },
        ],
      },
    })
  })

  it('mirrors soft-gate warning on induction start', async () => {
    getInduction.mockResolvedValue({
      data: {
        id: 'i1',
        reference_number: 'IND-0001',
        engineer_id: 7,
        template_id: 2,
        status: 'draft',
        stage: 'stage_1_onsite',
      },
    })
    startInduction.mockResolvedValue({
      data: {
        id: 'i1',
        reference_number: 'IND-0001',
        engineer_id: 7,
        template_id: 2,
        status: 'in_progress',
        stage: 'stage_1_onsite',
        competency_gate_cleared: false,
        competency_gate_reason: 'No active competency record',
        competency_gate_mode: 'soft',
      },
    })

    const TrainingExecution = (await import('../TrainingExecution')).default

    render(
      <MemoryRouter initialEntries={['/workforce/training/i1/execute']}>
        <Routes>
          <Route path="/workforce/training/:id/execute" element={<TrainingExecution />} />
        </Routes>
      </MemoryRouter>,
    )

    const banner = await screen.findByTestId('competency-gate-soft-warning')
    expect(within(banner).getByText(/No active competency record/)).toBeInTheDocument()
    expect(await screen.findByText('Show item?')).toBeInTheDocument()
  })
})

describe('isCompetencyGateBlockedError / readCompetencyGateWarning', () => {
  it('parses blocked envelope and soft warning fields', async () => {
    const { isCompetencyGateBlockedError, readCompetencyGateWarning } = await import(
      '../AssessmentExecution'
    )

    expect(
      isCompetencyGateBlockedError({
        response: { data: { error: { code: 'COMPETENCY_GATE_BLOCKED' } } },
      }),
    ).toBe(true)
    expect(isCompetencyGateBlockedError({ response: { data: { error: { code: 'OTHER' } } } })).toBe(
      false,
    )

    expect(
      readCompetencyGateWarning({
        competency_gate_cleared: false,
        competency_gate_reason: 'due',
        competency_gate_mode: 'soft',
      }),
    ).toEqual({ cleared: false, reason: 'due', mode: 'soft' })

    expect(readCompetencyGateWarning({ competency_gate_cleared: true })).toBeNull()
  })
})
