// Pure helpers for the manager Training Matrix board (horizon-first view).
// Mirrors src/domain/services/training_matrix_board.py so the FE board and BE
// notify/preview paths agree on the same due-date horizons and role grouping.
import type { TrainingMatrixComplianceRow } from '../../../api/trainingMatrixClient'

export const BOARD_ROLES = ['Engineer', 'Workshop', 'Office', 'Management'] as const
export type BoardRole = (typeof BOARD_ROLES)[number]

export type Horizon = 'overdue' | 'd30' | 'd60' | 'd180' | 'ok'

const OVERDUE_STATUSES = new Set(['overdue', 'missing', 'pending', 'failed'])
/** In-cycle: has Passed within frequency (includes due_soon). Mirrors BE _OK_STATUSES. */
const OK_STATUSES = new Set(['compliant', 'due_soon'])

const DAY_MS = 24 * 60 * 60 * 1000

export function isOkStatus(status?: string | null): boolean {
  return OK_STATUSES.has((status || '').trim().toLowerCase())
}

export function isGapStatus(status?: string | null): boolean {
  return OVERDUE_STATUSES.has((status || '').trim().toLowerCase())
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function parseDueDate(qgpDueOn?: string | null): Date | null {
  if (!qgpDueOn) return null
  // Parse "YYYY-MM-DD" as a local calendar date — `new Date(str)` treats bare
  // date strings as UTC midnight, which can shift a day off in non-UTC zones.
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(qgpDueOn)
  if (match) {
    const [, y, m, d] = match
    return new Date(Number(y), Number(m) - 1, Number(d))
  }
  const parsed = new Date(qgpDueOn)
  if (Number.isNaN(parsed.getTime())) return null
  return startOfDay(parsed)
}

/** Prefer Admin override; else first BOARD_ROLE substring-matched in department (e.g. Engineer in "Mobile Engineers"). */
export function resolveBoardRole(
  department?: string | null,
  override?: string | null,
): BoardRole | null {
  if (override) {
    const cleaned = override.trim().toLowerCase()
    const exact = BOARD_ROLES.find((role) => role.toLowerCase() === cleaned)
    if (exact) return exact
  }
  if (!department) return null
  const deptLower = department.trim().toLowerCase()
  for (const role of BOARD_ROLES) {
    if (deptLower.includes(role.toLowerCase())) return role
  }
  return null
}

/** Classify a person x course compliance row into a due-date horizon bucket. */
export function horizonForRow(
  status: string | null | undefined,
  qgpDueOn: string | null | undefined,
  today: Date = new Date(),
): Horizon {
  const todayStart = startOfDay(today)
  const statusLower = (status || '').trim().toLowerCase()
  const due = parseDueDate(qgpDueOn)

  if (OVERDUE_STATUSES.has(statusLower) && (due === null || due < todayStart)) {
    return 'overdue'
  }
  if (due === null) {
    return OVERDUE_STATUSES.has(statusLower) ? 'overdue' : 'ok'
  }
  const daysAway = Math.round((due.getTime() - todayStart.getTime()) / DAY_MS)
  if (daysAway < 0) return 'overdue'
  if (daysAway <= 30) return 'd30'
  if (daysAway <= 60) return 'd60'
  if (daysAway <= 180) return 'd180'
  return 'ok'
}

/** Plain status label: "Overdue" / "Due in Nd" / "OK until <date>". */
export function statusLabel(row: TrainingMatrixComplianceRow, today: Date = new Date()): string {
  const horizon = horizonForRow(row.status, row.qgp_due_on, today)
  if (horizon === 'overdue') return 'Overdue'
  const due = parseDueDate(row.qgp_due_on)
  if (!due) return 'OK'
  if (horizon === 'ok') return `OK until ${row.qgp_due_on}`
  const daysAway = Math.round((due.getTime() - startOfDay(today).getTime()) / DAY_MS)
  return `Due in ${daysAway}d`
}

export type RoleStat = {
  role: string
  pct: number
  ok: number
  total: number
  metric?: 'module_ok' | 'people_fully_ok'
}

/** Module-level OK% (compliant + due_soon) — hero primary. Mirrors BE compute_module_role_stats. */
export function computeModuleRoleStats(rows: TrainingMatrixComplianceRow[]): RoleStat[] {
  const scopes: Array<BoardRole | 'Overall'> = ['Overall', ...BOARD_ROLES]
  return scopes.map((scope) => {
    const scoped =
      scope === 'Overall'
        ? rows
        : rows.filter((r) => resolveBoardRole(r.department, r.board_role_override) === scope)
    const total = scoped.length
    const ok = scoped.filter((r) => isOkStatus(r.status)).length
    return {
      role: scope,
      ok,
      total,
      pct: total ? Math.round((100 * ok) / total) : 0,
      metric: 'module_ok' as const,
    }
  })
}

/** People with every required module OK — hero secondary caption. */
export function computePeopleFullyOkStats(rows: TrainingMatrixComplianceRow[]): RoleStat[] {
  const byPerson = new Map<string, TrainingMatrixComplianceRow[]>()
  for (const row of rows) {
    const bucket = byPerson.get(row.atlas_name)
    if (bucket) bucket.push(row)
    else byPerson.set(row.atlas_name, [row])
  }

  const roleCounts: Record<string, { ok: number; total: number }> = {}
  for (const role of BOARD_ROLES) roleCounts[role] = { ok: 0, total: 0 }
  let overallOk = 0
  let overallTotal = 0

  for (const [, personRows] of byPerson) {
    if (personRows.length === 0) continue
    const fullyOk = personRows.every((r) => isOkStatus(r.status))
    overallTotal += 1
    if (fullyOk) overallOk += 1
    const role = resolveBoardRole(personRows[0].department, personRows[0].board_role_override)
    if (role) {
      roleCounts[role].total += 1
      if (fullyOk) roleCounts[role].ok += 1
    }
  }

  const stats: RoleStat[] = [
    {
      role: 'Overall',
      pct: overallTotal ? Math.round((100 * overallOk) / overallTotal) : 0,
      ok: overallOk,
      total: overallTotal,
      metric: 'people_fully_ok',
    },
  ]
  for (const role of BOARD_ROLES) {
    const { ok, total } = roleCounts[role]
    stats.push({
      role,
      pct: total ? Math.round((100 * ok) / total) : 0,
      ok,
      total,
      metric: 'people_fully_ok',
    })
  }
  return stats
}

/** @deprecated Prefer computeModuleRoleStats for hero; kept as alias to people-fully-OK for briefings. */
export function computeRoleStats(rows: TrainingMatrixComplianceRow[]): RoleStat[] {
  return computePeopleFullyOkStats(rows)
}

export type PersonRollup = {
  atlas_name: string
  person_id?: number | null
  engineer_display_name?: string | null
  department?: string | null
  board_role_override?: string | null
  role: BoardRole | null
  complete: number
  overdue: number
  need: number
  total: number
  pct: number
  /** Rows used for the rollup (full required set). */
  allRows: TrainingMatrixComplianceRow[]
  /** Subset matching the active horizon filter (for list membership / selection). */
  filteredRows: TrainingMatrixComplianceRow[]
}

/** Full-set person rollups; optional filteredRows decide who appears under a horizon. */
export function buildPersonRollups(
  allRows: TrainingMatrixComplianceRow[],
  filteredRows: TrainingMatrixComplianceRow[],
  today: Date = new Date(),
): PersonRollup[] {
  const byPerson = new Map<string, TrainingMatrixComplianceRow[]>()
  for (const row of allRows) {
    const bucket = byPerson.get(row.atlas_name)
    if (bucket) bucket.push(row)
    else byPerson.set(row.atlas_name, [row])
  }
  const filteredNames = new Set(filteredRows.map((r) => r.atlas_name))
  const filteredByPerson = new Map<string, TrainingMatrixComplianceRow[]>()
  for (const row of filteredRows) {
    const bucket = filteredByPerson.get(row.atlas_name)
    if (bucket) bucket.push(row)
    else filteredByPerson.set(row.atlas_name, [row])
  }

  const rollups: PersonRollup[] = []
  for (const [atlasName, personRows] of byPerson) {
    if (!filteredNames.has(atlasName)) continue
    const complete = personRows.filter((r) => isOkStatus(r.status)).length
    const overdue = personRows.filter(
      (r) => horizonForRow(r.status, r.qgp_due_on, today) === 'overdue',
    ).length
    const total = personRows.length
    const need = total - complete
    const first = personRows[0]
    rollups.push({
      atlas_name: atlasName,
      person_id: first.person_id,
      engineer_display_name: first.engineer_display_name,
      department: first.department,
      board_role_override: first.board_role_override,
      role: resolveBoardRole(first.department, first.board_role_override),
      complete,
      overdue,
      need,
      total,
      pct: total ? Math.round((100 * complete) / total) : 0,
      allRows: personRows,
      filteredRows: filteredByPerson.get(atlasName) || [],
    })
  }
  return rollups.sort((a, b) => b.overdue - a.overdue || a.atlas_name.localeCompare(b.atlas_name))
}

export type Briefing = { title: string; detail: string }

/** Up to 5 grounded, data-derived insights for the rotating status banner. */
export function buildStatusBriefings(
  rows: TrainingMatrixComplianceRow[],
  roleStats: Pick<RoleStat, 'role' | 'pct' | 'total'>[],
  today: Date = new Date(),
): Briefing[] {
  const briefings: Briefing[] = []
  const overdueByCourse = new Map<string, number>()
  let d30Count = 0
  const byPerson = new Map<string, TrainingMatrixComplianceRow[]>()

  for (const row of rows) {
    const horizon = horizonForRow(row.status, row.qgp_due_on, today)
    if (horizon === 'overdue') {
      const label = row.course_display_name || row.course_key
      overdueByCourse.set(label, (overdueByCourse.get(label) || 0) + 1)
    } else if (horizon === 'd30') {
      d30Count += 1
    }
    if (row.atlas_name) {
      const bucket = byPerson.get(row.atlas_name)
      if (bucket) bucket.push(row)
      else byPerson.set(row.atlas_name, [row])
    }
  }

  if (overdueByCourse.size > 0) {
    let topCourse = ''
    let topCount = 0
    for (const [course, count] of overdueByCourse) {
      if (count > topCount) {
        topCourse = course
        topCount = count
      }
    }
    briefings.push({
      title: 'Highest-risk module',
      detail: `${topCourse} has ${topCount} overdue completion${topCount !== 1 ? 's' : ''} across the workforce — the biggest single gap right now.`,
    })
  }

  const newStarters = [...byPerson.entries()]
    .filter(([, personRows]) => personRows.length > 0 && personRows.every((r) => (r.status || '').toLowerCase() === 'missing'))
    .map(([name]) => name)
    .sort()
  if (newStarters.length > 0) {
    const sample = newStarters.slice(0, 3).join(', ')
    const more = newStarters.length > 3 ? ` and ${newStarters.length - 3} more` : ''
    briefings.push({
      title: 'Likely new starters',
      detail: `${newStarters.length} people show every required module as missing (no Atlas history yet) — check onboarding for ${sample}${more}.`,
    })
  }

  const roleEntries = roleStats.filter((s) => s.role !== 'Overall' && s.total > 0)
  if (roleEntries.length > 0) {
    const weakest = roleEntries.reduce((a, b) => (b.pct < a.pct ? b : a))
    briefings.push({
      title: 'Weakest role',
      detail: `${weakest.role} is at ${weakest.pct}% fully compliant — the lowest of the role groups.`,
    })
  }

  briefings.push({
    title: 'Due in 30 days',
    detail: `${d30Count} module completion${d30Count !== 1 ? 's' : ''} fall due in the next 30 days — plan Atlas time now to stay ahead of overdue.`,
  })

  if (roleEntries.length > 0) {
    const strongest = roleEntries.reduce((a, b) => (b.pct > a.pct ? b : a))
    briefings.push({
      title: 'Strongest role',
      detail: `${strongest.role} leads at ${strongest.pct}% fully compliant.`,
    })
  }

  return briefings.slice(0, 5)
}

export const HORIZON_FILTERS: { id: Horizon | 'all'; label: string }[] = [
  { id: 'overdue', label: 'Overdue' },
  { id: 'd30', label: 'Next 30 days' },
  { id: 'd60', label: 'Next 60 days' },
  { id: 'd180', label: 'Next 180 days' },
  { id: 'all', label: 'All open' },
]

/** Rows matching a horizon filter. "all" keeps every non-compliant row (open gaps). */
export function filterRowsByHorizon(
  rows: TrainingMatrixComplianceRow[],
  horizon: Horizon | 'all',
  today: Date = new Date(),
): TrainingMatrixComplianceRow[] {
  if (horizon === 'all') return rows.filter((r) => !isOkStatus(r.status))
  return rows.filter((r) => horizonForRow(r.status, r.qgp_due_on, today) === horizon)
}

export type CourseAggregate = {
  course_key: string
  course_display_name: string
  overdue: number
  d30: number
  d60: number
  d180: number
  ok: number
  total: number
}

/** Group filtered rows by course, counting horizon buckets — used for "By course" view + top-courses. */
export function groupRowsByCourse(
  rows: TrainingMatrixComplianceRow[],
  today: Date = new Date(),
): CourseAggregate[] {
  const byCourse = new Map<string, CourseAggregate>()
  for (const row of rows) {
    const key = row.course_key
    let agg = byCourse.get(key)
    if (!agg) {
      agg = {
        course_key: key,
        course_display_name: row.course_display_name,
        overdue: 0,
        d30: 0,
        d60: 0,
        d180: 0,
        ok: 0,
        total: 0,
      }
      byCourse.set(key, agg)
    }
    agg.total += 1
    agg[horizonForRow(row.status, row.qgp_due_on, today)] += 1
  }
  return [...byCourse.values()].sort((a, b) => b.overdue - a.overdue || a.course_display_name.localeCompare(b.course_display_name))
}

/** Top courses within a single horizon bucket, most-affected first. */
export function topCoursesInHorizon(
  rows: TrainingMatrixComplianceRow[],
  horizon: Horizon,
  limit = 5,
  today: Date = new Date(),
): { course_display_name: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const row of rows) {
    if (horizonForRow(row.status, row.qgp_due_on, today) !== horizon) continue
    const label = row.course_display_name
    counts.set(label, (counts.get(label) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([course_display_name, count]) => ({ course_display_name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit)
}

export type DepartmentAggregate = {
  department: string
  overdue: number
  total: number
}

/** Group filtered rows by raw Atlas department — used for the "By group" view. */
export function groupRowsByDepartment(
  rows: TrainingMatrixComplianceRow[],
  today: Date = new Date(),
): DepartmentAggregate[] {
  const byDept = new Map<string, DepartmentAggregate>()
  for (const row of rows) {
    const dept = row.department || 'Unspecified'
    let agg = byDept.get(dept)
    if (!agg) {
      agg = { department: dept, overdue: 0, total: 0 }
      byDept.set(dept, agg)
    }
    agg.total += 1
    if (horizonForRow(row.status, row.qgp_due_on, today) === 'overdue') agg.overdue += 1
  }
  return [...byDept.values()].sort((a, b) => b.overdue - a.overdue || a.department.localeCompare(b.department))
}

export type PersonAggregate = {
  atlas_name: string
  engineer_display_name?: string | null
  department?: string | null
  rows: TrainingMatrixComplianceRow[]
  overdue: number
  total: number
}

/** Group filtered rows by person — used for "By group" and "By individual" views. */
export function groupRowsByPerson(rows: TrainingMatrixComplianceRow[], today: Date = new Date()): PersonAggregate[] {
  const byPerson = new Map<string, PersonAggregate>()
  for (const row of rows) {
    let agg = byPerson.get(row.atlas_name)
    if (!agg) {
      agg = {
        atlas_name: row.atlas_name,
        engineer_display_name: row.engineer_display_name,
        department: row.department,
        rows: [],
        overdue: 0,
        total: 0,
      }
      byPerson.set(row.atlas_name, agg)
    }
    agg.rows.push(row)
    agg.total += 1
    if (horizonForRow(row.status, row.qgp_due_on, today) === 'overdue') agg.overdue += 1
  }
  return [...byPerson.values()].sort((a, b) => b.overdue - a.overdue || a.atlas_name.localeCompare(b.atlas_name))
}

/** Required modules for a role with % compliant across people mapped to that role — "By module" view. */
export function moduleViewForRole(
  rows: TrainingMatrixComplianceRow[],
  role: BoardRole,
): { course_key: string; course_display_name: string; compliant: number; total: number; pct: number }[] {
  const scoped = rows.filter((r) => resolveBoardRole(r.department, r.board_role_override) === role)
  const byCourse = new Map<string, { course_display_name: string; compliant: number; total: number }>()
  for (const row of scoped) {
    let agg = byCourse.get(row.course_key)
    if (!agg) {
      agg = { course_display_name: row.course_display_name, compliant: 0, total: 0 }
      byCourse.set(row.course_key, agg)
    }
    agg.total += 1
    if (isOkStatus(row.status)) agg.compliant += 1
  }
  return [...byCourse.entries()]
    .map(([course_key, v]) => ({
      course_key,
      course_display_name: v.course_display_name,
      compliant: v.compliant,
      total: v.total,
      pct: v.total ? Math.round((100 * v.compliant) / v.total) : 0,
    }))
    .sort((a, b) => a.pct - b.pct)
}

/** CSV rows (header + data) for the currently filtered gap board rows. */
export function rowsToCsv(rows: TrainingMatrixComplianceRow[], today: Date = new Date()): string {
  const header = ['Person', 'Department', 'Course', 'Status', 'Passed', 'QGP due', 'Atlas expiry']
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`
  const lines = [header]
  for (const row of rows) {
    lines.push([
      row.engineer_display_name || row.atlas_name,
      row.department || '',
      row.course_display_name,
      statusLabel(row, today),
      row.passed_on || '',
      row.qgp_due_on || '',
      row.expires_on || '',
    ])
  }
  return lines.map((cols) => cols.map((c) => escape(String(c))).join(',')).join('\n')
}

export type MyTrainingSummary = {
  total: number
  okCount: number
  nextDue: { course_display_name: string; qgp_due_on: string } | null
}

/** Progress counts + next due module for the "My training" panel (Complete = compliant + due_soon). */
export function myTrainingSummary(rows: TrainingMatrixComplianceRow[]): MyTrainingSummary {
  const okCount = rows.filter((r) => isOkStatus(r.status)).length
  const withDue = rows
    .filter((r) => r.qgp_due_on && isGapStatus(r.status))
    .sort((a, b) => (a.qgp_due_on! < b.qgp_due_on! ? -1 : 1))
  const nextDue = withDue[0]
    ? { course_display_name: withDue[0].course_display_name, qgp_due_on: withDue[0].qgp_due_on! }
    : null
  return { total: rows.length, okCount, nextDue }
}

/** CSV for By individual person rollups. */
export function personRollupsToCsv(rollups: PersonRollup[]): string {
  const header = ['Person', 'Department', 'Training group', 'Complete', 'Overdue', 'Need', 'Total', 'Percent']
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`
  const lines = [header]
  for (const p of rollups) {
    lines.push([
      p.engineer_display_name || p.atlas_name,
      p.department || '',
      p.role || '',
      String(p.complete),
      String(p.overdue),
      String(p.need),
      String(p.total),
      String(p.pct),
    ])
  }
  return lines.map((cols) => cols.map((c) => escape(String(c))).join(',')).join('\n')
}
