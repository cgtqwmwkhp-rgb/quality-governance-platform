import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mockNavigate = vi.fn()
const {
  listEngineers,
  createEngineer,
  syncFromPams,
  linkEngineerUser,
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
    linkEngineerUser: vi.fn(),
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

vi.mock('../../../utils/workforceAccess', () => ({
  isWorkforceManager: vi.fn(() => true),
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listEngineers: (...args: unknown[]) => listEngineers(...args),
    createEngineer: (...args: unknown[]) => createEngineer(...args),
    syncFromPams: (...args: unknown[]) => syncFromPams(...args),
    linkEngineerUser: (...args: unknown[]) => linkEngineerUser(...args),
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

  it('guides managers through linking multiple selected unlinked employees', async () => {
    listEngineers.mockResolvedValue({
      data: {
        items: [
          { ...employee, id: 1, user_id: null, display_name: 'PAMS One' },
          { ...employee, id: 2, user_id: null, display_name: 'PAMS Two' },
        ],
      },
    })
    renderPage()

    fireEvent.click(await screen.findByLabelText('Select PAMS One for user linking'))
    fireEvent.click(screen.getByLabelText('Select PAMS Two for user linking'))
    fireEvent.click(screen.getByRole('button', { name: 'Link selected (2)' }))

    expect(screen.getByTestId('employee-bulk-link-dialog')).toBeInTheDocument()
    expect(screen.getAllByText('PAMS One')).toHaveLength(2)
    expect(screen.getAllByText('PAMS Two')).toHaveLength(2)
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

  it('filters roster by linked user status and shows active-link coverage', async () => {
    listEngineers.mockResolvedValue({
      data: {
        items: [],
        active_engineers: 8,
        linked_active_engineers: 6,
        linked_coverage_percent: 75,
      },
    })
    renderPage()

    expect(await screen.findByTestId('engineer-link-coverage')).toHaveTextContent('6/8 linked (75%)')
    fireEvent.change(screen.getByLabelText('Engineer link status'), { target: { value: 'unlinked' } })

    await waitFor(() => {
      expect(listEngineers).toHaveBeenCalledWith(
        expect.objectContaining({ link_status: 'unlinked', page: '1', page_size: '50' }),
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

  it('sorts the list view when column headers are clicked', async () => {
    listEngineers.mockResolvedValue({
      data: {
        items: [
          {
            ...employee,
            id: 1,
            display_name: 'Charlie',
            job_title: 'Welder',
            site: 'South',
            user_id: null,
          },
          {
            ...employee,
            id: 2,
            display_name: 'Alice',
            job_title: 'Technician',
            site: 'North',
            user_id: 10,
          },
          {
            ...employee,
            id: 3,
            display_name: 'Bob',
            job_title: 'Supervisor',
            site: 'East',
            user_id: null,
          },
        ],
      },
    })
    renderPage()

    await screen.findByText('Alice')
    fireEvent.click(screen.getByTestId('employees-view-mode-list'))

    const list = await screen.findByTestId('employees-view-list')
    const nameCells = () =>
      Array.from(list.querySelectorAll('tbody tr')).map(
        (row) => row.querySelector('td')?.textContent?.trim() ?? '',
      )

    expect(nameCells()).toEqual(['Alice', 'Bob', 'Charlie'])

    fireEvent.click(screen.getByTestId('employees-sort-name'))
    expect(nameCells()).toEqual(['Charlie', 'Bob', 'Alice'])
    expect(screen.getByTestId('employees-sort-name').closest('th')).toHaveAttribute(
      'aria-sort',
      'descending',
    )

    fireEvent.click(screen.getByTestId('employees-sort-site'))
    expect(nameCells()).toEqual(['Bob', 'Alice', 'Charlie'])
    expect(screen.getByTestId('employees-sort-site').closest('th')).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
  })
})
