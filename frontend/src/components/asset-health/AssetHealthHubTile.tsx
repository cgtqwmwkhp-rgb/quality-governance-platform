import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, PackageCheck, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { assetHealthAnalyticsApi, type AssetHealthSummary } from '../../api/assetHealthAnalyticsClient'
import { Card, CardContent } from '../ui/Card'

export function AssetHealthHubTile() {
  const [summary, setSummary] = useState<AssetHealthSummary | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    void assetHealthAnalyticsApi
      .getSummary()
      .then((response) => {
        if (active) setSummary(response.data)
      })
      .catch(() => {
        if (active) setUnavailable(true)
      })
    return () => {
      active = false
    }
  }, [])

  const overdue = summary?.expiry_bands.overdue ?? 0
  const quarantined = summary?.by_status.quarantined ?? 0

  return (
    <Link to="/safety-assets/analytics" aria-label="View asset health analytics">
      <Card hoverable className="h-full border-primary/20 bg-primary/5">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Asset health</p>
              <p className="mt-1 text-2xl font-bold text-foreground">
                {unavailable ? '—' : (summary?.total ?? '…')}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">registered safety assets</p>
            </div>
            <div className="rounded-xl bg-primary/10 p-3 text-primary">
              <PackageCheck className="h-5 w-5" />
            </div>
          </div>
          {unavailable ? (
            <p className="mt-4 text-xs text-muted-foreground">Metrics are currently unavailable.</p>
          ) : (
            <div className="mt-4 flex gap-3 text-xs">
              <span className="flex items-center gap-1 text-destructive">
                <AlertTriangle className="h-3.5 w-3.5" />
                {overdue} overdue
              </span>
              <span className="flex items-center gap-1 text-warning">
                <ShieldAlert className="h-3.5 w-3.5" />
                {quarantined} quarantined
              </span>
            </div>
          )}
          <span className="mt-4 flex items-center gap-1 text-sm font-medium text-primary">
            View asset health <ArrowRight className="h-4 w-4" />
          </span>
        </CardContent>
      </Card>
    </Link>
  )
}
