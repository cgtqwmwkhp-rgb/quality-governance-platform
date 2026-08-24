/**
 * Library WK-1 / L-48 — portal CURRENT coverage badge (scaffold).
 *
 * 360px-safe: sits in the existing max-w-lg PortalReading header row.
 * No editor. CEL/coverage % wiring waits for WI-1 LIVE.
 *
 * Labels are resolved by the caller (i18n) so this module stays pure for vitest.
 */

import {
  resolvePortalCoverageBadge,
  type PortalCoverageBadgeSource,
} from './portalCoverageBadgeHelpers'

export interface PortalCoverageBadgeProps {
  source?: PortalCoverageBadgeSource | null
  /** Already-translated label from the parent (PortalReading). */
  label: string
  /** Optional version text shown beside CURRENT for honesty. */
  showVersion?: boolean
  className?: string
}

const VARIANT_CLASS: Record<string, string> = {
  success: 'border-transparent bg-success/10 text-success',
  warning: 'border-transparent bg-warning/10 text-warning',
  secondary: 'border-transparent bg-secondary text-secondary-foreground',
  outline: 'border-border text-foreground bg-transparent',
}

export function PortalCoverageBadge({
  source,
  label,
  showVersion = true,
  className = '',
}: PortalCoverageBadgeProps) {
  const model = resolvePortalCoverageBadge(source)
  if (!model.visible) return null

  const version =
    showVersion && source?.document_version
      ? String(source.document_version).trim()
      : ''

  const variantClass = VARIANT_CLASS[model.variant] ?? VARIANT_CLASS.outline

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${variantClass} ${className}`.trim()}
      data-testid="portal-coverage-badge"
      data-issue-state={model.state}
      title={version ? `Issue ${version}` : undefined}
    >
      <span className="max-w-[9rem] truncate sm:max-w-none">{label}</span>
      {model.state === 'CURRENT' && version ? (
        <span
          className="opacity-80 truncate max-w-[4.5rem]"
          data-testid="portal-coverage-badge-version"
        >
          v{version}
        </span>
      ) : null}
    </span>
  )
}
