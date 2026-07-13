import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Link2,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import {
  competenceGapApi,
  type CompetenceGapAction,
  type GoldenThreadResponse,
} from '../api/competenceGapClient'
import { getApiErrorMessage } from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { Input } from '../components/ui/Input'
import { cn } from '../helpers/utils'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

const statusBadge = (status: string) => {
  if (status === 'open') return <Badge variant="submitted">Open</Badge>
  if (status === 'linked') return <Badge variant="outline">Linked</Badge>
  if (status === 'capa_created') return <Badge variant="warning">CAPA created</Badge>
  if (status === 'resolved') return <Badge variant="success">Resolved</Badge>
  if (status === 'dismissed') return <Badge variant="outline">Dismissed</Badge>
  return <Badge variant="outline">{status}</Badge>
}

const STATUS_OPTIONS = [
  { value: 'all', labelKey: 'competenceGaps.filter.all' },
  { value: 'open', labelKey: 'competenceGaps.filter.open' },
  { value: 'linked', labelKey: 'competenceGaps.filter.linked' },
  { value: 'capa_created', labelKey: 'competenceGaps.filter.capa_created' },
  { value: 'resolved', labelKey: 'competenceGaps.filter.resolved' },
  { value: 'dismissed', labelKey: 'competenceGaps.filter.dismissed' },
] as const

export function competenceGapActionHref(id: number): string {
  return `/workforce/competence-gaps?id=${id}`
}

