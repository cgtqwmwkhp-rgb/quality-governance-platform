/**
 * UpstreamDegradedBanner — Path-to-10 Preferred S10 degraded UX for OCR/AI/blob.
 *
 * Controlled mode: pass openCircuits / halfOpenCircuits / message.
 * Optional pollReadyz: reads public /readyz upstream.ai.circuits without
 * inventing secrets or requiring client.ts changes.
 */

import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { API_BASE_URL } from '../config/apiBase'

export type UpstreamCircuitState = 'closed' | 'open' | 'half_open' | 'unregistered' | string

export type UpstreamDegradedBannerProps = {
  /** Controlled: circuit names currently OPEN. */
  openCircuits?: string[]
  /** Controlled: circuit names currently HALF_OPEN. */
  halfOpenCircuits?: string[]
  /** Controlled override message. */
  message?: string | null
  /** When true, poll /readyz for upstream.ai.circuits state. */
  pollReadyz?: boolean
  /** Poll interval ms (default 30s). */
  pollIntervalMs?: number
  className?: string
}

type CircuitHealth = {
  name?: string
  state?: UpstreamCircuitState
}

function buildMessage(open: string[], halfOpen: string[], override?: string | null): string {
  if (override) return override
  if (open.length && halfOpen.length) {
    return `Upstream OCR/AI services are degraded (open: ${open.join(', ')}; probing: ${halfOpen.join(', ')}). Import may be delayed — retry shortly.`
  }
  if (open.length) {
    return `Upstream OCR/AI services are temporarily unavailable (circuit open: ${open.join(', ')}). Import may be delayed — retry shortly.`
  }
  if (halfOpen.length) {
    return `Upstream OCR/AI services are recovering (probing: ${halfOpen.join(', ')}). New import calls may still fail — retry shortly.`
  }
  return ''
}

function parseReadyzCircuits(payload: unknown): { open: string[]; halfOpen: string[] } {
  const open: string[] = []
  const halfOpen: string[] = []
  if (!payload || typeof payload !== 'object') return { open, halfOpen }

  const root = payload as Record<string, unknown>
  const upstream = (root.upstream ?? {}) as Record<string, unknown>
  const ai = (upstream.ai ?? {}) as Record<string, unknown>
  const circuitsRaw = ai.circuits

  let entries: CircuitHealth[] = []
  if (Array.isArray(circuitsRaw)) {
    entries = circuitsRaw as CircuitHealth[]
  } else if (circuitsRaw && typeof circuitsRaw === 'object') {
    entries = Object.values(circuitsRaw as Record<string, CircuitHealth>)
  }

  for (const row of entries) {
    const name = typeof row?.name === 'string' ? row.name : ''
    const state = row?.state
    if (!name) continue
    if (state === 'open') open.push(name)
    else if (state === 'half_open') halfOpen.push(name)
  }
  return { open, halfOpen }
}

export function UpstreamDegradedBanner({
  openCircuits,
  halfOpenCircuits,
  message,
  pollReadyz = false,
  pollIntervalMs = 30_000,
  className = '',
}: UpstreamDegradedBannerProps) {
  const [polledOpen, setPolledOpen] = useState<string[]>([])
  const [polledHalfOpen, setPolledHalfOpen] = useState<string[]>([])

  const refresh = useCallback(async () => {
    if (!pollReadyz) return
    try {
      const res = await fetch(`${API_BASE_URL}/readyz`, {
        method: 'GET',
        credentials: 'same-origin',
      })
      if (!res.ok) return
      const json: unknown = await res.json()
      const parsed = parseReadyzCircuits(json)
      setPolledOpen(parsed.open)
      setPolledHalfOpen(parsed.halfOpen)
    } catch {
      // Fail closed for UI: do not claim degradation on probe errors.
    }
  }, [pollReadyz])

  useEffect(() => {
    if (!pollReadyz) return
    void refresh()
    const id = window.setInterval(() => void refresh(), pollIntervalMs)
    return () => window.clearInterval(id)
  }, [pollReadyz, pollIntervalMs, refresh])

  const open = openCircuits ?? polledOpen
  const halfOpen = halfOpenCircuits ?? polledHalfOpen
  const degraded = open.length > 0 || halfOpen.length > 0
  if (!degraded) return null

  const text = buildMessage(open, halfOpen, message)

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="upstream-degraded-banner"
      className={`flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 ${className}`}
    >
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
      <div className="space-y-1">
        <p className="font-medium">Upstream services degraded</p>
        <p>{text}</p>
      </div>
    </div>
  )
}

export default UpstreamDegradedBanner
