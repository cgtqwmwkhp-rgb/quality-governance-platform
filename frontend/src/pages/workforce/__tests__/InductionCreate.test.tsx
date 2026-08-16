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
    createInduction: vi.fn(),
  },
  auditsApi: {
    listTemplates,
  },
  getApiErrorMessage: (err: unknown, fallback = 'Request failed') =>
    err instanceof Error ? err.message : fallback,
}))

describe('InductionCreate employee picker (EMP-07)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTemplates.mockResolvedValue({
      data: {
        items: [{ id: 1, name: 'Induction A', audit_type: 'induction', tags: ['instrument:induction'] }],
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

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter>
        <InductionCreate />
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

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter>
        <InductionCreate />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('induction-create-employees-empty')).toBeInTheDocument(),
    )
  })

  it('does not present a failed roster request as an empty roster', async () => {
    listEngineers.mockRejectedValue(new Error('Engineers unavailable'))

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter>
        <InductionCreate />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('induction-create-employees-unavailable')).toHaveTextContent(
      /could not be loaded/i,
    )
    expect(screen.queryByTestId('induction-create-employees-empty')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/workforce\.common\.engineer/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /workforce\.induction\.create_start/i })).toBeDisabled()
  })

  it('seeds the template select from ?templateId=', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 1, name: 'Induction A', audit_type: 'induction', tags: ['instrument:induction'] },
          {
            id: 42,
            name: 'Seeded induction template',
            audit_type: 'inspection',
            tags: ['instrument:induction'],
          },
        ],
      },
    })

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter initialEntries={['/workforce/training/new?templateId=42']}>
        <InductionCreate />
      </MemoryRouter>,
    )

    const select = await screen.findByLabelText(/workforce\.common\.template/i)
    await waitFor(() => expect(select).toHaveValue('42'))
  })

  it('hides published templates that are not induction instruments', async () => {
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

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter>
        <InductionCreate />
      </MemoryRouter>,
    )

    const select = await screen.findByLabelText(/workforce\.common\.template/i)
    expect(select).toHaveTextContent('Induction template')
    expect(select).not.toHaveTextContent('Audit template')
    expect(select).not.toHaveTextContent('Skills template')
    expect(select).not.toHaveTextContent('Untagged template')
  })

  it('shows an author-induction empty state when no induction templates exist', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 1, name: 'Skills template', audit_type: 'inspection', tags: ['instrument:skills'] },
        ],
      },
    })

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter>
        <InductionCreate />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('induction-create-templates-empty')).toBeInTheDocument()
    expect(screen.getByText('workforce.induction.templates_empty_link')).toHaveAttribute(
      'href',
      '/audit-templates/new?instrument=induction',
    )
    expect(screen.queryByText(/Skills template/)).not.toBeInTheDocument()
  })

  it('does not seed a wrong-purpose templateId', async () => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    listTemplates.mockResolvedValue({
      data: {
        items: [
          { id: 42, name: 'Skills template', audit_type: 'inspection', tags: ['instrument:skills'] },
          {
            id: 7,
            name: 'Induction template',
            audit_type: 'inspection',
            tags: ['instrument:induction'],
          },
        ],
      },
    })

    const InductionCreate = (await import('../InductionCreate')).default
    render(
      <MemoryRouter initialEntries={['/workforce/training/new?templateId=42']}>
        <InductionCreate />
      </MemoryRouter>,
    )

    const select = await screen.findByLabelText(/workforce\.common\.template/i)
    await waitFor(() => expect(select).toHaveValue(''))
    expect(screen.getByTestId('induction-create-template-wrong-purpose')).toBeInTheDocument()
    expect(select).not.toHaveValue('42')
  })
})
