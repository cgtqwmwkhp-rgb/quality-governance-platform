import { useEffect, useState } from 'react'
import { Loader2, Save } from 'lucide-react'
import { getApiErrorMessage, hsKpisApi } from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import type { HsReportingPeriodRow } from '../../api/hsKpisClient'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'

type DraftRow = {
  reporting_year: number
  period_start: string
  period_end: string
  average_fte: string
  hours_per_fte_year: string
  manual_hours: string
  hours: number
  hours_source: 'manual' | 'calculated'
  /** True once the admin edits Annual hours; stops FTE/date edits from overwriting it. */
  hoursLocked: boolean
}

function calculatedHours(row: Pick<DraftRow, 'period_start' | 'period_end' | 'average_fte' | 'hours_per_fte_year'>): number {
  const averageFte = Number(row.average_fte)
  const hoursPerFte = Number(row.hours_per_fte_year)
  if (
    !Number.isFinite(averageFte) ||
    averageFte <= 0 ||
    !Number.isFinite(hoursPerFte) ||
    hoursPerFte <= 0 ||
    !row.period_start ||
    !row.period_end ||
    row.period_end < row.period_start
  ) {
    return 0
  }
  const start = Date.parse(`${row.period_start}T00:00:00Z`)
  const end = Date.parse(`${row.period_end}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end)) return 0
  const days = Math.max(0, Math.round((end - start) / 86_400_000) + 1)
  return Math.round(((averageFte * hoursPerFte * days) / 365) * 100) / 100
}

function toDraft(row: HsReportingPeriodRow): DraftRow {
  return {
    reporting_year: row.reporting_year,
    period_start: row.period_start.slice(0, 10),
    period_end: row.period_end.slice(0, 10),
    average_fte: String(row.average_fte),
    hours_per_fte_year: String(row.hours_per_fte_year),
    // Prefer showing the effective board hours in the editable field.
    manual_hours: String(row.manual_hours ?? row.hours),
    hours: row.hours,
    hours_source: row.hours_source,
    // Calculated rows stay linked to FTE/dates until the admin edits Annual hours.
    hoursLocked: row.hours_source === 'manual',
  }
}

export default function HsReportingHours() {
  const [rows, setRows] = useState<DraftRow[]>([])
  const [loading, setLoading] = useState(true)
  const [savingYear, setSavingYear] = useState<number | null>(null)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const result = await hsKpisApi.listPeriods()
      setRows(result.data.items.map(toDraft))
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not load H&S reporting hours.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const updateRow = (year: number, patch: Partial<DraftRow>) => {
    setRows((current) =>
      current.map((row) => {
        if (row.reporting_year !== year) return row
        const next = { ...row, ...patch }
        const fteOrDatesChanged =
          patch.period_start !== undefined ||
          patch.period_end !== undefined ||
          patch.average_fte !== undefined ||
          patch.hours_per_fte_year !== undefined
        if (fteOrDatesChanged && !next.hoursLocked) {
          const estimate = calculatedHours(next)
          if (estimate > 0) {
            next.manual_hours = String(estimate)
          }
        }
        return next
      }),
    )
  }

  const saveRow = async (row: DraftRow) => {
    const manualHours = Number(row.manual_hours)
    const averageFte = Number(row.average_fte)
    const hoursPerFte = Number(row.hours_per_fte_year)
    if (!Number.isFinite(manualHours) || manualHours <= 0) {
      toast.error(`Enter a valid annual hours figure for ${row.reporting_year}`)
      return
    }
    if (!Number.isFinite(averageFte) || averageFte <= 0) {
      toast.error(`Enter a valid average FTE for ${row.reporting_year}`)
      return
    }
    if (!row.period_start || !row.period_end || row.period_end < row.period_start) {
      toast.error(`Check period dates for ${row.reporting_year}`)
      return
    }

    setSavingYear(row.reporting_year)
    try {
      const result = await hsKpisApi.putPeriod(row.reporting_year, {
        reporting_year: row.reporting_year,
        period_start: row.period_start,
        period_end: row.period_end,
        average_fte: averageFte,
        hours_per_fte_year: Number.isFinite(hoursPerFte) && hoursPerFte > 0 ? hoursPerFte : 2124,
        manual_hours: manualHours,
      })
      setRows((current) =>
        current.map((item) => (item.reporting_year === row.reporting_year ? toDraft(result.data) : item)),
      )
      toast.success(`${row.reporting_year} hours saved — H&S Performance board will use ${manualHours.toLocaleString()}`)
    } catch (err) {
      toast.error(getApiErrorMessage(err, `Could not save ${row.reporting_year} hours`))
    } finally {
      setSavingYear(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">H&S reporting hours</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manual annual hours for each reporting year. These figures drive the Hours column and
          LTIFR/AFR rates on Analytics → H&S Performance.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Reporting years</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading periods…
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-3">Year</th>
                    <th className="py-2 pr-3">Period start</th>
                    <th className="py-2 pr-3">Period end</th>
                    <th className="py-2 pr-3">Average FTE</th>
                    <th className="py-2 pr-3">Annual hours</th>
                    <th className="py-2 pr-3">Board source</th>
                    <th className="py-2"> </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const estimate = calculatedHours(row)
                    return (
                      <tr key={row.reporting_year} className="border-b align-top">
                        <td className="py-3 pr-3 font-medium">{row.reporting_year}</td>
                        <td className="py-3 pr-3">
                          <Input
                            id={`hs-period-start-${row.reporting_year}`}
                            type="date"
                            value={row.period_start}
                            onChange={(e) => updateRow(row.reporting_year, { period_start: e.target.value })}
                            className="w-[11rem]"
                          />
                        </td>
                        <td className="py-3 pr-3">
                          <Input
                            id={`hs-period-end-${row.reporting_year}`}
                            type="date"
                            value={row.period_end}
                            onChange={(e) => updateRow(row.reporting_year, { period_end: e.target.value })}
                            className="w-[11rem]"
                          />
                        </td>
                        <td className="py-3 pr-3">
                          <Input
                            id={`hs-fte-${row.reporting_year}`}
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={row.average_fte}
                            onChange={(e) => updateRow(row.reporting_year, { average_fte: e.target.value })}
                            className="w-[7rem]"
                          />
                        </td>
                        <td className="py-3 pr-3">
                          <label className="sr-only" htmlFor={`hs-hours-${row.reporting_year}`}>
                            Annual hours {row.reporting_year}
                          </label>
                          <Input
                            id={`hs-hours-${row.reporting_year}`}
                            type="number"
                            min={1}
                            step={0.01}
                            value={row.manual_hours}
                            onChange={(e) =>
                              updateRow(row.reporting_year, {
                                manual_hours: e.target.value,
                                hoursLocked: true,
                              })
                            }
                            className="w-[10rem]"
                          />
                          {estimate > 0 && (
                            <button
                              type="button"
                              className="mt-1 block text-xs text-muted-foreground underline-offset-2 hover:underline"
                              onClick={() =>
                                updateRow(row.reporting_year, {
                                  manual_hours: String(estimate),
                                  hoursLocked: false,
                                })
                              }
                            >
                              FTE estimate: {estimate.toLocaleString()}
                            </button>
                          )}
                        </td>
                        <td className="py-3 pr-3 text-muted-foreground">
                          {row.hours_source === 'manual' ? 'Manual' : 'Calculated'}
                        </td>
                        <td className="py-3">
                          <Button
                            type="button"
                            size="sm"
                            disabled={savingYear === row.reporting_year}
                            onClick={() => void saveRow(row)}
                          >
                            {savingYear === row.reporting_year ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Save className="h-4 w-4" />
                            )}
                            <span className="ml-1.5">Save</span>
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-muted-foreground mt-4">
            Period dates control which incidents/near misses/RTAs are counted for that year. Annual hours
            are the denominator for LTIFR and AFR (per 100,000 hours). Changing FTE or dates updates Annual
            hours until you edit that figure directly; click the FTE estimate to re-sync.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
