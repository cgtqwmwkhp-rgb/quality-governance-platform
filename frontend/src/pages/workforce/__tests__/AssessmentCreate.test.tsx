import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listEngineers = vi.fn()
const listTemplates = vi.fn()
const listAssetTypes = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
  I18nextProvider: ({ children }: { children: unknown }) => children,
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listEngineers,
    listAssetTypes,
    createAssessment: vi.fn(),
  },
  auditsApi: {
    listTemplates,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Request failed') =>
    err instanceof Error ? err.message : fallback,
}))

describe('AssessmentCreate employee picker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTemplates.mockResolvedValue({
      data: {
        items: [{ id: 1, name: 'Template A', audit_type: 'competency', tags: ['instrument:skills'] }],
      },
    })
    listAssetTypes.mockResolvedValue({ data: { items: [] } })
  })

  it('loads active employees with role-aware labels', async () => {
    listEngineers.mockResolvedValue({
      data: {
        items: [
          {
            id: 42,
            external_id: 'x',
            is_active: true,
            display_name: 'Alex Technician',
            job_title: 'Plant Tech',
            department: 'Ops',
          },
        ],
      },
    })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    await waitFor(() => expect(listEngineers).toHaveBeenCalled())
    expect(listEngineers).toHaveBeenCalledWith(
      expect.objectContaining({ is_active: 'true', page_size: '500' }),
    )

    const select = await screen.findByLabelText(/workforce\.common\.engineer/i)
    expect(select).toHaveTextContent('Alex Technician — Plant Tech · Ops')
  })

  it('shows honest empty roster guidance when no active employees', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('assessment-create-employees-empty')).toBeInTheDocument(),
    )
    expect(screen.getByText('workforce.assessments.employees_empty')).toBeInTheDocument()
    expect(screen.getByText('workforce.assessments.employees_empty_link')).toHaveAttribute(
      'href',
      '/workforce/engineers',
    )
    expect(screen.getByLabelText(/workforce\.common\.engineer/i)).toBeDisabled()
  })

  it('shows MAP Assist confirm-loop honesty on competency create', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('map-w2-competency-assist-panel')).toBeInTheDocument()
    expect(screen.getByTestId('map-w2-competency-assist-honesty')).toHaveTextContent(
      /Assist Map confirm loop is live/i,
    )
    expect(screen.getByTestId('map-w2-competency-scheme-chips')).toBeInTheDocument()
    expect(screen.getByTestId('map-w2-competency-scheme-iso')).toBeInTheDocument()
    expect(screen.getByTestId('map-w2-competency-scheme-planet-mark')).toBeInTheDocument()
    expect(screen.getByTestId('map-w2-competency-scheme-uvdb')).toBeInTheDocument()
  })

  it('seeds the template select from ?templateId=', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 1, name: 'Template A', audit_type: 'competency', tags: ['instrument:skills'] },
          {
            id: 42,
            name: 'Seeded skills template',
            audit_type: 'inspection',
            tags: ['instrument:skills'],
          },
        ],
      },
    })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter initialEntries={['/workforce/assessments/new?templateId=42']}>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    const select = await screen.findByLabelText(/workforce\.common\.template/i)
    await waitFor(() => expect(select).toHaveValue('42'))
  })

  it('hides published templates that are not skills instruments', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 1, name: 'Audit template', audit_type: 'inspection', tags: ['instrument:audit'] },
          { id: 2, name: 'Skills template', audit_type: 'inspection', tags: ['instrument:skills'] },
          {
            id: 3,
            name: 'Induction template',
            audit_type: 'inspection',
            tags: ['instrument:induction'],
          },
          { id: 4, name: 'Untagged template', audit_type: 'inspection', tags: [] },
        ],
      },
    })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    const select = await screen.findByLabelText(/workforce\.common\.template/i)
    expect(select).toHaveTextContent('Skills template')
    expect(select).not.toHaveTextContent('Audit template')
    expect(select).not.toHaveTextContent('Induction template')
    expect(select).not.toHaveTextContent('Untagged template')
  })

  it('shows an author-skills empty state when no skills templates exist', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 1, name: 'Audit template', audit_type: 'inspection', tags: ['instrument:audit'] },
        ],
      },
    })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('assessment-create-templates-empty')).toBeInTheDocument()
    expect(screen.getByText('workforce.assessments.templates_empty_link')).toHaveAttribute(
      'href',
      '/audit-templates/new?instrument=skills',
    )
    expect(screen.queryByText('Audit template')).not.toBeInTheDocument()
  })

  it('does not seed a wrong-purpose templateId', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 42, name: 'Audit template', audit_type: 'inspection', tags: ['instrument:audit'] },
          { id: 7, name: 'Skills template', audit_type: 'inspection', tags: ['instrument:skills'] },
        ],
      },
    })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter initialEntries={['/workforce/assessments/new?templateId=42']}>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    const select = await screen.findByLabelText(/workforce\.common\.template/i)
    await waitFor(() => expect(select).toHaveValue(''))
    expect(screen.getByTestId('assessment-create-template-wrong-purpose')).toBeInTheDocument()
    expect(select).not.toHaveValue('42')
  })

  it('shows template frequency and the existing training calendar link', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          {
            id: 42,
            name: 'Quarterly skills',
            audit_type: 'competency',
            tags: ['instrument:skills'],
            frequency: 'quarterly',
          },
        ],
      },
    })

    const AssessmentCreate = (await import('../AssessmentCreate')).default
    render(
      <MemoryRouter initialEntries={['/workforce/assessments/new?templateId=42']}>
        <AssessmentCreate />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('assessment-create-cadence')).toHaveTextContent(
      'workforce.assessments.cadence_frequency',
    )
    expect(screen.getByTestId('assessment-create-cadence-calendar')).toHaveAttribute(
      'href',
      '/calendar?types=training',
    )
  })
})
