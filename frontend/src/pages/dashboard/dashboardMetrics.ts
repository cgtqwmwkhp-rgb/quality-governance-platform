/**
 * Pure, framework-free helpers for the role-aware "living" Dashboard.
 * Kept free of React/axios so persona + fail-honest + highlight-rail logic can be
 * unit tested without mounting the page or mocking network calls.
 */
import type { PortalClearState } from '../../api/portalComplianceClient'

// ============================================================================
// Fail-honest metric wrapper — never let a failed/absent fetch masquerade as 0.
// ============================================================================

export type Metric<T> = { status: 'ok'; value: T } | { status: 'unavailable' }

export function metricOk<T>(value: T): Metric<T> {
  return { status: 'ok', value }
}

export function metricUnavailable<T>(): Metric<T> {
  return { status: 'unavailable' }
}

export function isMetricOk<T>(metric: Metric<T>): metric is { status: 'ok'; value: T } {
  return metric.status === 'ok'
}

/** Read a settled Promise.allSettled result into a fail-honest Metric. */
export function metricFromSettled<T, U = T>(
  result: PromiseSettledResult<T>,
  select: (value: T) => U = (value) => value as unknown as U,
): Metric<U> {
  if (result.status !== 'fulfilled') return metricUnavailable<U>()
  try {
    return metricOk(select(result.value))
  } catch {
    return metricUnavailable<U>()
  }
}

// ============================================================================
// Persona (CUJ locked design §5)
// ============================================================================

export type DashboardPersona = 'engineer' | 'manager' | 'dual' | 'unlinked'

/**
 * linked engineer (no org role)      -> 'engineer'  — My Day only
 * admin/manager (no engineer link)   -> 'manager'    — Org first
 * linked engineer AND admin/manager  -> 'dual'       — My Day first + compact org strip
 * neither (rare: no link, no role)   -> 'unlinked'   — fall back to Org-first shell
 */
export function derivePersona(opts: { linked: boolean; isOrgRole: boolean }): DashboardPersona {
  if (opts.linked && opts.isOrgRole) return 'dual'
  if (opts.linked) return 'engineer'
  if (opts.isOrgRole) return 'manager'
  return 'unlinked'
}

export function personaShowsMyDay(persona: DashboardPersona): boolean {
  return persona === 'engineer' || persona === 'dual'
}

export function personaShowsOrgStrip(persona: DashboardPersona): boolean {
  return persona === 'manager' || persona === 'dual' || persona === 'unlinked'
}

/** Dual-role gets the same org data, rendered as a condensed strip (2A operator-priority). */
export function personaOrgStripIsCompact(persona: DashboardPersona): boolean {
  return persona === 'dual'
}

// ============================================================================
// Date-window helpers (pulse strip "N events in last 7 days")
// ============================================================================

/** Count items whose created_at falls within the last `days` days (inclusive). */
export function countCreatedWithinDays<T extends { created_at?: string | null }>(
  items: T[],
  days: number,
  now: Date = new Date(),
): number {
  const cutoff = now.getTime() - days * 24 * 60 * 60 * 1000
  return items.reduce((count, item) => {
    if (!item.created_at) return count
    const t = new Date(item.created_at).getTime()
    return Number.isFinite(t) && t >= cutoff ? count + 1 : count
  }, 0)
}

// ============================================================================
// Risk trend / forecast (Org Command strip §4)
// ============================================================================

export type RiskTrendDirection = 'increasing' | 'stable' | 'decreasing' | null

/** Simple two-point forecast direction from the risk trends series (avg residual score). */
export function computeRiskTrendDirection(
  series: Array<{ avg_residual: number }> | undefined | null,
): RiskTrendDirection {
  if (!series || series.length < 2) return null
  const last = series[series.length - 1]?.avg_residual
  const prior = series[series.length - 2]?.avg_residual
  if (typeof last !== 'number' || typeof prior !== 'number') return null
  if (!Number.isFinite(last) || !Number.isFinite(prior)) return null
  const delta = last - prior
  if (Math.abs(delta) < 0.05) return 'stable'
  return delta > 0 ? 'increasing' : 'decreasing'
}

