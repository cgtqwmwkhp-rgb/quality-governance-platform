import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'

const mockList = vi.fn()
const mockCreate = vi.fn()
const mockDelete = vi.fn()
const mockListPendingSafetyLookups = vi.fn()
const mockApproveSafetyLookup = vi.fn()
const mockMergeSafetyLookup = vi.fn()
const mockRejectSafetyLookup = vi.fn()
const mockListAssetTypes = vi.fn()
const mockListLocations = vi.fn()

vi.mock('../../../api/client', () => ({
  lookupsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
  getApiErrorMessage: (err: unknown, fallback?: string) =>
    err instanceof Error ? err.message : fallback || 'error',
}))

const mockCreateLocation = vi.fn()
const mockCreateAssetType = vi.fn()
const mockPreviewSafetyLookup = vi.fn()

vi.mock('../../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listPendingSafetyLookups: (...args: unknown[]) => mockListPendingSafetyLookups(...args),
    approveSafetyLookup: (...args: unknown[]) => mockApproveSafetyLookup(...args),
    mergeSafetyLookup: (...args: unknown[]) => mockMergeSafetyLookup(...args),
    rejectSafetyLookup: (...args: unknown[]) => mockRejectSafetyLookup(...args),
    listAssetTypes: (...args: unknown[]) => mockListAssetTypes(...args),
    listLocations: (...args: unknown[]) => mockListLocations(...args),
    listAllAssetTypes: async () => {
      const res = await mockListAssetTypes({ page: 1, page_size: 500 })
      return { items: res.data.items ?? [], total: res.data.total ?? 0 }
    },
    previewSafetyLookup: (...args: unknown[]) => mockPreviewSafetyLookup(...args),
    createAssetType: (...args: unknown[]) => mockCreateAssetType(...args),
    createLocation: (...args: unknown[]) => mockCreateLocation(...args),
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) =>
      typeof fallback === 'string' ? fallback : key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import LookupTables from '../LookupTables'

function renderLookups(ui: ReactElement, initialEntry = '/admin/lookups') {
  return render(<MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>)
}

