import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import SafetyAssetRegister from '../SafetyAssetRegister'

const mockListAllAssetsForBoard = vi.fn()
const mockListAssetTypes = vi.fn()
const mockListLocations = vi.fn()
const mockListEngineers = vi.fn()
const mockCesImportDryRun = vi.fn()
const mockCesImportCommit = vi.fn()

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
    listAllAssetsForBoard: (...args: unknown[]) => mockListAllAssetsForBoard(...args),
    listAssetTypes: (...args: unknown[]) => mockListAssetTypes(...args),
    listLocations: (...args: unknown[]) => mockListLocations(...args),
    cesImportDryRun: (...args: unknown[]) => mockCesImportDryRun(...args),
    cesImportCommit: (...args: unknown[]) => mockCesImportCommit(...args),
  },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: () => 'Request failed',
  workforceApi: {
    listEngineers: (...args: unknown[]) => mockListEngineers(...args),
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('SafetyAssetRegister Wave 2 board', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    mockListAssetTypes.mockResolvedValue({ data: { items: [], total: 0 } })
    mockListLocations.mockResolvedValue({ data: { items: [], total: 0 } })
    mockListEngineers.mockResolvedValue({ data: { items: [] } })
  })

  it('renders em dashes for KPIs when load fails (no silent zeros)', async () => {
    mockListAllAssetsForBoard.mockRejectedValue(new Error('boom'))

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
  })

  it('renders asset rows and engineer rollup drill-in', async () => {
    mockListAssetTypes.mockResolvedValue({
      data: {
        items: [{ id: 10, category: 'safety', name: 'Harness', is_active: true }],
        total: 1,
      },
    })
    mockListEngineers.mockResolvedValue({
      data: { items: [{ id: 1, user_id: 3, display_name: 'Alex Owner', is_active: true }] },
    })
    mockListAllAssetsForBoard.mockResolvedValue([
      {
        id: 55,
        external_id: 'ext-55',
        asset_type_id: 10,
        asset_number: 'SA-001',
        name: 'Fall harness A',
        status: 'active',
        serial_number: 'SN-55',
        vehicle_reg: 'AB12CDE',
        owner_user_id: 3,
        expiry_date: '2026-12-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-table')).toBeInTheDocument()
    })

    expect(screen.getByTestId('safety-asset-row-55')).toBeInTheDocument()
    expect(screen.getByText('SN-55')).toBeInTheDocument()
    expect(screen.getByText('Fall harness A')).toBeInTheDocument()
    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('1')
    expect(screen.queryByTestId('safety-assets-kpi-unavailable')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('safety-assets-view-engineer'))
    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-engineer-table')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('safety-assets-rollup-user:3'))
    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-drilldown-sheet')).toBeInTheDocument()
    })
    expect(screen.getByTestId('safety-assets-sheet-row-55')).toBeInTheDocument()
  })

  it('keeps removed assets hidden when the Removed band is selected', async () => {
    mockListAllAssetsForBoard.mockResolvedValue([
      {
        id: 55,
        external_id: 'ext-55',
        asset_type_id: 10,
        asset_number: 'SA-001',
        name: 'Active harness',
        status: 'active',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 56,
        external_id: 'ext-56',
        asset_type_id: 10,
        asset_number: 'SA-002',
        name: 'Removed harness',
        status: 'decommissioned',
        expiry_date: '2025-01-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await screen.findByTestId('safety-assets-table')
    expect(screen.getByTestId('safety-assets-hide-removed')).toBeChecked()
    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('1')
    expect(screen.getByTestId('safety-assets-kpi-decommissioned')).toHaveTextContent('1')
    expect(screen.queryByTestId('safety-asset-row-56')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('safety-assets-kpi-decommissioned'))
    expect(screen.getByTestId('safety-assets-kpi-total')).toHaveTextContent('1')
    expect(screen.queryByTestId('safety-asset-row-56')).not.toBeInTheDocument()
    expect(screen.queryByTestId('safety-asset-row-55')).not.toBeInTheDocument()
  })

  it('shows CES upload panel on upload view', async () => {
    mockListAllAssetsForBoard.mockResolvedValue([])

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('safety-assets-view-upload')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('safety-assets-view-upload'))
    expect(screen.getByTestId('ces-import-panel')).toBeInTheDocument()
  })

  it('gates CES commit until similar lookups are confirmed', async () => {
    mockListAllAssetsForBoard.mockResolvedValue([])
    mockCesImportDryRun.mockResolvedValue({
      data: {
        ok: true,
        mode: 'dry_run',
        total_rows: 2,
        valid_rows: 2,
        error_rows: 0,
        warning_rows: 1,
        creates: 2,
        updates: 0,
        skipped: 0,
        // Dry-run: similar lookups block can_commit until UI confirms.
        can_commit: false,
        requires_confirmation: true,
        errors: [],
        warnings: [],
        lookup_proposals: [
          {
            kind: 'asset_type',
            name: 'D Shackel',
            intent: 'similar',
            needs_confirmation: true,
            row_count: 2,
            similar_matches: [{ id: 7, name: 'D Shackle', score: 0.92 }],
          },
          {
            kind: 'location',
            name: 'New Depot',
            intent: 'new',
            needs_confirmation: false,
            row_count: 2,
            similar_matches: [],
          },
        ],
      },
    })
    mockCesImportCommit.mockResolvedValue({
      data: {
        report: {
          ok: true,
          mode: 'commit',
          valid_rows: 2,
          error_rows: 0,
          creates: 2,
          updates: 0,
          lookup_proposals: [],
          errors: [],
          warnings: [],
        },
        provisional_type_ids: [],
        provisional_location_ids: [99],
      },
    })

    render(
      <MemoryRouter>
        <SafetyAssetRegister />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByTestId('safety-assets-view-upload'))
    const fileInput = screen.getByLabelText('CES workbook')
    const file = new File(['xlsx'], 'ces.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    fireEvent.change(fileInput, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Dry run' }))

    await waitFor(() => {
      expect(screen.getByTestId('ces-import-similar-lookups')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ces-import-new-lookups')).toBeInTheDocument()
    expect(screen.getByTestId('ces-import-commit')).toBeDisabled()

    fireEvent.click(screen.getByLabelText('Use existing “D Shackle”'))
    expect(screen.getByTestId('ces-import-commit')).not.toBeDisabled()

    fireEvent.click(screen.getByTestId('ces-import-commit'))
    await waitFor(() => {
      expect(mockCesImportCommit).toHaveBeenCalledWith(
        file,
        expect.arrayContaining([
          expect.objectContaining({
            kind: 'asset_type',
            name: 'D Shackel',
            action: 'reuse',
            reuse_id: 7,
          }),
        ]),
      )
    })
  })
})
