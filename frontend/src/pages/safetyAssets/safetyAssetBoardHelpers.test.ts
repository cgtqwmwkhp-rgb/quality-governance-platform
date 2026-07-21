import { describe, expect, it } from 'vitest'
import type { SafetyAsset } from '../../api/safetyAssetsClient'
import {
  bandLabel,
  buildEngineerRollups,
  buildTypeRollups,
  buildVehicleRollups,
  computeHeroCounts,
  filterAssetRows,
  horizonForAsset,
  isOkAsset,
  sortAssetRows,
  sortEntityRollups,
} from './safetyAssetBoardHelpers'

function asset(partial: Partial<SafetyAsset> & Pick<SafetyAsset, 'id'>): SafetyAsset {
  return {
    external_id: `ext-${partial.id}`,
    asset_type_id: 1,
    asset_number: `A-${partial.id}`,
    name: `Asset ${partial.id}`,
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...partial,
  }
}

const today = new Date(2026, 6, 21) // 21 Jul 2026 local

describe('safetyAssetBoardHelpers OK SSOT', () => {
  it('treats active non-overdue bands as OK (Training due_soon analogue)', () => {
    expect(isOkAsset(asset({ id: 1, expiry_date: '2026-08-01' }), today)).toBe(true) // due_30
    expect(isOkAsset(asset({ id: 2, expiry_date: '2026-12-01' }), today)).toBe(true) // in_date
    expect(isOkAsset(asset({ id: 3, expiry_date: '2026-06-01' }), today)).toBe(false) // overdue
    expect(isOkAsset(asset({ id: 4, status: 'quarantined', expiry_date: '2026-12-01' }), today)).toBe(
      false,
    )
  })

  it('classifies exclusive horizons', () => {
    expect(horizonForAsset(asset({ id: 1, expiry_date: '2026-06-01' }), today)).toBe('overdue')
    expect(horizonForAsset(asset({ id: 2, expiry_date: '2026-08-01' }), today)).toBe('due_30')
    expect(horizonForAsset(asset({ id: 3, expiry_date: '2026-09-01' }), today)).toBe('due_60')
    expect(horizonForAsset(asset({ id: 4, expiry_date: '2026-10-01' }), today)).toBe('due_90')
    expect(horizonForAsset(asset({ id: 5, expiry_date: '2027-01-01' }), today)).toBe('in_date')
  })

  it('builds hero counts and engineer % OK', () => {
    const rows = [
      asset({ id: 1, owner_user_id: 9, expiry_date: '2026-12-01' }),
      asset({ id: 2, owner_user_id: 9, expiry_date: '2026-06-01' }),
      asset({ id: 3, owner_user_id: 9, status: 'quarantined', expiry_date: '2026-12-01' }),
      asset({ id: 4, vehicle_reg: 'AB12CDE', expiry_date: '2026-08-10' }),
      asset({ id: 5, status: 'decommissioned', expiry_date: '2025-01-01' }),
    ]
    const hero = computeHeroCounts(rows, today)
    expect(hero.all).toBe(5)
    expect(hero.overdue).toBe(2) // id 2 + decommissioned past date
    expect(hero.quarantined).toBe(1)
    expect(hero.decommissioned).toBe(1)

    const engineers = buildEngineerRollups(rows, new Map([[9, 'Darren Adams']]), today)
    const darren = engineers.find((r) => r.key === 'user:9')
    expect(darren?.total).toBe(3)
    expect(darren?.ok).toBe(1)
    expect(darren?.pct).toBe(33)
    expect(bandLabel(rows[2], today)).toBe('Fail')
  })

  it('rolls up vehicle and type, and sorts/filters asset rows', () => {
    const rows = [
      asset({
        id: 1,
        vehicle_reg: 'LA23HXM',
        asset_type_id: 10,
        name: 'Torque',
        serial_number: 'TW1',
        owner_user_id: 1,
        expiry_date: '2026-12-01',
      }),
      asset({
        id: 2,
        vehicle_reg: 'LA23HXM',
        asset_type_id: 11,
        name: 'RCD',
        serial_number: 'RCD1',
        expiry_date: '2026-06-01',
      }),
    ]
    const vehicles = buildVehicleRollups(rows, today)
    expect(vehicles[0].label).toBe('LA23HXM')
    expect(vehicles[0].total).toBe(2)
    expect(vehicles[0].overdue).toBe(1)

    const types = buildTypeRollups(rows, new Map([[10, 'Torque Wrench'], [11, 'RCD Tester']]), today)
    expect(types).toHaveLength(2)

    const sorted = sortAssetRows(rows, 'serial', 'asc', new Map(), new Map())
    expect(sorted.map((a) => a.serial_number)).toEqual(['RCD1', 'TW1'])

    const filtered = filterAssetRows(
      rows,
      {
        serial: 'tw',
        name: '',
        type: '',
        owner: '',
        vehicle: '',
        site: '',
        expiry: '',
        status: '',
      },
      new Map(),
      new Map(),
    )
    expect(filtered).toHaveLength(1)

    const rollups = sortEntityRollups(vehicles, 'overdue', 'desc')
    expect(rollups[0].overdue).toBeGreaterThanOrEqual(rollups[rollups.length - 1].overdue)
  })
})
