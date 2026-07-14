import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, RefreshCw, ShieldAlert } from 'lucide-react'
import { assetHealthAnalyticsApi, type AssetHealthSummary } from '../api/assetHealthAnalyticsClient'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'

function CountList({ values }: { values: Record<string, number> }) {
  return (
    <dl className="space-y-2">
      {Object.entries(values).map(([label, count]) => (
        <div key={label} className="flex items-center justify-between border-b border-border pb-2 text-sm">
          <dt className="capitalize text-muted-foreground">{label.split('_').join(' ')}</dt>
          <dd className="font-semibold text-foreground">{count}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function AssetHealthAnalytics() {
  const [summary, setSummary] = useState<AssetHealthSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await assetHealthAnalyticsApi.getSummary()
      setSummary(response.data)
    } catch {
      setError('Could not load asset health metrics.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <Link
            to="/safety-assets"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Asset register
          </Link>
          <h1 className="text-3xl font-bold text-foreground">Asset health analytics</h1>
          <p className="mt-1 text-muted-foreground">
            Tenant-scoped safety asset counts by expiry band, type, and status.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadSummary()} disabled={loading}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {error ? (
        <Card>
          <CardContent className="p-5 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {summary ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="p-5">
                <p className="text-sm text-muted-foreground">Registered assets</p>
                <p className="mt-1 text-3xl font-bold">{summary.total}</p>
              </CardContent>
            </Card>
            <Card className="border-destructive/20 bg-destructive/5">
              <CardContent className="p-5">
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <AlertTriangle className="h-4 w-4 text-destructive" /> Overdue
                </p>
                <p className="mt-1 text-3xl font-bold text-destructive">
                  {summary.expiry_bands.overdue ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card className="border-warning/20 bg-warning/5">
              <CardContent className="p-5">
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <ShieldAlert className="h-4 w-4 text-warning" /> Quarantined
                </p>
                <p className="mt-1 text-3xl font-bold text-warning">
                  {summary.by_status.quarantined ?? 0}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Expiry bands</CardTitle>
              </CardHeader>
              <CardContent>
                <CountList values={summary.expiry_bands} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Asset types</CardTitle>
              </CardHeader>
              <CardContent>
                <CountList values={summary.by_type} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Statuses</CardTitle>
              </CardHeader>
              <CardContent>
                <CountList values={summary.by_status} />
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}

      {loading && !summary ? <p className="text-sm text-muted-foreground">Loading asset health metrics…</p> : null}
    </div>
  )
}
