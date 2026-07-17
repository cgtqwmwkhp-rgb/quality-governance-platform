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
    listTemplates.mockResolvedValue({ data: { items: [{ id: 1, name: 'Template A', audit_type: 'competency' }] } })
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
})
