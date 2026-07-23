import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { hsKpisApi } from '../api/client'
import type { HsKpiSummary } from '../api/hsKpisClient'

const metrics = [
  ['injuries', 'Injuries'], ['near_misses', 'Near misses'], ['rtas', 'RTAs'], ['ltis', 'LTIs'],
  ['riddor', 'RIDDOR'], ['ltifr', 'LTIFR'], ['afr', 'AFR'],
] as const

export default function HsPerformance() {
  const [summary, setSummary] = useState<HsKpiSummary | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    void hsKpisApi.getSummary().then((result) => setSummary(result.data)).catch(() => setError('Could not load H&S performance data.'))
  }, [])

  const latest = summary?.by_year.at(-1)
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">H&S Performance</h1>
        <p className="text-sm text-muted-foreground">LTIFR and AFR are shown per 100,000 hours worked.</p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4 xl:grid-cols-7">
        {metrics.map(([key, label]) => (
          <Card key={key}>
            <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">{label}</CardTitle></CardHeader>
            <CardContent className="text-2xl font-semibold">{latest?.[key] ?? '—'}</CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>Reporting years</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-muted-foreground"><th>Year</th><th>Hours</th><th>Injuries</th><th>Near misses</th><th>RTAs</th><th>LTIs</th><th>RIDDOR</th><th>LTIFR</th><th>AFR</th></tr></thead>
            <tbody>{summary?.by_year.map((year) => <tr key={year.reporting_year} className="border-b"><td>{year.reporting_year}</td><td>{year.hours.toLocaleString()}</td><td>{year.injuries}</td><td>{year.near_misses}</td><td>{year.rtas}</td><td>{year.ltis}</td><td>{year.riddor}</td><td>{year.ltifr}</td><td>{year.afr}</td></tr>)}</tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
