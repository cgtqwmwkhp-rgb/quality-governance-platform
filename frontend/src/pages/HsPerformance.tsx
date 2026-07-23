import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { hsKpisApi } from '../api/client'
import type { HsExcelImportDryRun, HsKpiSummary } from '../api/hsKpisClient'

const metrics = [
  ['injuries', 'Injuries'],
  ['near_misses', 'Near misses'],
  ['rtas', 'RTAs'],
  ['ltis', 'LTIs'],
  ['riddor', 'RIDDOR'],
  ['ltifr', 'LTIFR'],
  ['afr', 'AFR'],
] as const

export default function HsPerformance() {
  const [summary, setSummary] = useState<HsKpiSummary | null>(null)
  const [error, setError] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dryRun, setDryRun] = useState<HsExcelImportDryRun | null>(null)
  const [importMessage, setImportMessage] = useState('')
  const [importing, setImporting] = useState(false)

  const reload = () => {
    void hsKpisApi
      .getSummary()
      .then((result) => setSummary(result.data))
      .catch(() => setError('Could not load H&S performance data.'))
  }

  useEffect(() => {
    reload()
  }, [])

  const latest = summary?.by_year.length
    ? summary.by_year[summary.by_year.length - 1]
    : undefined

  const handleDryRun = async () => {
    if (!file) return
    setImporting(true)
    setImportMessage('')
    try {
      const result = await hsKpisApi.dryRunExcelImport(file)
      setDryRun(result.data)
    } catch {
      setImportMessage('Dry-run failed. Check the workbook format.')
    } finally {
      setImporting(false)
    }
  }

  const handleCommit = async () => {
    if (!file) return
    setImporting(true)
    setImportMessage('')
    try {
      const result = await hsKpisApi.commitExcelImport(file)
      setImportMessage(
        `Imported: incidents ${result.data.created.incident ?? 0}, near misses ${result.data.created.near_miss ?? 0}, complaints ${result.data.created.complaint ?? 0}, RTAs ${result.data.created.rta ?? 0}, skipped ${result.data.created.skipped ?? 0}.`,
      )
      setDryRun(null)
      reload()
    } catch {
      setImportMessage('Commit failed.')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">H&S Performance</h1>
        <p className="text-sm text-muted-foreground">
          LTIFR and AFR are shown per 100,000 hours worked (Excel SLT convention).
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4 xl:grid-cols-7">
        {metrics.map(([key, label]) => (
          <Card key={key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground">{label}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">{latest?.[key] ?? '—'}</CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Reporting years</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th>Year</th>
                <th>Hours</th>
                <th>Injuries</th>
                <th>Near misses</th>
                <th>RTAs</th>
                <th>LTIs</th>
                <th>RIDDOR</th>
                <th>LTIFR</th>
                <th>AFR</th>
              </tr>
            </thead>
            <tbody>
              {summary?.by_year.map((year) => (
                <tr key={year.reporting_year} className="border-b">
                  <td>{year.reporting_year}</td>
                  <td>{year.hours.toLocaleString()}</td>
                  <td>{year.injuries}</td>
                  <td>{year.near_misses}</td>
                  <td>{year.rtas}</td>
                  <td>{year.ltis}</td>
                  <td>{year.riddor}</td>
                  <td>{year.ltifr}</td>
                  <td>{year.afr}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import H&S workbook</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Upload Plantexpand H&S Incident Model .xlsx (Incident Log + RTA Log). Dry-run first; commit is
            idempotent on excel sheet/id keys.
          </p>
          <input
            type="file"
            accept=".xlsx"
            aria-label="H&S workbook file"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null)
              setDryRun(null)
              setImportMessage('')
            }}
          />
          <div className="flex gap-2">
            <Button type="button" variant="outline" disabled={!file || importing} onClick={handleDryRun}>
              Dry-run
            </Button>
            <Button type="button" disabled={!file || importing} onClick={handleCommit}>
              Commit import
            </Button>
          </div>
          {dryRun && (
            <div className="text-sm space-y-1">
              <p>
                Planned creates — incidents {dryRun.counts.incident ?? 0}, near misses{' '}
                {dryRun.counts.near_miss ?? 0}, complaints {dryRun.counts.complaint ?? 0}, RTAs{' '}
                {dryRun.counts.rta ?? 0}, already imported {dryRun.counts.skip_existing ?? 0}
              </p>
              {dryRun.warnings.length > 0 && (
                <p className="text-muted-foreground">Warnings: {dryRun.warnings.slice(0, 5).join(' · ')}</p>
              )}
            </div>
          )}
          {importMessage && <p className="text-sm">{importMessage}</p>}
        </CardContent>
      </Card>
    </div>
  )
}
