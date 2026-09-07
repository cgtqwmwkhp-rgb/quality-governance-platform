import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompetenceBindListResponse } from '../../../api/competenceBindClient'

const list = vi.fn()
const create = vi.fn()
const remove = vi.fn()
const listTemplates = vi.fn()
const toastError = vi.fn()
const toastSuccess = vi.fn()

vi.mock('../../../api/client', () => ({
  competenceBindApi: {
    list: () => list(),
    create: (payload: unknown) => create(payload),
    remove: (bindId: number) => remove(bindId),
  },
  auditsApi: {
    listTemplates: (page: number, size: number, filters: unknown) =>
      listTemplates(page, size, filters),
  },
  getApiErrorMessage: (error: unknown, fallback?: string) => {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    return detail ?? fallback ?? 'API failed'
  },
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: {
    error: (message: string) => toastError(message),
    success: (message: string) => toastSuccess(message),
  },
}))

function httpError(status: number, detail?: string) {
  return { response: { status, data: detail ? { detail } : {} } }
}

const TEMPLATES = {
  data: {
    items: [
      { id: 8, name: 'FLT field assessment', tags: ['instrument:skills'], is_published: true },
      { id: 12, name: 'FLT induction', tags: ['instrument:induction'], is_published: true },
    ],
  },
}

const BINDS: CompetenceBindListResponse = {
  items: [
    {
      id: 1,
      template_id: 8,
      characteristic_key: 'COUNTERBALANCE_FLT',
      mode: 'field',
      interval_days: 365,
      created_at: '2026-09-03T09:00:00Z',
    },
  ],
  characteristics: [
    { key: 'COUNTERBALANCE_FLT', label: 'COUNTERBALANCE_FLT' },
    { key: 'MEWP_3A', label: 'MEWP_3A' },
  ],
  banner: null,
}

async function renderPage() {
  const CompetenceBinds = (await import('../CompetenceBinds')).default
  await act(async () => {
    render(
      <MemoryRouter>
        <CompetenceBinds />
      </MemoryRouter>,
    )
  })
}