export default function CompetenceGaps() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const focusId = searchParams.get('id')

  const [items, setItems] = useState<CompetenceGapAction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [actingId, setActingId] = useState<number | null>(null)
  const [engineerIdInput, setEngineerIdInput] = useState('')
  const [requirementIdInput, setRequirementIdInput] = useState('')
  const [thread, setThread] = useState<GoldenThreadResponse | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await competenceGapApi.list(
        statusFilter === 'all' ? undefined : { status: statusFilter },
      )
      setItems(response.data)
    } catch (err) {
      setError(reportFailure(err))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  const focused = useMemo(() => {
    if (!focusId) return null
    const id = Number(focusId)
    return items.find((item) => item.id === id) ?? null
  }, [focusId, items])

  const handleCreateCapa = async (id: number) => {
    setActingId(id)
    try {
      const response = await competenceGapApi.createCapa(id)
      toast.success(
        t('competenceGaps.toast.capa_created', {
          ref: response.data.action.reference_number,
        }),
      )
      await load()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActingId(null)
    }
  }

  const handleLink = async (id: number) => {
    const engineerId = Number(engineerIdInput)
    if (!Number.isFinite(engineerId) || engineerId <= 0) {
      toast.error(t('competenceGaps.toast.engineer_required'))
      return
    }
    const requirementRaw = requirementIdInput.trim()
    const requirementId = requirementRaw ? Number(requirementRaw) : undefined
    setActingId(id)
    try {
      await competenceGapApi.link(id, {
        engineer_id: engineerId,
        requirement_id:
          requirementId !== undefined && Number.isFinite(requirementId)
            ? requirementId
            : undefined,
      })
      toast.success(t('competenceGaps.toast.linked'))
      setEngineerIdInput('')
      setRequirementIdInput('')
      await load()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActingId(null)
    }
  }

  const handleResolve = async (id: number, dismiss = false) => {
    setActingId(id)
    try {
      await competenceGapApi.resolve(id, {
        dismiss,
        notes: dismiss
          ? t('competenceGaps.toast.dismiss_notes')
          : t('competenceGaps.toast.resolve_notes'),
      })
      toast.success(
        dismiss ? t('competenceGaps.toast.dismissed') : t('competenceGaps.toast.resolved'),
      )
      await load()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActingId(null)
    }
  }

  const handleGoldenThread = async (id: number) => {
    setActingId(id)
    try {
      const response = await competenceGapApi.goldenThread(id)
      setThread(response.data)
      setSearchParams({ id: String(id) })
    } catch (err) {
      reportFailure(err)
    } finally {
      setActingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {t('competenceGaps.title')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('competenceGaps.subtitle')}</p>
        </div>
        <div className="space-y-1.5 min-w-[12rem]">
          <label htmlFor="competence-gap-status" className="text-xs font-medium text-muted-foreground">
            {t('competenceGaps.filter.label')}
          </label>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger id="competence-gap-status" aria-label={t('competenceGaps.filter.label')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {t(opt.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {error && (
        <Card className="p-4 border-destructive/40 bg-destructive/5 flex gap-3 items-start">
          <AlertTriangle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-foreground">{t('competenceGaps.load_failed')}</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        </Card>
      )}

      {items.length === 0 && !error ? (
        <EmptyState
          icon={ShieldAlert}
          title={t('competenceGaps.empty.title')}
          description={t('competenceGaps.empty.description')}
        />
      ) : (
        <div className="space-y-3">
          {items.map((gap) => (
            <Card
              key={gap.id}
              className={cn(
                'p-4 space-y-3',
                focused?.id === gap.id && 'ring-2 ring-primary/40',
              )}
            >
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">
                      {t('competenceGaps.row.id', { id: gap.id })}
                    </span>
                    {statusBadge(gap.status)}
                    <Badge variant="outline">{gap.signal_type}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {gap.source_type}:{gap.source_id}
                    {gap.confidence != null ? ` · ${Math.round(gap.confidence * 100)}%` : ''}
                  </p>
                  {gap.rationale && (
                    <p className="text-sm text-foreground/90 line-clamp-3">{gap.rationale}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {t('competenceGaps.row.links', {
                      engineer: gap.engineer_id ?? '—',
                      requirement: gap.requirement_id ?? '—',
                      capa: gap.capa_action_id ?? '—',
                    })}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {gap.action_key && (
                    <Button variant="outline" size="sm" asChild>
                      <Link to={`/actions?action_key=${encodeURIComponent(gap.action_key)}`}>
                        {t('competenceGaps.actions.open_capa')}
                      </Link>
                    </Button>
                  )}
                  {!gap.capa_action_id &&
                    gap.status !== 'resolved' &&
                    gap.status !== 'dismissed' && (
                      <Button
                        size="sm"
                        disabled={actingId === gap.id}
                        onClick={() => void handleCreateCapa(gap.id)}
                      >
                        <CheckCircle2 className="w-4 h-4 mr-1" />
                        {t('competenceGaps.actions.create_capa')}
                      </Button>
                    )}
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={actingId === gap.id}
                    onClick={() => void handleGoldenThread(gap.id)}
                  >
                    {t('competenceGaps.actions.golden_thread')}
                  </Button>
                  {gap.status !== 'resolved' && gap.status !== 'dismissed' && (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={actingId === gap.id}
                        onClick={() => void handleResolve(gap.id, false)}
                      >
                        {t('competenceGaps.actions.resolve')}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={actingId === gap.id}
                        onClick={() => void handleResolve(gap.id, true)}
                      >
                        <XCircle className="w-4 h-4 mr-1" />
                        {t('competenceGaps.actions.dismiss')}
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {gap.status !== 'resolved' && gap.status !== 'dismissed' && !gap.engineer_id && (
                <div className="flex flex-col sm:flex-row gap-2 items-end border-t border-border pt-3">
                  <div className="space-y-1 flex-1">
                    <label className="text-xs text-muted-foreground" htmlFor={`eng-${gap.id}`}>
                      {t('competenceGaps.link.engineer_id')}
                    </label>
                    <Input
                      id={`eng-${gap.id}`}
                      value={engineerIdInput}
                      onChange={(e) => setEngineerIdInput(e.target.value)}
                      placeholder="42"
                    />
                  </div>
                  <div className="space-y-1 flex-1">
                    <label className="text-xs text-muted-foreground" htmlFor={`req-${gap.id}`}>
                      {t('competenceGaps.link.requirement_id')}
                    </label>
                    <Input
                      id={`req-${gap.id}`}
                      value={requirementIdInput}
                      onChange={(e) => setRequirementIdInput(e.target.value)}
                      placeholder={t('competenceGaps.link.requirement_optional')}
                    />
                  </div>
                  <Button
                    size="sm"
                    disabled={actingId === gap.id}
                    onClick={() => void handleLink(gap.id)}
                  >
                    <Link2 className="w-4 h-4 mr-1" />
                    {t('competenceGaps.actions.link')}
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {thread && (
        <Card className="p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-medium text-foreground">
              {t('competenceGaps.golden_thread.title', { id: thread.gap.id })}
            </h2>
            <Button variant="ghost" size="sm" onClick={() => setThread(null)}>
              {t('competenceGaps.golden_thread.close')}
            </Button>
          </div>
          <ol className="space-y-2 list-decimal list-inside">
            {thread.events.map((evt, idx) => (
              <li key={`${evt.event}-${idx}`} className="text-sm text-foreground">
                <span className="font-medium">{evt.event}</span>
                {evt.at ? (
                  <span className="text-muted-foreground"> · {evt.at}</span>
                ) : null}
                {evt.actor_id != null ? (
                  <span className="text-muted-foreground"> · actor {evt.actor_id}</span>
                ) : null}
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}
