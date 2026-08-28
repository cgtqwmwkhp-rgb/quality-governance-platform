import { Link } from 'react-router-dom'
import { lookupRegister } from './registerCatalogueHonesty'

const INCIDENT_TYPE_LABEL: Record<string, string> = {
  injury: 'injury',
  near_miss: 'near miss',
  hazard: 'hazard',
  property_damage: 'property damage',
  environmental: 'environmental',
  security: 'security',
  quality: 'quality',
  other: 'other',
}

type RegisterCaptionBannerProps = {
  registerParam: string | null
  typeParam?: string | null
  serverTotal?: number | null
  showServerTotal?: boolean
}

/**
 * Caption under a live list H1. Unknown ?register= renders nothing
 * and must not change the list.
 */
export default function RegisterCaptionBanner({
  registerParam,
  typeParam,
  serverTotal,
  showServerTotal = false,
}: RegisterCaptionBannerProps) {
  const entry = lookupRegister(registerParam)
  if (!entry) {
    return null
  }

  const typeLabel = typeParam ? INCIDENT_TYPE_LABEL[typeParam] : undefined
  const applied = typeLabel
    ? `Server filter: type=${typeParam} (${typeLabel}).`
    : 'No type filter — this is the module list, captioned.'

  return (
    <aside
      className="mt-3 rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm"
      data-testid="register-caption-banner"
      aria-label="Register caption"
    >
      <p className="font-medium text-foreground">
        {entry.docRef} · {entry.title}
      </p>
      <p className="text-muted-foreground mt-1">
        Owner: {entry.ownerRole}. {applied}
        {showServerTotal && typeof serverTotal === 'number'
          ? ` Server total: ${serverTotal}.`
          : ''}
      </p>
      {entry.note ? <p className="text-muted-foreground mt-1">{entry.note}</p> : null}
      <p className="mt-2">
        <Link to="/registers" className="text-primary underline-offset-2 hover:underline">
          Back to Registers
        </Link>
      </p>
    </aside>
  )
}
