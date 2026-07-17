import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mockNavigate = vi.fn()
const {
  listEngineers,
  createEngineer,
  syncFromPams,
  t,
} = vi.hoisted(() => {
  const t = (key: string, opts?: Record<string, unknown>) => {
    if (opts && typeof opts === 'object') {
      return `${key}:${JSON.stringify(opts)}`
    }
    return key
  }
  return {
    listEngineers: vi.fn(),
    createEngineer: vi.fn(),
    syncFromPams: vi.fn(),
    t,
  }
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listEngineers: (...args: unknown[]) => listEngineers(...args),
    createEngineer: (...args: unknown[]) => createEngineer(...args),
    syncFromPams: (...args: unknown[]) => syncFromPams(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'load failed',
}))

import Engineers from '../Engineers'

const employee = {
  id: 42,
  external_id: 'ext-42',
  display_name: 'Alex Technician',
  employee_number: 'E-042',
  job_title: 'Field Tech',
  department: 'Ops',
  site: 'North',
  is_active: true,
}

function renderPage() {
  return render(
    <MemoryRouter>
      <Engineers />
    </MemoryRouter>,
  )
}

describe('Engineers', () => {
  beforeEach(() => {
    listEngineers.mockResolvedValue({ data: { items: [] } })
    createEngineer.mockResolvedValue({ data: employee })
    syncFromPams.mockResolvedValue({
      data: { created: 1, updated: 0, deactivated: 0, skipped: 0, errors: 0 },
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows user link badges on roster cards (EMP-06)', async () => {
    listEngineers.mockResolvedValue({
      data: {
        items: [
          { ...employee, id: 1, user_id: 99 },
          { ...employee, id: 2, user_id: null, display_name: 'PAMS Only' },
        ],
      },
    })
    renderPage()

    expect(await screen.findByTestId('engineer-user-linked-1')).toHaveTextContent(
      'workforce.engineers.user_link.roster_linked:{"id":99}',
    )
    expect(screen.getByTestId('engineer-user-unlinked-2')).toHaveTextContent(
      'workforce.engineers.user_link.roster_unlinked',
    )
  })

  it('shows honest empty state with PAMS sync CTA when roster is empty', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('workforce.engineers.empty')).toBeInTheDocument()
    })
    expect(screen.getAllByText('workforce.engineers.sync_from_pams').length).toBeGreaterThan(0)
  })

  it('passes is_active filter to listEngineers', async () => {
    renderPage()

    await waitFor(() => expect(listEngineers).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('workforce.engineers.filter_status'), {
      target: { value: 'false' },
    })

    await waitFor(() => {
      expect(listEngineers).toHaveBeenCalledWith(
        expect.objectContaining({ is_active: 'false', page: '1', page_size: '50' }),
      )
    })
  })

  it('creates an employee from the dialog and navigates to profile', async () => {
    renderPage()

    await waitFor(() => expect(listEngineers).toHaveBeenCalled())

    fireEvent.click(screen.getByText('workforce.engineers.add'))
    fireEvent.change(screen.getByLabelText('workforce.engineers.display_name'), {
      target: { value: 'Alex Technician' },
    })
    fireEvent.click(screen.getAllByText('workforce.engineers.add')[1])

    await waitFor(() => {
      expect(createEngineer).toHaveBeenCalledWith(
        expect.objectContaining({ display_name: 'Alex Technician' }),
      )
      expect(mockNavigate).toHaveBeenCalledWith('/workforce/engineers/42')
    })
  })

  it('requires display name or user id before create', async () => {
    renderPage()

    await waitFor(() => expect(listEngineers).toHaveBeenCalled())

    fireEvent.click(screen.getByText('workforce.engineers.add'))
    fireEvent.click(screen.getAllByText('workforce.engineers.add')[1])

    await waitFor(() => {
      expect(screen.getByText('workforce.engineers.form_required')).toBeInTheDocument()
    })
    expect(createEngineer).not.toHaveBeenCalled()
  })
})
