import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const mockListTemplates = vi.fn()
const mockContractsList = vi.fn()
const mockAuditList = vi.fn()

vi.mock('../../../api/formConfigClient', () => ({
  formConfigApi: {
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
  },
}))

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>('../../../api/client')
  return {
    ...actual,
    contractsApi: {
      list: (...args: unknown[]) => mockContractsList(...args),
    },
    auditTrailApi: {
      list: (...args: unknown[]) => mockAuditList(...args),
    },
  }
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  }
})

vi.mock('react-i18next', () => {
  const mockT = (_key: string, fallback?: string) => fallback ?? _key
  return {
    useTranslation: () => ({
      t: mockT,
    }),
    initReactI18next: { type: '3rdParty', init: () => {} },
  }
})

import AdminDashboard from '../AdminDashboard'

describe('AdminDashboard soft-fail honesty', () => {
  beforeEach(() => {
    mockListTemplates.mockReset()
    mockContractsList.mockReset()
    mockAuditList.mockReset()

    mockListTemplates.mockResolvedValue({ items: [], total: 3, page: 1, page_size: 1 })
    mockContractsList.mockResolvedValue({ items: [], total: 2 })
    mockAuditList.mockResolvedValue({ data: { items: [], total: 0, page: 1, per_page: 5 } })
  })

  it('renders partial dashboard when contracts API fails instead of crashing', async () => {
    mockContractsList.mockRejectedValue(new Error('503'))

    render(<AdminDashboard />)

    expect(await screen.findByTestId('admin-dashboard-unavailable')).toBeInTheDocument()
    expect(screen.getByText('Admin summary unavailable')).toBeInTheDocument()
    expect(screen.getByText('Active Forms')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    expect(screen.getByText('Quick Actions')).toBeInTheDocument()
  })
})
