import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import SafetyAssetDetail from '../SafetyAssetDetail'

const mockGetAsset = vi.fn()
const mockListAssetTypes = vi.fn()
const mockGetLocation = vi.fn()
const mockListRequirements = vi.fn()
const mockGetEngineerMatrix = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallback?: string | Record<string, unknown>,
      options?: Record<string, unknown>,
    ) => {
      if (typeof fallback === 'string') {
        return fallback.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
          String(options?.[name] ?? `{{${name}}}`),
        )
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    getAsset: (...args: unknown[]) => mockGetAsset(...args),
    listAssetTypes: (...args: unknown[]) => mockListAssetTypes(...args),
    getLocation: (...args: unknown[]) => mockGetLocation(...args),
    updateAsset: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  evidenceAssetsApi: { getSignedUrl: vi.fn(), upload: vi.fn() },
  getApiErrorMessage: () => 'Request failed',
  workforceApi: {
    competencyRequirements: {
      list: (...args: unknown[]) => mockListRequirements(...args),
    },
    analytics: {
      getEngineerMatrix: (...args: unknown[]) => mockGetEngineerMatrix(...args),
    },
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const asset = {
  id: 55,
  external_id: 'asset-55',
  asset_type_id: 10,
  asset_number: 'SA-001',
  name: 'Fall harness A',
  status: 'active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/safety-assets/55']}>
      <Routes>
        <Route path="/safety-assets/:id" element={<SafetyAssetDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SafetyAssetDetail competency panel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetAsset.mockResolvedValue({ data: asset })
    mockListAssetTypes.mockResolvedValue({
      data: { items: [{ id: 10, name: 'Harness', category: 'safety', is_active: true }] },
    })
    mockListRequirements.mockResolvedValue({ data: { items: [] } })
    mockGetEngineerMatrix.mockResolvedValue({ data: { asset_types: [], engineers: [] } })
  })

  it('shows type requirements and type-linked competency holders', async () => {
    mockListRequirements.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            asset_type_id: 10,
            template_id: 3,
            name: 'Harness inspection',
            is_mandatory: true,
            reassessment_interval_days: 365,
            tenant_id: 1,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
      },
    })
    mockGetEngineerMatrix.mockResolvedValue({
      data: {
        asset_types: [{ id: 10, name: 'Harness', category: 'safety' }],
        engineers: [
          { engineer_id: 7, user_id: 70, employee_number: 'E-007', competencies: { 10: 'active' } },
          {
            engineer_id: 8,
            user_id: 80,
            employee_number: 'E-008',
            competencies: { 10: 'expired' },
          },
        ],
      },
    })

    renderDetail()

    await waitFor(() => {
      expect(screen.getByTestId('safety-asset-competency')).toBeInTheDocument()
    })

    expect(screen.getByText('Harness inspection')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Requirements are linked to the asset type, not to this physical asset instance.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('This physical asset instance')).toBeInTheDocument()
    expect(screen.getByTestId('safety-asset-competency-holders')).toHaveTextContent('Engineer #7')
    expect(screen.queryByText('Engineer #8')).not.toBeInTheDocument()
    expect(mockListRequirements).toHaveBeenCalledWith({ asset_type_id: 10, page_size: 500 })
  })

  it('uses unavailable states instead of implying zero data', async () => {
    mockListRequirements.mockRejectedValue(new Error('requirements unavailable'))
    mockGetEngineerMatrix.mockRejectedValue(new Error('matrix unavailable'))

    renderDetail()

    await waitFor(() => {
      expect(
        screen.getByTestId('safety-asset-competency-requirements-unavailable'),
      ).toBeInTheDocument()
    })
    expect(screen.getByTestId('safety-asset-competency-holders-unavailable')).toBeInTheDocument()
  })
})
