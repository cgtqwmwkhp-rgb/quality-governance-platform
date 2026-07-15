export type WorkforcePassportState =
  | 'verified'
  | 'pending_verification'
  | 'expired'
  | 'missing'

export interface WorkforcePassportCardProps {
  workerName: string
  passportReference?: string
  state: WorkforcePassportState
  expiresOn?: string
  gateReason?: string
}

const STATE_LABELS: Record<WorkforcePassportState, string> = {
  verified: 'Verified — start permitted',
  pending_verification: 'Pending verification — start blocked',
  expired: 'Expired — start blocked',
  missing: 'No passport — start blocked',
}

/**
 * Presentational stub for the QR workforce passport and its hard start-gate
 * outcome. The future route adapter supplies server-evaluated status only.
 */
export function WorkforcePassportCard({
  workerName,
  passportReference,
  state,
  expiresOn,
  gateReason,
}: WorkforcePassportCardProps) {
  const allowed = state === 'verified'

  return (
    <section
      aria-label="workforce.passport.card"
      className="rounded-lg border border-gray-200 bg-white p-4"
      data-gate-state={allowed ? 'allowed' : 'blocked'}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{workerName}</h2>
          <p className="mt-1 text-xs text-gray-600">{STATE_LABELS[state]}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            allowed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}
        >
          {allowed ? 'Gate clear' : 'Gate blocked'}
        </span>
      </div>

      <dl className="mt-4 grid gap-2 text-xs text-gray-700">
        <div className="flex justify-between gap-4">
          <dt>Passport reference</dt>
          <dd>{passportReference || 'Not issued'}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt>Expires</dt>
          <dd>{expiresOn || 'Not recorded'}</dd>
        </div>
        {!allowed && gateReason && (
          <div className="rounded bg-red-50 p-2 text-red-800" role="alert">
            {gateReason}
          </div>
        )}
      </dl>
    </section>
  )
}