describe('LookupTables configure CTA', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockCreate.mockReset()
    mockDelete.mockReset()
    mockListPendingSafetyLookups.mockReset()
    mockApproveSafetyLookup.mockReset()
    mockMergeSafetyLookup.mockReset()
    mockRejectSafetyLookup.mockReset()
    mockListLocations.mockReset()
    mockCreateLocation.mockReset()
    mockCreateAssetType.mockReset()
    mockPreviewSafetyLookup.mockReset()
    mockListPendingSafetyLookups.mockResolvedValue({ data: { items: [], total: 0 } })
    mockRejectSafetyLookup.mockResolvedValue({ data: { approval_status: 'rejected' } })
    mockListLocations.mockResolvedValue({ data: { items: [], total: 0 } })
    mockPreviewSafetyLookup.mockResolvedValue({
      data: { intent: 'create', similar_matches: [], blocked_exact_duplicate: false },
    })
    mockCreateLocation.mockResolvedValue({ data: { id: 1 } })
    mockList.mockImplementation(async (category: string) => {
      if (
        category === 'workforce_roles' ||
        category === 'customers' ||
        category === 'medical_assistance'
      ) {
        return { items: [], total: 0 }
      }
      return {
        items: [{ id: 1, category, code: 'a', label: 'A', is_active: true, display_order: 0 }],
        total: 1,
      }
    })
    mockListAssetTypes.mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('shows Not configured honesty and primary Configure CTA for empty categories', async () => {
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-count-medical_assistance')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-empty-medical_assistance')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-configure-medical_assistance')).toHaveTextContent('Configure')
  })

  it('opens editor from Configure CTA and loads real options', async () => {
    const user = userEvent.setup()
    renderLookups(<LookupTables />)

    await screen.findByTestId('lookup-configure-incident_types')
    await user.click(screen.getByTestId('lookup-configure-incident_types'))

    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('incident_types', false)
    })
    expect(await screen.findByTestId('lookup-editor-list')).toHaveTextContent('A')
  })

  it('does not fabricate zero when list fails', async () => {
    mockList.mockRejectedValue(new Error('network'))
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-count-medical_assistance')).toHaveTextContent(
      'Count unavailable',
    )
    expect(screen.queryByTestId('lookup-empty-departments')).not.toBeInTheDocument()
  })

  it('shows workforce_roles catalog card with documented code hints', async () => {
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-card-workforce_roles')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-count-workforce_roles')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-workforce-roles-hints')).toHaveTextContent(
      'engineer, field_engineer, supervisor, process_scheduler',
    )
  })

  it('shows customers catalog card with documented code hints', async () => {
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-card-customers')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-count-customers')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-customers-hints')).toHaveTextContent('ukpn, openreach')
  })

  it('exposes asset types and medical assistance categories on the hub', async () => {
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-card-assets')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('lookup-count-assets')).toHaveTextContent('Not configured')
    })
    expect(screen.getByTestId('lookup-card-medical_assistance')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-hub-category-filter')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockListAssetTypes).toHaveBeenCalled()
    })
  })

  it('opens workforce_roles editor and shows standard code hints when empty', async () => {
    const user = userEvent.setup()
    renderLookups(<LookupTables />)

    await screen.findByTestId('lookup-configure-workforce_roles')
    await user.click(screen.getByTestId('lookup-configure-workforce_roles'))

    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('workforce_roles', false)
    })
    expect(screen.getByTestId('lookup-editor-workforce-role-hints')).toHaveTextContent(
      'field_engineer',
    )
    expect(screen.getByTestId('lookup-editor-workforce-role-hints')).toHaveTextContent(
      'process_scheduler',
    )
  })

  it('opens customers editor and shows suggested customer codes when empty', async () => {
    const user = userEvent.setup()
    renderLookups(<LookupTables />)

    await screen.findByTestId('lookup-configure-customers')
    await user.click(screen.getByTestId('lookup-configure-customers'))

    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('customers', false)
    })
    expect(screen.getByTestId('lookup-editor-customer-hints')).toHaveTextContent('ukpn')
    expect(screen.getByTestId('lookup-editor-customer-hints')).toHaveTextContent('openreach')
  })

  it('adds an option from name only and auto-generates the system code', async () => {
    const user = userEvent.setup()
    mockCreate.mockResolvedValue({
      id: 9,
      category: 'medical_assistance',
      code: 'oxford_depot',
      label: 'Oxford Depot',
      is_active: true,
      display_order: 0,
    })
    renderLookups(<LookupTables />)

    await user.click(await screen.findByTestId('lookup-configure-medical_assistance'))
    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()

    await user.type(screen.getByTestId('lookup-new-label'), 'Oxford Depot')
    expect(screen.getByTestId('lookup-code-preview')).toHaveTextContent('oxford_depot')
    expect(screen.queryByTestId('lookup-new-code')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('lookup-add-option'))
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        'medical_assistance',
        expect.objectContaining({
          category: 'medical_assistance',
          code: 'oxford_depot',
          label: 'Oxford Depot',
        }),
      )
    })
  })

  it('allows overriding the auto-generated code via advanced reveal', async () => {
    const user = userEvent.setup()
    mockCreate.mockResolvedValue({
      id: 10,
      category: 'medical_assistance',
      code: 'ox5',
      label: 'Oxford Depot',
      is_active: true,
      display_order: 0,
    })
    renderLookups(<LookupTables />)

    await user.click(await screen.findByTestId('lookup-configure-medical_assistance'))
    await screen.findByTestId('lookup-editor-dialog')
    await user.type(screen.getByTestId('lookup-new-label'), 'Oxford Depot')
    await user.click(screen.getByTestId('lookup-advanced-code-toggle'))
    const codeInput = await screen.findByTestId('lookup-new-code')
    await user.clear(codeInput)
    await user.type(codeInput, 'ox5')
    await user.click(screen.getByTestId('lookup-add-option'))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        'medical_assistance',
        expect.objectContaining({ code: 'ox5', label: 'Oxford Depot' }),
      )
    })
  })

  it('shows Safety pending queue and approves provisional lookups', async () => {
    const user = userEvent.setup()
    mockListPendingSafetyLookups.mockResolvedValue({
      data: {
        items: [
          {
            kind: 'asset_type',
            id: 42,
            name: 'D Shackel',
            source: 'ces_import',
            similar_matches: [{ id: 7, name: 'D Shackle', score: 0.92 }],
          },
        ],
        total: 1,
      },
    })
    mockApproveSafetyLookup.mockResolvedValue({ data: { ok: true } })

    renderLookups(<LookupTables />, '/admin/lookups?pending=safety')

    expect(await screen.findByTestId('safety-pending-asset_type-42')).toBeInTheDocument()
    expect(screen.getByTestId('safety-lookup-pending-panel')).toBeInTheDocument()
    await user.click(screen.getByTestId('safety-pending-approve-asset_type-42'))
    await waitFor(() => {
      expect(mockApproveSafetyLookup).toHaveBeenCalledWith('asset_type', 42)
    })
  })

  it('exposes Reject for pending Safety lookups (PX-196)', async () => {
    const user = userEvent.setup()
    mockListPendingSafetyLookups.mockResolvedValue({
      data: {
        items: [
          {
            kind: 'location',
            id: 8,
            name: 'SPARE',
            source: 'ces_import',
            is_active: false,
            approval_status: 'pending',
            similar_matches: [],
          },
        ],
        total: 1,
      },
    })

    renderLookups(<LookupTables />, '/admin/lookups?pending=safety')

    expect(await screen.findByTestId('safety-pending-reject-location-8')).toBeInTheDocument()
    await user.click(screen.getByTestId('safety-pending-reject-location-8'))
    await waitFor(() => {
      expect(mockRejectSafetyLookup).toHaveBeenCalledWith('location', 8)
    })
  })

  it('exposes Merge into… when similar_matches is empty and merges into chosen target', async () => {
    const user = userEvent.setup()
    mockListPendingSafetyLookups.mockResolvedValue({
      data: {
        items: [
          {
            kind: 'location',
            id: 9,
            name: 'Unspecified site (9)',
            source: 'ces_import',
            is_active: false,
            approval_status: 'pending',
            similar_matches: [],
          },
        ],
        total: 1,
      },
    })
    mockListLocations.mockResolvedValue({
      data: {
        items: [
          { id: 9, name: 'Unspecified site (9)', kind: 'site', is_active: false },
          { id: 3, name: 'Sandford Depot', kind: 'site', is_active: true },
          { id: 1, name: 'Head Office', kind: 'site', is_active: true },
        ],
        total: 3,
      },
    })
    mockMergeSafetyLookup.mockResolvedValue({ data: { merged: true } })

    renderLookups(<LookupTables />, '/admin/lookups?pending=safety')

    expect(await screen.findByTestId('safety-pending-merge-into-location-9')).toBeInTheDocument()
    expect(screen.queryByTestId('safety-pending-merge-location-9')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('safety-pending-merge-into-location-9'))
    expect(await screen.findByTestId('safety-lookup-merge-dialog')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockListLocations).toHaveBeenCalledWith({
        page: 1,
        page_size: 500,
        is_active: true,
      })
    })

    const select = await screen.findByTestId('safety-lookup-merge-target')
    await user.selectOptions(select, '3')
    await user.click(screen.getByTestId('safety-lookup-merge-confirm'))

    await waitFor(() => {
      expect(mockMergeSafetyLookup).toHaveBeenCalledWith('location', 9, 3)
    })
  })

  it('creates a location with premises kind from the kind select (W1)', async () => {
    const user = userEvent.setup()
    renderLookups(<LookupTables />, '/admin/lookups?pending=safety')

    await user.click(await screen.findByRole('button', { name: 'Add location' }))
    const kindSelect = await screen.findByTestId('safety-create-location-kind')
    expect(kindSelect).toHaveValue('site')
    await user.selectOptions(kindSelect, 'premises')
    expect(kindSelect).toHaveValue('premises')

    await user.type(screen.getByLabelText('Safety lookup name'), 'Main Premises')
    await user.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => {
      expect(mockCreateLocation).toHaveBeenCalledWith({
        name: 'Main Premises',
        kind: 'premises',
        force: false,
      })
    })
  })
})

describe('generateLookupCode', () => {
  it('slugifies human names into stable codes', async () => {
    const { generateLookupCode } = await import('../LookupTables')
    expect(generateLookupCode('Oxford Depot')).toBe('oxford_depot')
    expect(generateLookupCode('  High-risk / Near Miss  ')).toBe('high_risk_near_miss')
  })
})
