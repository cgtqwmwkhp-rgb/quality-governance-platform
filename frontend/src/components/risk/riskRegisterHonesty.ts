/**
 * Run021 risk-register honesty helpers (Lane C).
 *
 * PX-157 / PX-264: surface never-reviewed and untriaged-import backlog without
 * pretending Outside Appetite = 0 or an empty Accept queue means control.
 */

export type NeverReviewedHonesty = {
  show: boolean
  neverReviewed: number
  total: number
  message: string
}

/**
 * When most open risks have never been reviewed, KPI tiles (bands / Outside
 * Appetite) must not read as director-level reassurance.
 */
export function buildNeverReviewedHonesty(
  neverReviewed: number | null | undefined,
  total: number | null | undefined,
): NeverReviewedHonesty {
  const never = typeof neverReviewed === 'number' && neverReviewed >= 0 ? neverReviewed : 0
  const tot = typeof total === 'number' && total >= 0 ? total : 0
  if (never <= 0 || tot <= 0) {
    return { show: false, neverReviewed: never, total: tot, message: '' }
  }
  return {
    show: true,
    neverReviewed: never,
    total: tot,
    message:
      `${never} of ${tot} open risks have never been reviewed. ` +
      'Band and Outside Appetite figures describe scored rows only — they are not assurance that the register is under control. ' +
      'Overdue review counts can include risks that were never assessed.',
  }
}

export type ImportTriageHonesty = {
  show: boolean
  pendingTotal: number
  unassignedLoaded: number
  oldestAgeDays: number | null
  message: string
}

function ageDaysFromIso(iso: string | null | undefined, nowMs: number): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  return Math.max(0, Math.floor((nowMs - t) / (24 * 60 * 60 * 1000)))
}

/**
 * Honesty strip for Import triage: pending backlog, unassigned owners, age.
 */
export function buildImportTriageHonesty(opts: {
  pendingTotal: number
  risks: ReadonlyArray<{ risk_owner_name?: string | null; created_at?: string | null }>
  nowMs?: number
}): ImportTriageHonesty {
  const pendingTotal = Math.max(0, opts.pendingTotal || 0)
  const nowMs = opts.nowMs ?? Date.now()
  const unassignedLoaded = opts.risks.filter((r) => !String(r.risk_owner_name || '').trim()).length
  let oldestAgeDays: number | null = null
  for (const r of opts.risks) {
    const age = ageDaysFromIso(r.created_at, nowMs)
    if (age == null) continue
    if (oldestAgeDays == null || age > oldestAgeDays) oldestAgeDays = age
  }

  if (pendingTotal <= 0) {
    return {
      show: false,
      pendingTotal: 0,
      unassignedLoaded: 0,
      oldestAgeDays: null,
      message: '',
    }
  }

  const parts: string[] = [
    `${pendingTotal} import-sourced risk${pendingTotal === 1 ? '' : 's'} await accept or reject.`,
  ]
  if (unassignedLoaded > 0) {
    parts.push(
      `${unassignedLoaded} on this page ${unassignedLoaded === 1 ? 'is' : 'are'} unassigned — accept requires an owner.`,
    )
  }
  if (oldestAgeDays != null && oldestAgeDays >= 14) {
    parts.push(`Oldest loaded item has sat for ${oldestAgeDays} days.`)
  }

  return {
    show: true,
    pendingTotal,
    unassignedLoaded,
    oldestAgeDays,
    message: parts.join(' '),
  }
}

/** Accept is blocked until the risk has a non-empty owner name (PX-264). */
export function canAcceptImportTriage(risk: {
  risk_owner_name?: string | null
}): boolean {
  return Boolean(String(risk.risk_owner_name || '').trim())
}
