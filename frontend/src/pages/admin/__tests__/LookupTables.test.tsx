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

vi.mock('../../../api/client', () => ({
  lookupsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
  getApiErrorMessage: (err: unknown, fallback?: string) =>
    err instanceof Error ? err.message : fallback || 'error',
}))

vi.mock('../../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listPendingSafetyLookups: (...args: unknown[]) => mockListPendingSafetyLookups(...args),
    approveSafetyLookup: (...args: unknown[]) => mockApproveSafetyLookup(...args),
    mergeSafetyLookup: (...args: unknown[]) => mockMergeSafetyLookup(...args),
    previewSafetyLookup: vi.fn(),
    createAssetType: vi.fn(),
    createLocation: vi.fn(),
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
    mockListPendingSafetyLookups.mockResolvedValue({ data: { items: [], total: 0 } })
    mockList.mockImplementation(async (category: string) => {
      if (
        category === 'departments' ||
        category === 'locations' ||
        category === 'workforce_roles' ||
        category === 'customers' ||
        category === 'tools' ||
        category === 'assets'
      ) {
        return { items: [], total: 0 }
      }
      return {
        items: [{ id: 1, category, code: 'a', label: 'A', is_active: true, display_order: 0 }],
        total: 1,
      }
    })
  })

  it('shows Not configured honesty and primary Configure CTA for empty categories', async () => {
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-count-departments')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-empty-departments')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-configure-departments')).toHaveTextContent('Configure')
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

    expect(await screen.findByTestId('lookup-count-departments')).toHaveTextContent(
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

  it('exposes tools and assets lookup categories on the hub', async () => {
    renderLookups(<LookupTables />)

    expect(await screen.findByTestId('lookup-card-tools')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-card-assets')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-count-tools')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-count-assets')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-hub-category-filter')).toBeInTheDocument()
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
      category: 'locations',
      code: 'oxford_depot',
      label: 'Oxford Depot',
      is_active: true,
      display_order: 0,
    })
    renderLookups(<LookupTables />)

    await user.click(await screen.findByTestId('lookup-configure-locations'))
    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()

    await user.type(screen.getByTestId('lookup-new-label'), 'Oxford Depot')
    expect(screen.getByTestId('lookup-code-preview')).toHaveTextContent('oxford_depot')
    expect(screen.queryByTestId('lookup-new-code')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('lookup-add-option'))
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        'locations',
        expect.objectContaining({
          category: 'locations',
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
      category: 'locations',
      code: 'ox5',
      label: 'Oxford Depot',
      is_active: true,
      display_order: 0,
    })
    renderLookups(<LookupTables />)

    await user.click(await screen.findByTestId('lookup-configure-locations'))
    await screen.findByTestId('lookup-editor-dialog')
    await user.type(screen.getByTestId('lookup-new-label'), 'Oxford Depot')
    await user.click(screen.getByTestId('lookup-advanced-code-toggle'))
    const codeInput = await screen.findByTestId('lookup-new-code')
    await user.clear(codeInput)
    await user.type(codeInput, 'ox5')
    await user.click(screen.getByTestId('lookup-add-option'))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        'locations',
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
})

describe('generateLookupCode', () => {
  it('slugifies human names into stable codes', async () => {
    const { generateLookupCode } = await import('../LookupTables')
    expect(generateLookupCode('Oxford Depot')).toBe('oxford_depot')
    expect(generateLookupCode('  High-risk / Near Miss  ')).toBe('high_risk_near_miss')
  })
})
