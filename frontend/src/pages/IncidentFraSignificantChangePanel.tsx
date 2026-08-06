/**
 * Banner on Incident Detail: create / open / dismiss FRA after significant change.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Loader2 } from 'lucide-react'
import api, {
  complianceScheduleApi,
  getApiErrorMessage,
  type Incident,
} from '../api/client'
import { safetyAssetsApi, type SafetyLocation } from '../api/safetyAssetsClient'
import { Button } from '../components/ui/Button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { toast } from '../contexts/ToastContext'
import { trackError } from '../utils/errorTracker'
import {
  dismissFraSignificantChange,
  isFraSignificantChangeDismissed,
  shouldShowFraSignificantChangePrompt,
} from './incidentFraSignificantChange'
import { fraSigChangeCopy } from './incidentFraSignificantChangeI18n'

type FraSignificantChangeResponse = {
  created: boolean
  requirement_id: number
  reference_number: string
  location_id: number
  incident_id: number
  suggested_location_id?: number | null
  href: string
}

const ELIGIBLE_KINDS = new Set(['premises', 'office'])

export type IncidentFraSignificantChangePanelProps = {
  incident: Incident
  flagEnabled: boolean
}

export function IncidentFraSignificantChangePanel({
  incident,
  flagEnabled,
}: IncidentFraSignificantChangePanelProps) {
  const { i18n } = useTranslation()
  const copy = fraSigChangeCopy(i18n.language)
  const navigate = useNavigate()

  const [dismissed, setDismissed] = useState(() =>
    typeof incident.id === 'number' ? isFraSignificantChangeDismissed(incident.id) : false,
  )
  const [locations, setLocations] = useState<SafetyLocation[]>([])
  const [locationId, setLocationId] = useState<string>('')
  const [existingFraId, setExistingFraId] = useState<number | null>(null)
  const [loadingLocations, setLoadingLocations] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const visible = shouldShowFraSignificantChangePrompt(incident, {
    flagEnabled,
    dismissed,
  })

  const loadLocations = useCallback(async () => {
    setLoadingLocations(true)
    try {
      const [premisesRes, officeRes] = await Promise.all([
        safetyAssetsApi.listLocations({
          page: 1,
          page_size: 200,
          kind: 'premises',
          is_active: true,
        }),
        safetyAssetsApi.listLocations({
          page: 1,
          page_size: 200,
          kind: 'office',
          is_active: true,
        }),
      ])
      const merged = [...(premisesRes.data.items ?? []), ...(officeRes.data.items ?? [])].filter(
        (loc) => ELIGIBLE_KINDS.has(String(loc.kind || '').toLowerCase()),
      )
      merged.sort((a, b) => a.name.localeCompare(b.name))
      setLocations(merged)

      let suggested: number | null = null
      if (incident.asset_id) {
        try {
          const assetRes = await safetyAssetsApi.getAsset(incident.asset_id)
          const assetLoc = assetRes.data.location_id
          if (
            assetLoc != null &&
            merged.some((loc) => loc.id === assetLoc)
          ) {
            suggested = assetLoc
          }
        } catch {
          // Prefill is best-effort
        }
      }
      if (suggested != null) {
        setLocationId(String(suggested))
      }
    } catch (err) {
      trackError(err, {
        component: 'IncidentFraSignificantChangePanel',
        action: 'loadLocations',
      })
      toast.error(getApiErrorMessage(err, copy.loadLocationsFailed))
      setLocations([])
    } finally {
      setLoadingLocations(false)
    }
  }, [copy.loadLocationsFailed, incident.asset_id])

  useEffect(() => {
    if (!visible) return
    void loadLocations()
  }, [visible, loadLocations])

  useEffect(() => {
    if (!locationId || !visible) {
      setExistingFraId(null)
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const res = await complianceScheduleApi.getLocationCoverageGaps()
        if (cancelled) return
        const locId = Number(locationId)
        const row = res.data.items?.find((item) => item.location_id === locId)
        setExistingFraId(row?.fra_requirement_id ?? null)
      } catch {
        if (!cancelled) setExistingFraId(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [locationId, visible])

  const selectedLabel = useMemo(() => {
    const id = Number(locationId)
    return locations.find((loc) => loc.id === id)?.name
  }, [locationId, locations])

  const handleDismiss = () => {
    dismissFraSignificantChange(incident.id)
    setDismissed(true)
  }

  const handleCreate = async () => {
    if (!locationId) return
    setSubmitting(true)
    try {
      const res = await api.post<FraSignificantChangeResponse>(
        `/api/v1/incidents/${incident.id}/fra-significant-change`,
        { location_id: Number(locationId) },
        { suppressErrorToast: true },
      )
      const data = res.data
      toast.success(data.created ? copy.createSuccess : copy.linkSuccess)
      navigate(data.href || `/compliance-schedule/${data.requirement_id}`)
    } catch (err) {
      trackError(err, {
        component: 'IncidentFraSignificantChangePanel',
        action: 'createFra',
      })
      toast.error(getApiErrorMessage(err, copy.createFailed))
    } finally {
      setSubmitting(false)
    }
  }

  const handleOpenExisting = () => {
    if (existingFraId == null) return
    navigate(`/compliance-schedule/${existingFraId}`)
  }

  if (!visible) return null

  return (
    <div
      className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950"
      data-testid="incident-fra-significant-change"
      role="region"
      aria-label={copy.title}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h3 className="text-sm font-semibold">{copy.title}</h3>
            <p className="mt-1 text-sm text-amber-900/90">{copy.subtitle}</p>
          </div>

          <div className="max-w-md space-y-1.5">
            <label className="text-xs font-medium text-amber-900" htmlFor="fra-sigchange-location">
              {copy.locationLabel}
            </label>
            {loadingLocations ? (
              <div className="flex items-center gap-2 text-sm text-amber-800">
                <Loader2 className="h-4 w-4 animate-spin" />
                {copy.creating}
              </div>
            ) : locations.length === 0 ? (
              <p className="text-sm text-amber-800">{copy.noLocations}</p>
            ) : (
              <Select value={locationId || undefined} onValueChange={setLocationId}>
                <SelectTrigger id="fra-sigchange-location" data-testid="fra-sigchange-location">
                  <SelectValue placeholder={copy.locationPlaceholder}>
                    {selectedLabel || copy.locationPlaceholder}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {locations.map((loc) => (
                    <SelectItem key={loc.id} value={String(loc.id)}>
                      {loc.name} ({loc.kind})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              disabled={!locationId || submitting || existingFraId != null}
              onClick={() => void handleCreate()}
              data-testid="fra-sigchange-create"
            >
              {submitting ? copy.creating : copy.createFra}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={existingFraId == null || submitting}
              onClick={handleOpenExisting}
              data-testid="fra-sigchange-open"
            >
              {copy.openExisting}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={submitting}
              onClick={handleDismiss}
              data-testid="fra-sigchange-dismiss"
            >
              {copy.dismiss}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default IncidentFraSignificantChangePanel
