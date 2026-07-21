import { describe, expect, it } from 'vitest'
import type { TrainingMatrixComplianceRow } from '../../../api/trainingMatrixClient'
import {
  BOARD_ROLES,
  buildPersonRollups,
  buildStatusBriefings,
  computeModuleRoleStats,
  computePeopleFullyOkStats,
  computeRoleStats,
  filterRowsByHorizon,
  groupRowsByCourse,
  groupRowsByDepartment,
  groupRowsByPerson,
  horizonForRow,
  isOkStatus,
  moduleViewForRole,
  myTrainingSummary,
  resolveBoardRole,
  rowsToCsv,
  statusLabel,
  topCoursesInHorizon,
} from './trainingMatrixBoardHelpers'

const TODAY = new Date(2026, 6, 20) // 20 Jul 2026 (local, matches Python test fixture)

function iso(days: number): string {
  const d = new Date(TODAY)
  d.setDate(d.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function row(overrides: Partial<TrainingMatrixComplianceRow>): TrainingMatrixComplianceRow {
  return {
    atlas_name: 'Alice',
    department: 'Mobile Engineers',
    engineer_id: 1,
    engineer_display_name: 'Alice A',
    course_key: 'asbestos_awareness',
    course_display_name: 'Asbestos Awareness',
    frequency_years: 1,
    status: 'compliant',
    atlas_status: 'Completed',
    passed_on: null,
    expires_on: null,
    qgp_due_on: null,
    expiry_without_passed: false,
    atlas_hub_url: 'https://atlas',
    ...overrides,
  }
}

describe('BOARD_ROLES', () => {
  it('matches the backend role order', () => {
    expect(BOARD_ROLES).toEqual(['Engineer', 'Workshop', 'Office', 'Management'])
  })
})

describe('resolveBoardRole', () => {
  it('matches roles as a substring of department', () => {
    expect(resolveBoardRole('Mobile Engineers')).toBe('Engineer')
    expect(resolveBoardRole('Workshop')).toBe('Workshop')
    expect(resolveBoardRole('Head Office')).toBe('Office')
    expect(resolveBoardRole('Senior Management')).toBe('Management')
  })

  it('prefers an Admin Training group override over Atlas department', () => {
    expect(resolveBoardRole('IT', 'Office')).toBe('Office')
    expect(resolveBoardRole('Mobile Engineers', 'Management')).toBe('Management')
    expect(resolveBoardRole('IT', null)).toBeNull()
    expect(resolveBoardRole('IT', 'Sales')).toBeNull()
  })

  it('returns null when nothing matches', () => {
    expect(resolveBoardRole('Sales')).toBeNull()
    expect(resolveBoardRole(null)).toBeNull()
    expect(resolveBoardRole(undefined)).toBeNull()
  })
})

describe('horizonForRow', () => {
  it('treats overdue-family statuses without a due date as overdue', () => {
    for (const status of ['overdue', 'missing', 'pending', 'failed']) {
      expect(horizonForRow(status, null, TODAY)).toBe('overdue')
    }
  })

  it('treats a past due date as overdue regardless of status', () => {
    expect(horizonForRow('compliant', iso(-1), TODAY)).toBe('overdue')
    expect(horizonForRow('due_soon', iso(-400), TODAY)).toBe('overdue')
  })

  it('buckets future due dates into d30/d60/d180/ok', () => {
    expect(horizonForRow('compliant', iso(0), TODAY)).toBe('d30')
    expect(horizonForRow('compliant', iso(30), TODAY)).toBe('d30')
    expect(horizonForRow('compliant', iso(31), TODAY)).toBe('d60')
    expect(horizonForRow('compliant', iso(60), TODAY)).toBe('d60')
    expect(horizonForRow('compliant', iso(61), TODAY)).toBe('d180')
    expect(horizonForRow('compliant', iso(180), TODAY)).toBe('d180')
    expect(horizonForRow('compliant', iso(181), TODAY)).toBe('ok')
  })

  it('is ok when there is no due date and status is not overdue-family', () => {
    expect(horizonForRow('compliant', null, TODAY)).toBe('ok')
    expect(horizonForRow(null, null, TODAY)).toBe('ok')
  })
})

describe('statusLabel', () => {
  it('renders plain labels', () => {
    expect(statusLabel(row({ status: 'overdue', qgp_due_on: null }), TODAY)).toBe('Overdue')
    expect(statusLabel(row({ status: 'due_soon', qgp_due_on: iso(10) }), TODAY)).toBe('Due in 10d')
    expect(statusLabel(row({ status: 'compliant', qgp_due_on: iso(200) }), TODAY)).toBe(`OK until ${iso(200)}`)
  })
})

describe('computeModuleRoleStats', () => {
  it('counts due_soon as OK and reports module-level %', () => {
    const rows = [
      row({ atlas_name: 'Alice', department: 'Mobile Engineers', course_key: 'a', status: 'compliant' }),
      row({ atlas_name: 'Alice', department: 'Mobile Engineers', course_key: 'b', status: 'missing' }),
      row({
        atlas_name: 'Dana',
        department: 'IT',
        board_role_override: 'Office',
        course_key: 'gdpr',
        status: 'due_soon',
      }),
    ]
    expect(isOkStatus('due_soon')).toBe(true)
    const stats = computeModuleRoleStats(rows)
    const overall = stats.find((s) => s.role === 'Overall')!
    expect(overall.ok).toBe(2)
    expect(overall.total).toBe(3)
    expect(overall.pct).toBe(67)
    expect(stats.find((s) => s.role === 'Office')?.pct).toBe(100)
  })
})

describe('computeRoleStats / people fully OK', () => {
  it('computes overall + per-role % of people with every course OK', () => {
    const rows = [
      row({ atlas_name: 'Alice', department: 'Mobile Engineers', course_key: 'a', status: 'compliant' }),
      row({ atlas_name: 'Alice', department: 'Mobile Engineers', course_key: 'b', status: 'compliant' }),
      row({ atlas_name: 'Bob', department: 'Mobile Engineers', course_key: 'a', status: 'overdue' }),
      row({ atlas_name: 'Carl', department: 'Workshop', course_key: 'a', status: 'compliant' }),
    ]
    const stats = computePeopleFullyOkStats(rows)
    const overall = stats.find((s) => s.role === 'Overall')!
    const engineer = stats.find((s) => s.role === 'Engineer')!
    const workshop = stats.find((s) => s.role === 'Workshop')!
    expect(overall.total).toBe(3)
    expect(overall.ok).toBe(2)
    expect(engineer.total).toBe(2)
    expect(engineer.ok).toBe(1)
    expect(workshop.pct).toBe(100)
    expect(computeRoleStats(rows)).toEqual(stats)
  })

  it('buckets people by override when set', () => {
    const rows = [
      row({
        atlas_name: 'Dana',
        department: 'IT',
        board_role_override: 'Office',
        status: 'compliant',
      }),
    ]
    const stats = computeRoleStats(rows)
    const office = stats.find((s) => s.role === 'Office')
    expect(office?.total).toBe(1)
    expect(office?.ok).toBe(1)
  })
})

describe('buildPersonRollups', () => {
  it('uses full required set for Complete/Need while horizon filters who appears', () => {
    const all = [
      row({ atlas_name: 'Alice', course_key: 'a', status: 'compliant', qgp_due_on: iso(100) }),
      row({ atlas_name: 'Alice', course_key: 'b', status: 'missing', qgp_due_on: null }),
      row({ atlas_name: 'Bob', course_key: 'a', status: 'compliant', qgp_due_on: iso(100) }),
    ]
    const filtered = [all[1]] // overdue/missing horizon would include Alice only
    const rollups = buildPersonRollups(all, filtered, TODAY)
    expect(rollups).toHaveLength(1)
    expect(rollups[0].atlas_name).toBe('Alice')
    expect(rollups[0].complete).toBe(1)
    expect(rollups[0].need).toBe(1)
    expect(rollups[0].pct).toBe(50)
    expect(rollups[0].overdue).toBe(1)
  })
})

describe('buildStatusBriefings', () => {
  it('surfaces the highest-risk module and due-in-30 pulse', () => {
    const rows = [
      row({ atlas_name: 'Alice', course_display_name: 'Asbestos Awareness', status: 'overdue', qgp_due_on: iso(-5) }),
      row({ atlas_name: 'Bob', course_display_name: 'Asbestos Awareness', status: 'overdue', qgp_due_on: iso(-2) }),
      row({ atlas_name: 'Carl', course_display_name: 'GDPR', status: 'overdue', qgp_due_on: iso(-1) }),
      row({ atlas_name: 'Dana', course_display_name: 'GDPR', status: 'compliant', qgp_due_on: iso(10) }),
    ]
    const stats = computeRoleStats(rows)
    const briefings = buildStatusBriefings(rows, stats, TODAY)
    const titles = briefings.map((b) => b.title)
    expect(titles).toContain('Highest-risk module')
    const highest = briefings.find((b) => b.title === 'Highest-risk module')!
    expect(highest.detail).toContain('Asbestos Awareness')
    const due30 = briefings.find((b) => b.title === 'Due in 30 days')!
    expect(due30.detail).toContain('1')
    expect(briefings.length).toBeLessThanOrEqual(5)
  })

  it('flags people whose every module is missing as likely new starters', () => {
    const rows = [
      row({ atlas_name: 'Eve', course_key: 'a', status: 'missing', qgp_due_on: null }),
      row({ atlas_name: 'Eve', course_key: 'b', status: 'missing', qgp_due_on: null }),
      row({ atlas_name: 'Frank', course_key: 'a', status: 'compliant', qgp_due_on: iso(90) }),
    ]
    const briefings = buildStatusBriefings(rows, computeRoleStats(rows), TODAY)
    const starters = briefings.find((b) => b.title === 'Likely new starters')
    expect(starters?.detail).toContain('Eve')
    expect(starters?.detail).not.toContain('Frank')
  })
})

describe('filterRowsByHorizon', () => {
  const rows = [
    row({ atlas_name: 'Alice', status: 'overdue', qgp_due_on: iso(-1) }),
    row({ atlas_name: 'Bob', status: 'compliant', qgp_due_on: iso(20) }),
    row({ atlas_name: 'Carl', status: 'compliant', qgp_due_on: iso(200) }),
  ]

  it('filters to a specific horizon bucket', () => {
    expect(filterRowsByHorizon(rows, 'overdue', TODAY)).toHaveLength(1)
    expect(filterRowsByHorizon(rows, 'd30', TODAY)).toHaveLength(1)
  })

  it('keeps every non-compliant row for "all"', () => {
    const filtered = filterRowsByHorizon(rows, 'all', TODAY)
    expect(filtered).toHaveLength(1)
    expect(filtered[0].atlas_name).toBe('Alice')
  })
})

describe('groupRowsByCourse and topCoursesInHorizon', () => {
  const rows = [
    row({ course_key: 'a', course_display_name: 'Asbestos Awareness', status: 'overdue', qgp_due_on: iso(-1) }),
    row({ course_key: 'a', course_display_name: 'Asbestos Awareness', status: 'overdue', qgp_due_on: iso(-2) }),
    row({ course_key: 'b', course_display_name: 'GDPR', status: 'compliant', qgp_due_on: iso(10) }),
  ]

  it('aggregates counts per course with the worst course first', () => {
    const grouped = groupRowsByCourse(rows, TODAY)
    expect(grouped[0].course_key).toBe('a')
    expect(grouped[0].overdue).toBe(2)
  })

  it('returns top courses within a horizon, most-affected first', () => {
    const top = topCoursesInHorizon(rows, 'overdue', 5, TODAY)
    expect(top[0]).toEqual({ course_display_name: 'Asbestos Awareness', count: 2 })
  })
})

describe('groupRowsByDepartment', () => {
  it('sorts departments with the most overdue rows first', () => {
    const rows = [
      row({ department: 'Mobile Engineers', status: 'overdue', qgp_due_on: iso(-1) }),
      row({ department: 'Head Office', status: 'compliant', qgp_due_on: iso(10) }),
      row({ department: 'Mobile Engineers', course_key: 'b', status: 'overdue', qgp_due_on: iso(-2) }),
    ]
    const grouped = groupRowsByDepartment(rows, TODAY)
    expect(grouped[0].department).toBe('Mobile Engineers')
    expect(grouped[0].overdue).toBe(2)
    expect(grouped[1].department).toBe('Head Office')
  })
})

describe('groupRowsByPerson', () => {
  it('sorts people with the most overdue rows first', () => {
    const rows = [
      row({ atlas_name: 'Alice', status: 'compliant', qgp_due_on: iso(10) }),
      row({ atlas_name: 'Bob', status: 'overdue', qgp_due_on: iso(-1) }),
      row({ atlas_name: 'Bob', course_key: 'b', status: 'overdue', qgp_due_on: iso(-2) }),
    ]
    const grouped = groupRowsByPerson(rows, TODAY)
    expect(grouped[0].atlas_name).toBe('Bob')
    expect(grouped[0].overdue).toBe(2)
  })
})

describe('moduleViewForRole', () => {
  it('scopes to a role and computes % compliant per course', () => {
    const rows = [
      row({ atlas_name: 'Alice', department: 'Mobile Engineers', course_key: 'a', status: 'compliant' }),
      row({ atlas_name: 'Bob', department: 'Mobile Engineers', course_key: 'a', status: 'overdue' }),
      row({ atlas_name: 'Carl', department: 'Workshop', course_key: 'a', status: 'compliant' }),
    ]
    const view = moduleViewForRole(rows, 'Engineer')
    expect(view).toHaveLength(1)
    expect(view[0].total).toBe(2)
    expect(view[0].compliant).toBe(1)
    expect(view[0].pct).toBe(50)
  })

  it('uses board_role_override when Atlas department does not match a board role', () => {
    const rows = [
      row({
        atlas_name: 'Dana',
        department: 'IT',
        board_role_override: 'Office',
        course_key: 'gdpr',
        status: 'compliant',
      }),
    ]
    const view = moduleViewForRole(rows, 'Office')
    expect(view).toHaveLength(1)
    expect(view[0].total).toBe(1)
    expect(moduleViewForRole(rows, 'Engineer')).toHaveLength(0)
  })
})

describe('rowsToCsv', () => {
  it('renders a header row plus one row per compliance line', () => {
    const csv = rowsToCsv([row({ status: 'overdue', qgp_due_on: null })], TODAY)
    const lines = csv.split('\n')
    expect(lines).toHaveLength(2)
    expect(lines[0]).toContain('Person')
    expect(lines[1]).toContain('Overdue')
  })
})

describe('myTrainingSummary', () => {
  it('counts OK modules (including due_soon) and finds the next gap due', () => {
    const rows = [
      row({ course_display_name: 'Asbestos Awareness', status: 'compliant', qgp_due_on: iso(100) }),
      row({ course_display_name: 'GDPR', status: 'overdue', qgp_due_on: iso(-1) }),
      row({ course_display_name: 'DSE', status: 'due_soon', qgp_due_on: iso(5) }),
    ]
    const summary = myTrainingSummary(rows)
    expect(summary.total).toBe(3)
    expect(summary.okCount).toBe(2) // compliant + due_soon
    expect(summary.nextDue?.course_display_name).toBe('GDPR')
  })
})
