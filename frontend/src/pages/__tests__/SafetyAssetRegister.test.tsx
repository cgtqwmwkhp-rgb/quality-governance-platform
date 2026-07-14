import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import SafetyAssetRegister from '../SafetyAssetRegister'

const mockListAssets = vi.fn()
const mockGetKpis = vi.fn()
const mockListAssetTypes = vi.fn()
const mockListLocations = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && 'defaultValue' in fallback) {
        return String(fallback.defaultValue)
      }
      if (fallback && typeof fallback === 'object' && 'count' in fallback) {
        return `${fallback.count} assets`
      }
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/safetyAssetsClient', () => ({
  EMPTY_SAFETY_ASSET_KPIS: {
    total: null,
    in_date: null,
    due_30: null,
    due_60: null,
    due_90: null,
    overdue: null,
    quarantined: null,
  },
  safetyAssetsApi: {
    listAssets: (...args: unknown[]) => mockListAssets(...args),
    getKpis: (...args: unknown[]) => mockGetKpis(...args),
    listAssetTypes: (...args: unknown[]) => mockListAssetTypes(...args),
    listLocations: (...args: unknown[]) => mockListLocations(...args),
  },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: () => 'Request failed',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('SafetyAssetRegister KPI honesty + list', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAssetTypes.mockResolvedValue({ data: { items: [], total: 0 } })
    mockListLocations.mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('renders em dashes for KPIs when fetch fails (no silent zeros)', async () => {
    mockListAssets.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 20, pages: 0 },
    })
    mockGetKpis.mockResolvedValue({
      total: null,
      in_date: null,
      due_30: null,
      due_60: null,
      due_90: null,
      overdue: null,
      quarantined: null,
    })

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-kpi-unavailable')).toBeInTheDocument()
    })

    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('—')
    expect(screen.getByTestId('safety-assets-kpi-overdue')).toHaveTextContent('—')
    expect(screen.getByTestId('safety-assets-kpi-quarantined')).toHaveTextContent('—')
    expect(screen.queryByTestId('safety-assets-kpi-total')).not.toHaveTextContent(/^0$/)
  })

  it('renders asset rows from list response', async () => {
    mockGetKpis.mockResolvedValue({
      total: 1,
      in_date: 1,
      due_30: 0,
      due_60: 0,
      due_90: 0,
      overdue: 0,
      quarantined: 0,
    })
    mockListAssetTypes.mockResolvedValue({
      data: {
        items: [{ id: 10, category: 'safety', name: 'Harness', is_active: true }],
        total: 1,
      },
    })
    mockListAssets.mockResolvedValue({
      data: {
        items: [
          {
            id: 55,
            external_id: 'ext-55',
            asset_type_id: 10,
            asset_number: 'SA-001',
            name: 'Fall harness A',
            status: 'active',
            vehicle_reg: 'AB12CDE',
            owner_user_id: 3,
            expiry_date: '2026-12-01T00:00:00Z',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        pages: 1,
      },
    })

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-table')).toBeInTheDocument()
    })

    expect(screen.getByTestId('safety-asset-row-55')).toBeInTheDocument()
    expect(screen.getByText('SA-001')).toBeInTheDocument()
    expect(screen.getByText('Fall harness A')).toBeInTheDocument()
    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('1')
    expect(screen.queryByTestId('safety-assets-kpi-unavailable')).not.toBeInTheDocument()
  })
})