// ============================================================================
// Live Highlight Rail (locked design §1)
// ============================================================================

export type HighlightTone = 'critical' | 'warning' | 'info'

export interface HighlightChip {
  id: string
  label: string
  tone: HighlightTone
  href: string
}

export interface MyDayHighlightInputs {
  clearState?: Metric<PortalClearState>
  trainingGapCount?: Metric<number>
  myOverdueActions?: Metric<number>
}

export interface OrgHighlightInputs {
  unassignedTotal?: Metric<number>
  criticalIncidentsOpen?: Metric<number>
  outsideAppetiteRisks?: Metric<number>
  assetsOverdue?: Metric<number>
  assetsQuarantined?: Metric<number>
}

export interface HighlightInputs {
  myDay?: MyDayHighlightInputs
  org?: OrgHighlightInputs
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/**
 * Build priority chips for the Live Highlight Rail.
 *
 * Fail-honest by construction: a chip is only ever emitted from a Metric with
 * status 'ok' AND a truthy/positive value — an 'unavailable' metric (failed or
 * skipped fetch) never degrades into a fabricated zero-value chip.
 */
export function buildHighlightChips(inputs: HighlightInputs): HighlightChip[] {
  const chips: HighlightChip[] = []
  const md = inputs.myDay
  if (md) {
    if (md.clearState?.status === 'ok' && md.clearState.value === 'blocked') {
      chips.push({
        id: 'my-clear-blocked',
        label: 'Not clear to work',
        tone: 'critical',
        href: '/portal/tools',
      })
    } else if (md.clearState?.status === 'ok' && md.clearState.value === 'attention') {
      chips.push({
        id: 'my-clear-attention',
        label: 'Assets/van need attention',
        tone: 'warning',
        href: '/portal/tools',
      })
    }
    if (md.trainingGapCount?.status === 'ok' && md.trainingGapCount.value > 0) {
      chips.push({
        id: 'my-training-gap',
        label: `${plural(md.trainingGapCount.value, 'training module')} overdue`,
        tone: 'warning',
        href: '/portal/work#training',
      })
    }
    if (md.myOverdueActions?.status === 'ok' && md.myOverdueActions.value > 0) {
      chips.push({
        id: 'my-overdue-actions',
        label: `${plural(md.myOverdueActions.value, 'action')} overdue`,
        tone: 'critical',
        href: '/actions?view=my_overdue',
      })
    }
  }

  const org = inputs.org
  if (org) {
    if (org.criticalIncidentsOpen?.status === 'ok' && org.criticalIncidentsOpen.value > 0) {
      chips.push({
        id: 'org-critical-incidents',
        label: `${plural(org.criticalIncidentsOpen.value, 'critical incident')} open`,
        tone: 'critical',
        href: '/incidents',
      })
    }
    if (org.unassignedTotal?.status === 'ok' && org.unassignedTotal.value > 0) {
      chips.push({
        id: 'org-unassigned',
        label: `${plural(org.unassignedTotal.value, 'unassigned intake')}`,
        tone: 'warning',
        href: '/incidents?owner=unassigned',
      })
    }
    if (org.outsideAppetiteRisks?.status === 'ok' && org.outsideAppetiteRisks.value > 0) {
      chips.push({
        id: 'org-risk-appetite',
        label: `${plural(org.outsideAppetiteRisks.value, 'risk')} outside appetite`,
        tone: 'warning',
        href: '/risk-register?hero=outside_appetite',
      })
    }
    if (org.assetsQuarantined?.status === 'ok' && org.assetsQuarantined.value > 0) {
      chips.push({
        id: 'org-assets-quarantined',
        label: `${plural(org.assetsQuarantined.value, 'asset')} quarantined`,
        tone: 'critical',
        href: '/safety-assets/analytics',
      })
    }
    if (org.assetsOverdue?.status === 'ok' && org.assetsOverdue.value > 0) {
      chips.push({
        id: 'org-assets-overdue',
        label: `${plural(org.assetsOverdue.value, 'asset')} overdue`,
        tone: 'warning',
        href: '/safety-assets/analytics',
      })
    }
  }

  return chips
}
