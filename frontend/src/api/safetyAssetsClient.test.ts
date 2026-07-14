import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()
const mockPatch = vi.fn()

vi.mock('./client', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
  },
}))

describe('safetyAssetsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
  })

  it('listAssets hits /api/v1/assets/ with filters', async () => {
    mockGet.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20, pages: 0 } })
    const { safetyAssetsApi } = await import('./safetyAssetsClient')
    await safetyAssetsApi.listAssets({
      page: 2,
      page_size: 25,
      asset_type_id: 4,
      location_id: 9,
      vehicle_reg: 'AB12 CDE',
      owner_user_id: 3,
      expiry_band: 'due_30',
    })
    expect(mockGet).toHaveBeenCalledWith('/api/v1/assets/', {
      params: {
        page: 2,
        page_size: 25,
        asset_type_id: 4,
        location_id: 9,
        vehicle_reg: 'AB12 CDE',
        owner_user_id: 3,
        expiry_band: 'due_30',
      },
    })
  })

  it('listLocations and getAsset use distinct paths', async () => {
    mockGet.mockResolvedValue({ data: {} })
    const { safetyAssetsApi } = await import('./safetyAssetsClient')
    await safetyAssetsApi.listLocations({ page: 1, page_size: 100, kind: 'site' })
    await safetyAssetsApi.getAsset(42)
    expect(mockGet).toHaveBeenCalledWith('/api/v1/assets/locations', {
      params: { page: 1, page_size: 100, kind: 'site' },
    })
    expect(mockGet).toHaveBeenCalledWith('/api/v1/assets/42')
  })

  it('getKpis returns null metrics on fetch failure (no silent zeros)', async () => {
    mockGet.mockRejectedValue(new Error('network down'))
    const { safetyAssetsApi, EMPTY_SAFETY_ASSET_KPIS } = await import('./safetyAssetsClient')
    const kpis = await safetyAssetsApi.getKpis()
    expect(kpis).toEqual(EMPTY_SAFETY_ASSET_KPIS)
    expect(kpis.total).toBeNull()
    expect(kpis.overdue).toBeNull()
    expect(kpis.quarantined).toBeNull()
  })

  it('getKpis derives in_date from total − overdue when both succeed', async () => {
    mockGet.mockImplementation((_url: string, config?: { params?: Record<string, unknown> }) => {
      const band = config?.params?.expiry_band
      const status = config?.params?.status
      let total = 100
      if (band === 'overdue') total = 12
      else if (band === 'due_30') total = 5
      else if (band === 'due_60') total = 8
      else if (band === 'due_90') total = 15
      else if (status === 'quarantined') total = 2
      return Promise.resolve({ data: { items: [], total, page: 1, page_size: 1, pages: 1 } })
    })
    const { safetyAssetsApi } = await import('./safetyAssetsClient')
    const kpis = await safetyAssetsApi.getKpis()
    expect(kpis.total).toBe(100)
    expect(kpis.overdue).toBe(12)
    expect(kpis.in_date).toBe(88)
    expect(kpis.due_30).toBe(5)
    expect(kpis.quarantined).toBe(2)
  })

  it('updateAsset patches asset by id', async () => {
    mockPatch.mockResolvedValue({ data: { id: 7 } })
    const { safetyAssetsApi } = await import('./safetyAssetsClient')
    await safetyAssetsApi.updateAsset(7, { photo_evidence_id: 99, status: 'quarantined' })
    expect(mockPatch).toHaveBeenCalledWith('/api/v1/assets/7', {
      photo_evidence_id: 99,
      status: 'quarantined',
    })
  })
})
