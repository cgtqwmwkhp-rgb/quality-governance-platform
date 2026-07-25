import { Link } from 'react-router-dom'
import type { CampaignComplianceRow } from '../api/documentCampaignClient'
import { cn } from '../helpers/utils'
import {
  buildCampaignResultsHref,
  campaignRingLabel,
  campaignRingPercent,
  campaignRingTone,
  type CampaignRingTone as Tone,
} from './documentCampaignHelpers'

const TONE_TEXT_CLASS: Record<Tone, string> = {
  success: 'text-success',
  warning: 'text-warning',
  destructive: 'text-destructive',
}

const VIEWBOX_SIZE = 36
const RADIUS = 15
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export interface CampaignRingProps {
  documentId: number
  row: CampaignComplianceRow
  size?: number
  className?: string
}

/** Small circular completion indicator that replaces the campaign text badge (List 360, P1). */
export function CampaignRing({ documentId, row, size = 32, className }: CampaignRingProps) {
  const percent = campaignRingPercent(row)
  const tone = campaignRingTone(row)
  const label = campaignRingLabel(row)
  const dashOffset = CIRCUMFERENCE * (1 - percent / 100)

  return (
    <Link
      to={buildCampaignResultsHref(documentId, row.campaign_id)}
      onClick={(event) => event.stopPropagation()}
      title={label}
      aria-label={label}
      className={cn('relative inline-flex shrink-0 items-center justify-center rounded-full', className)}
      style={{ width: size, height: size }}
      data-testid={`document-campaign-ring-${documentId}`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${VIEWBOX_SIZE} ${VIEWBOX_SIZE}`}
        className="-rotate-90 transform"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <circle
          cx={VIEWBOX_SIZE / 2}
          cy={VIEWBOX_SIZE / 2}
          r={RADIUS}
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          className="text-muted"
        />
        <circle
          cx={VIEWBOX_SIZE / 2}
          cy={VIEWBOX_SIZE / 2}
          r={RADIUS}
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          className={cn('transition-[stroke-dashoffset] duration-300', TONE_TEXT_CLASS[tone])}
        />
      </svg>
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-0 flex items-center justify-center font-semibold leading-none',
          TONE_TEXT_CLASS[tone],
        )}
        style={{ fontSize: Math.max(8, Math.round(size * 0.3)) }}
      >
        {percent}
      </span>
    </Link>
  )
}
