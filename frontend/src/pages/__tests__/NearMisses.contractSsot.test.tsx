/**
 * Near Miss contract SSOT — create form uses the Admin Customers lookup +
 * contracts bridge (same pattern as Complaints/Incidents) and resolves
 * contract_id on submit, mirroring `tests/pages/__tests__/Complaints.test.tsx`.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import NearMisses from '../NearMisses'

const mockNavigate = vi.fn()
const mockToastSuccess = vi.fn()
const mockT = (key: string, fallback?: string) => fallback ?? key

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: (...args: unknown[]) => mockToastSuccess(...args), error: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

const mockList = vi.fn()
const mockCreate = vi.fn()
const mockLookupsList = vi.fn()
const mockContractsList = vi.fn()

vi.mock('../../api/client', () => ({
  nearMissesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
  lookupsApi: {
    list: (...args: unknown[]) => mockLookupsList(...args),
  },
  contractsApi: {
    list: (...args: unknown[]) => mockContractsList(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../components/FuzzySearchDropdown', () => ({
  default: ({
    value,
    onChange,
    label,
    placeholder,
  }: {
    value: string
    onChange: (v: string) => void
    label?: string
    placeholder?: string
  }) => (
    <label>
      {label}
      <input
        data-testid={`fuzzy-${placeholder || label || 'search'}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  ),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

describe('NearMisses contract SSOT create form', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 50 } })
    mockLookupsList.mockImplementation(async (category: string) => {
      if (category === 'customers') {
        return {
          items: [{ id: 1, category: 'customers', code: 'ukpn', label: 'UK Power Networks', is_active: true }],
          total: 1,
        }
      }
      return { items: [], total: 0 }
    })
    mockContractsList.mockResolvedValue({
      items: [{ id: 42, code: 'ukpn', name: 'UK Power Networks', is_active: true, display_order: 1 }],
      total: 1,
    })
    mockCreate.mockResolvedValue({
      data: {
        id: 9,
        reference_number: 'NM-00009',
        reporter_name: 'Alex',
        contract_id: 42,
        contract: 'ukpn',
        location: 'Yard',
        event_date: new Date().toISOString(),
        description: 'A pallet nearly fell over.',
        was_involved: true,
        witnesses_present: false,
        status: 'REPORTED',
        priority: 'MEDIUM',
      },
    })
  })

  async function openDialogAndWait() {
    render(<NearMisses />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.queryByText('near_misses.empty.title')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'near_misses.new' }))
    await waitFor(() => expect(mockContractsList).toHaveBeenCalledWith(true))
  }

  it('resolves contract_id from the selected customer on create', async () => {
    await openDialogAndWait()

    fireEvent.change(screen.getByLabelText('Reporter name'), { target: { value: 'Alex' } })
    fireEvent.change(screen.getByTestId('fuzzy-Search customer…'), {
      target: { value: 'ukpn' },
    })
    fireEvent.change(screen.getByLabelText('common.location'), { target: { value: 'Yard' } })
    fireEvent.change(screen.getByLabelText('common.description'), {
      target: { value: 'A pallet nearly fell over.' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'near_misses.create' }))

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
    const payload = mockCreate.mock.calls[0][0]
    expect(payload.contract_id).toBe(42)
    expect(payload.contract).toBe('ukpn')
    expect(mockToastSuccess).toHaveBeenCalled()
  })

  it('blocks create when no customer is selected', async () => {
    await openDialogAndWait()

    fireEvent.change(screen.getByLabelText('Reporter name'), { target: { value: 'Alex' } })
    fireEvent.change(screen.getByLabelText('common.location'), { target: { value: 'Yard' } })
    fireEvent.change(screen.getByLabelText('common.description'), {
      target: { value: 'A pallet nearly fell over.' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'near_misses.create' }))

    await waitFor(() =>
      expect(
        screen.getByText('Select which customer this near miss is from.'),
      ).toBeInTheDocument(),
    )
    expect(mockCreate).not.toHaveBeenCalled()
  })
})