describe('CompetenceBinds', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    list.mockResolvedValue({ data: BINDS })
    listTemplates.mockResolvedValue(TEMPLATES)
    create.mockResolvedValue({ data: {} })
    remove.mockResolvedValue({ data: undefined })
  })

  it('lists an unbound characteristic rather than hiding it, and does not paint it as a failure', async () => {
    await renderPage()

    await screen.findByTestId('competence-binds-table')
    expect(screen.getByTestId('bind-row-MEWP_3A')).toBeInTheDocument()

    const cell = screen.getByTestId('bind-cell-MEWP_3A-field')
    expect(cell).toHaveAttribute('data-cell-state', 'unbound')
    expect(cell.className).not.toContain('bg-destructive')
    expect(cell.className).not.toContain('bg-muted-foreground')
    expect(cell).toHaveTextContent('Not bound')
  })

  it('shows the bound template and its interval on the field column only', async () => {
    await renderPage()

    const field = await screen.findByTestId('bind-cell-COUNTERBALANCE_FLT-field')
    expect(field).toHaveAttribute('data-cell-state', 'bound')
    expect(field).toHaveTextContent('FLT field assessment')
    expect(field).toHaveTextContent('reassess every 365 days')

    const induction = screen.getByTestId('bind-cell-COUNTERBALANCE_FLT-induction')
    expect(induction).toHaveAttribute('data-cell-state', 'unbound')
  })

  it('only offers published templates to the picker', async () => {
    await renderPage()

    await screen.findByTestId('competence-binds-table')
    expect(listTemplates).toHaveBeenCalledWith(1, 200, { is_published: true })
  })

  it('posts the characteristic, template, mode and interval and reloads', async () => {
    const user = userEvent.setup()
    await renderPage()
    await screen.findByTestId('competence-binds-table')

    await user.selectOptions(screen.getByLabelText('PAMS characteristic'), 'MEWP_3A')
    await user.selectOptions(screen.getByLabelText('Published template'), '12')
    await user.selectOptions(screen.getByLabelText('Mode'), 'induction')
    await user.type(screen.getByLabelText('Reassessment interval (days)'), '730')
    await user.click(screen.getByTestId('competence-binds-submit'))

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith({
        template_id: 12,
        characteristic_key: 'MEWP_3A',
        mode: 'induction',
        interval_days: 730,
      }),
    )
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('sends a blank interval as null rather than inventing one', async () => {
    const user = userEvent.setup()
    await renderPage()
    await screen.findByTestId('competence-binds-table')

    await user.selectOptions(screen.getByLabelText('PAMS characteristic'), 'MEWP_3A')
    await user.selectOptions(screen.getByLabelText('Published template'), '12')
    await user.click(screen.getByTestId('competence-binds-submit'))

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ interval_days: null, mode: 'field' }),
      ),
    )
  })

  it("shows the server's own refusal when the 1:1 rule rejects a second template", async () => {
    const user = userEvent.setup()
    create.mockRejectedValue(
      httpError(409, 'This PAMS characteristic already has a different template bound for that mode.'),
    )
    await renderPage()
    await screen.findByTestId('competence-binds-table')

    await user.selectOptions(screen.getByLabelText('PAMS characteristic'), 'COUNTERBALANCE_FLT')
    await user.selectOptions(screen.getByLabelText('Published template'), '12')
    await user.click(screen.getByTestId('competence-binds-submit'))

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        'This PAMS characteristic already has a different template bound for that mode.',
      ),
    )
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('removes a bind and reloads so the column returns to unbound', async () => {
    const user = userEvent.setup()
    list
      .mockResolvedValueOnce({ data: BINDS })
      .mockResolvedValueOnce({ data: { ...BINDS, items: [] } })
    await renderPage()
    await screen.findByTestId('competence-binds-table')

    await user.click(screen.getByTestId('bind-remove-COUNTERBALANCE_FLT-field'))

    await waitFor(() => expect(remove).toHaveBeenCalledWith(1))
    await waitFor(() =>
      expect(screen.getByTestId('bind-cell-COUNTERBALANCE_FLT-field')).toHaveAttribute(
        'data-cell-state',
        'unbound',
      ),
    )
    // The characteristic is still on the page after its bind is gone.
    expect(screen.getByTestId('bind-row-COUNTERBALANCE_FLT')).toBeInTheDocument()
  })

  it("says the board is not enabled in the server's own words on a 404", async () => {
    list.mockRejectedValue(httpError(404, 'Competence board is not enabled in this environment.'))
    await renderPage()

    const notice = await screen.findByTestId('competence-binds-unavailable')
    expect(notice).toHaveTextContent('Competence board is not enabled in this environment.')
    expect(screen.queryByTestId('competence-binds-table')).not.toBeInTheDocument()
    expect(screen.queryByTestId('competence-binds-retry')).not.toBeInTheDocument()
  })

  it('offers a retry on a non-404 failure and clears the notice when it succeeds', async () => {
    const user = userEvent.setup()
    list.mockRejectedValueOnce(httpError(500)).mockResolvedValueOnce({ data: BINDS })
    await renderPage()

    await screen.findByTestId('competence-binds-error')
    await user.click(screen.getByTestId('competence-binds-retry'))

    await screen.findByTestId('competence-binds-table')
    expect(screen.queryByTestId('competence-binds-error')).not.toBeInTheDocument()
  })

  it('reports an absent snapshot as absent, not as zero characteristics bound', async () => {
    list.mockResolvedValue({
      data: {
        items: [],
        characteristics: [],
        banner: 'No PAMS competence snapshot yet, so there is no characteristic to bind against.',
      },
    })
    await renderPage()

    expect(await screen.findByTestId('competence-binds-empty')).toBeInTheDocument()
    expect(screen.getByTestId('competence-binds-banner')).toHaveTextContent(
      'No PAMS competence snapshot yet',
    )
    expect(screen.getByTestId('competence-binds-submit')).toBeDisabled()
  })

  it('keeps a bind whose characteristic has left the snapshot visible and removable', async () => {
    list.mockResolvedValue({
      data: {
        ...BINDS,
        items: [{ ...BINDS.items[0], characteristic_key: 'RETIRED_RIG' }],
      },
    })
    await renderPage()

    const row = await screen.findByTestId('bind-row-RETIRED_RIG')
    expect(within(row).getByTestId('bind-orphan-RETIRED_RIG')).toBeInTheDocument()
    expect(screen.getByTestId('bind-remove-RETIRED_RIG-field')).toBeInTheDocument()
  })

  it('degrades a malformed 200 to the empty panel rather than throwing', async () => {
    list.mockResolvedValue({ data: { items: null, characteristics: null } })
    await renderPage()

    expect(await screen.findByTestId('competence-binds-empty')).toBeInTheDocument()
  })

  it('says so when published templates cannot be loaded instead of offering an empty picker', async () => {
    listTemplates.mockRejectedValue(httpError(500))
    await renderPage()

    expect(await screen.findByTestId('competence-binds-templates-failed')).toBeInTheDocument()
  })

  it('issues no request that could write PAMS', async () => {
    await renderPage()
    await screen.findByTestId('competence-binds-table')

    expect(list).toHaveBeenCalled()
    expect(create).not.toHaveBeenCalled()
    expect(remove).not.toHaveBeenCalled()
  })
})
