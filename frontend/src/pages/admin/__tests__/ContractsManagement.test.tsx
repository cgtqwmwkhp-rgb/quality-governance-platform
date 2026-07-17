import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockList = vi.fn()
const mockCreate = vi.fn()
const mockUpdate = vi.fn()
const mockDelete = vi.fn()
const mockToastError = vi.fn()

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>('../../../api/client')
  return {
    ...actual,
    contractsApi: {
      list: (...args: unknown[]) => mockList(...args),
      create: (...args: unknown[]) => mockCreate(...args),
      update: (...args: unknown[]) => mockUpdate(...args),
      delete: (...args: unknown[]) => mockDelete(...args),
    },
  }
})

vi.mock('../../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: vi.fn(),
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

import ContractsManagement from '../ContractsManagement'

const sampleContract = {
  id: 1,
  name: 'UKPN',
  code: 'ukpn',
  is_active: true,
  display_order: 1,
}

describe('ContractsManagement admin honesty', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockCreate.mockReset()
    mockUpdate.mockReset()
    mockDelete.mockReset()
    mockToastError.mockReset()
    mockList.mockResolvedValue({ items: [sampleContract], total: 1 })
  })

  it('shows inline unavailable state on 503 without toast spam', async () => {
    mockList.mockRejectedValue({
      isAxiosError: true,
      response: { status: 503, data: { detail: 'Unable to list contracts at this time.' } },
      message: 'Request failed with status code 503',
    })

    render(<ContractsManagement />)

    expect(await screen.findByTestId('contracts-list-unavailable')).toBeInTheDocument()
    expect(screen.getByText('Contracts unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('contracts-list-unavailable-retry')).toBeInTheDocument()
    expect(mockToastError).not.toHaveBeenCalled()
  })

  it('retries load from inline banner', async () => {
    mockList.mockRejectedValueOnce(new Error('timeout'))
    mockList.mockResolvedValueOnce({ items: [sampleContract], total: 1 })

    const user = userEvent.setup()
    render(<ContractsManagement />)

    await screen.findByTestId('contracts-list-unavailable')
    await user.click(screen.getByTestId('contracts-list-unavailable-retry'))

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByText('UKPN')).toBeInTheDocument()
  })

  it('loads contracts from admin config API', async () => {
    render(<ContractsManagement />)

    expect(await screen.findByText('UKPN')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(true)
  })
})
