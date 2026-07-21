import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Truck } from 'lucide-react'
import { portalComplianceApi, type PortalMyVan } from '../api/client'
import { Card } from '../components/ui/Card'
import { cn } from '../helpers/utils'

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return 'Not recorded'
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function emptyCopy(reason: string | null | undefined): string {
  switch (reason) {
    case 'no_driver_profile':
      return 'No driver profile is linked to your account yet. Ask fleet admin to link you.'
    case 'no_van':
      return 'No van is allocated to you right now.'
    case 'assignment_conflict':
      return 'Your van assignment does not match the vehicle registry. Contact fleet admin.'
    case 'multiple_assigned':
      return 'More than one vehicle is assigned to you. Contact fleet admin to fix this.'
    default:
      return 'Van status is unavailable.'
  }
}

export default function PortalMyVanPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<PortalMyVan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void portalComplianceApi
      .myVan()
      .then(setData)
      .catch(() => setError('Could not load your van status. Try again when online.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div data-testid="portal-my-van" className="min-h-screen bg-surface">
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/portal')}
            className="p-2 hover:bg-surface rounded-lg"
            aria-label="Back to portal home"
          >
            <ArrowLeft className="w-5 h-5 text-muted-foreground" />
          </button>
          <div>
            <h1 className="text-foreground font-semibold">My van checks</h1>
            <p className="text-muted-foreground text-xs">Daily and monthly checks · open faults</p>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 space-y-4">
        {loading && (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        )}

        {error && (
          <Card className="p-4 border-destructive/30 bg-destructive/5" data-testid="portal-van-error">
            <p className="text-sm text-destructive">{error}</p>
          </Card>
        )}

        {!loading && !error && data?.empty_reason && (
          <Card className="p-6 text-center" data-testid="portal-van-empty">
            <Truck className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-foreground font-medium">Van not available</p>
            <p className="text-sm text-muted-foreground mt-1">{emptyCopy(data.empty_reason)}</p>
          </Card>
        )}

        {!loading && !error && data && !data.empty_reason && (
          <>
            <Card className="p-4" data-testid="portal-van-summary">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Vehicle</p>
              <p className="text-xl font-semibold text-foreground mt-1">{data.vehicle_reg}</p>
              {data.assignment_conflict && (
                <p className="text-sm text-amber-700 dark:text-amber-400 mt-2">
                  Assignment needs admin review
                </p>
              )}
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Last daily</p>
                  <p className="text-foreground font-medium">{formatWhen(data.daily_last_at)}</p>
                  {data.daily_pass != null && (
                    <p className={cn('text-xs mt-0.5', data.daily_pass ? 'text-emerald-600' : 'text-destructive')}>
                      {data.daily_pass ? 'Pass' : 'Fail'}
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-muted-foreground">Last monthly</p>
                  <p className="text-foreground font-medium">{formatWhen(data.monthly_last_at)}</p>
                </div>
              </div>
            </Card>

            <div>
              <h2 className="text-sm font-semibold text-foreground mb-2">
                Outstanding faults ({data.defect_counts.total})
              </h2>
              {data.open_defects.length === 0 ? (
                <Card className="p-4">
                  <p className="text-sm text-muted-foreground">No open faults on this van.</p>
                </Card>
              ) : (
                <div className="space-y-2">
                  {data.open_defects.map((defect) => (
                    <Card key={defect.id} className="p-4" data-testid={`portal-defect-${defect.id}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-foreground">{defect.check_field}</p>
                        <span
                          className={cn(
                            'text-xs font-semibold px-2 py-0.5 rounded-md',
                            defect.priority === 'P1'
                              ? 'bg-destructive/10 text-destructive'
                              : 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
                          )}
                        >
                          {defect.priority}
                        </span>
                      </div>
                      {defect.check_value && (
                        <p className="text-sm text-muted-foreground mt-1">{defect.check_value}</p>
                      )}
                      {defect.notes && <p className="text-sm text-muted-foreground mt-1">{defect.notes}</p>}
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
