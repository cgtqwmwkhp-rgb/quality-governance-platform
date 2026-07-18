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
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

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

  const filteredByType =
    summary && typeFilter !== 'all'
      ? Object.fromEntries(Object.entries(summary.by_type).filter(([key]) => key === typeFilter))
      : summary?.by_type ?? {}
  const filteredByStatus =
    summary && statusFilter !== 'all'
      ? Object.fromEntries(Object.entries(summary.by_status).filter(([key]) => key === statusFilter))
      : summary?.by_status ?? {}

  return (
    <div className="space-y-6" data-testid="asset-health-analytics">
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

      <div
        className="flex flex-col sm:flex-row gap-3"
        data-testid="asset-health-filters"
      >
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          aria-label="Filter by asset type"
          data-testid="asset-health-type-filter"
          className="w-full sm:w-56 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
        >
          <option value="all">All asset types</option>
          {summary
            ? Object.keys(summary.by_type).map((key) => (
                <option key={key} value={key}>
                  {key.split('_').join(' ')}
                </option>
              ))
            : null}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          data-testid="asset-health-status-filter"
          className="w-full sm:w-56 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
        >
          <option value="all">All statuses</option>
          {summary
            ? Object.keys(summary.by_status).map((key) => (
                <option key={key} value={key}>
                  {key.split('_').join(' ')}
                </option>
              ))
            : null}
        </select>
        <Button type="button" variant="outline" size="sm" data-testid="asset-health-filter-apply">
          Filter
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
                <p className="mt-1 text-3xl font-bold" data-testid="asset-health-kpi-total">
                  {summary.total}
                </p>
              </CardContent>
            </Card>
            <Card className="border-destructive/20 bg-destructive/5">
              <CardContent className="p-5">
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <AlertTriangle className="h-4 w-4 text-destructive" /> Overdue
                </p>
                <p className="mt-1 text-3xl font-bold text-destructive" data-testid="asset-health-kpi-overdue">
                  {summary.expiry_bands.overdue ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card className="border-warning/20 bg-warning/5">
              <CardContent className="p-5">
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <ShieldAlert className="h-4 w-4 text-warning" /> Quarantined
                </p>
                <p className="mt-1 text-3xl font-bold text-warning" data-testid="asset-health-kpi-quarantined">
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
                <CountList values={filteredByType} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Statuses</CardTitle>
              </CardHeader>
              <CardContent>
                <CountList values={filteredByStatus} />
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}

      {loading && !summary ? <p className="text-sm text-muted-foreground">Loading asset health metrics…</p> : null}
    </div>
  )
}
