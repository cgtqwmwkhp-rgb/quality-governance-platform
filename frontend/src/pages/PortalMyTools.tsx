import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Wrench } from 'lucide-react'
import { portalComplianceApi, type PortalMyTools, type PortalToolBand } from '../api/client'
import { Card } from '../components/ui/Card'
import { cn } from '../helpers/utils'

const BAND_LABEL: Record<PortalToolBand, string> = {
  overdue: 'Overdue',
  due_30: 'Due ≤30 days',
  due_60: 'Due ≤60 days',
  due_90: 'Due ≤90 days',
  in_date: 'In date',
  none: 'No expiry',
  quarantined: 'Quarantined',
  decommissioned: 'Decommissioned',
}

function bandTone(band: PortalToolBand): string {
  if (band === 'quarantined' || band === 'overdue') return 'bg-destructive/10 text-destructive'
  if (band === 'due_30') return 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
  if (band === 'due_60' || band === 'due_90') return 'bg-info/10 text-info'
  return 'bg-muted text-muted-foreground'
}

export default function PortalMyTools() {
  const navigate = useNavigate()
  const [data, setData] = useState<PortalMyTools | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void portalComplianceApi
      .myTools()
      .then(setData)
      .catch(() => setError('Could not load your tools. Try again when online.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div data-testid="portal-my-tools" className="min-h-screen bg-surface">
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
            <h1 className="text-foreground font-semibold">My asset compliance</h1>
            <p className="text-muted-foreground text-xs">Assigned to you and kit on your van</p>
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
          <Card
            className="p-4 border-destructive/30 bg-destructive/5"
            data-testid="portal-tools-error"
          >
            <p className="text-sm text-destructive">{error}</p>
          </Card>
        )}

        {!loading && !error && data && data.items.length === 0 && (
          <Card className="p-6 text-center" data-testid="portal-tools-empty">
            <Wrench className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-foreground font-medium">No assets on your list</p>
            <p className="text-sm text-muted-foreground mt-1">
              No assets are assigned to you and no kit is linked to your van.
            </p>
          </Card>
        )}

        {!loading &&
          !error &&
          data?.items.map((item) => (
            <Card key={item.id} className="p-4" data-testid={`portal-tool-${item.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-foreground truncate">{item.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {item.asset_number}
                    {item.asset_type_name ? ` · ${item.asset_type_name}` : ''}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">{item.why_shown}</p>
                  {item.type_pending && (
                    <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                      Type pending approval
                    </p>
                  )}
                </div>
                <span
                  className={cn(
                    'shrink-0 text-xs font-semibold px-2 py-1 rounded-md',
                    bandTone(item.band),
                  )}
                >
                  {BAND_LABEL[item.band]}
                </span>
              </div>
              {item.expiry_date && (
                <p className="text-xs text-muted-foreground mt-3">
                  Expires {new Date(item.expiry_date).toLocaleDateString('en-GB')}
                </p>
              )}
            </Card>
          ))}
      </main>
    </div>
  )
}
