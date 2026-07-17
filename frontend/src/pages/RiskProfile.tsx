import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft,
  AlertTriangle,
  ClipboardList,
  GitBranch,
  History,
  Loader2,
  MessageSquare,
  Plus,
  TrendingDown,
  TrendingUp,
  Minus,
} from 'lucide-react'
import { getApiErrorMessage, riskRegisterApi, UserSearchResult } from '../api/client'
import type {
  RiskActionItem,
  RiskActivityEvent,
  RiskAssessPayload,
  RiskNote,
  RiskProfile,
  RiskTrendPoint,
  RiskUpstreamItem,
} from '../api/riskRegisterClient'
import { buildRiskCreateActionHref } from '../api/riskRegisterClient'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Card, CardContent } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { UserEmailSearch } from '../components/UserEmailSearch'
import { trackError } from '../utils/errorTracker'

const MAX_NOTE_BODY_CHARS = 16000

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatRelativeTime(iso?: string | null): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const sec = Math.round((Date.now() - t) / 1000)
  if (sec < 45) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const h = Math.round(min / 60)
  if (h < 48) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 14) return `${d}d ago`
  return ''
}
function formatDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function levelBadgeVariant(
  level?: string | null,
): 'destructive' | 'warning' | 'secondary' | 'success' {
  switch ((level || '').toLowerCase()) {
    case 'critical':
    case 'high':
      return 'destructive'
    case 'medium':
      return 'warning'
    case 'low':
      return 'success'
    default:
      return 'secondary'
  }
}

function trendBadgeVariant(
  trend?: string | null,
): 'destructive' | 'warning' | 'secondary' | 'success' {
  switch (trend) {
    case 'increasing':
      return 'destructive'
    case 'decreasing':
      return 'success'
    default:
      return 'secondary'
  }
}

function TrendIcon({ trend }: { trend?: string | null }) {
  if (trend === 'increasing') return <TrendingUp className="h-4 w-4" aria-hidden />
  if (trend === 'decreasing') return <TrendingDown className="h-4 w-4" aria-hidden />
  return <Minus className="h-4 w-4" aria-hidden />
}

function normalizeTrendSeries(raw: unknown): RiskTrendPoint[] {
  if (Array.isArray(raw)) return raw as RiskTrendPoint[]
  if (raw && typeof raw === 'object' && Array.isArray((raw as { series?: unknown }).series)) {
    return (raw as { series: RiskTrendPoint[] }).series
  }
  return []
}

function scoreSelectOptions() {
  return [1, 2, 3, 4, 5].map((n) => (
    <option key={n} value={n}>
      {n}
    </option>
  ))
}

export default function RiskProfile() {
  const { t } = useTranslation()
  const { riskId } = useParams<{ riskId: string }>()
  const [profile, setProfile] = useState<RiskProfile | null>(null)
  const [trendSeries, setTrendSeries] = useState<RiskTrendPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [assessing, setAssessing] = useState(false)
  const [assessError, setAssessError] = useState<string | null>(null)
  const [assessForm, setAssessForm] = useState({
    inherent_likelihood: 3,
    inherent_impact: 3,
    residual_likelihood: 3,
    residual_impact: 3,
    assessment_notes: '',
    review_notes: '',
  })
  const [notes, setNotes] = useState<RiskNote[]>([])
  const [activity, setActivity] = useState<RiskActivityEvent[]>([])
  const [actions, setActions] = useState<RiskActionItem[]>([])
  const [upstream, setUpstream] = useState<RiskUpstreamItem[]>([])
  const [noteDraft, setNoteDraft] = useState('')
  const [postingNote, setPostingNote] = useState(false)
  const [noteError, setNoteError] = useState<string | null>(null)
  const [ownerSearch, setOwnerSearch] = useState('')
  const [savingOwner, setSavingOwner] = useState(false)
  const [ownerError, setOwnerError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const id = Number(riskId)
    if (!Number.isInteger(id) || id <= 0) {
      setNotFound(true)
      setLoading(false)
      setProfile(null)
      setError(null)
      setTrendSeries([])
      setNotes([])
      setActivity([])
      setActions([])
      setUpstream([])
      return
    }

    setLoading(true)
    setError(null)
    setNotFound(false)
    try {
      const [profileRes, trendsRes, notesRes, activityRes, actionsRes, upstreamRes] =
        await Promise.all([
          riskRegisterApi.getProfile(id),
          riskRegisterApi.getTrends(365, false, id),
          riskRegisterApi.listNotes(id, { page_size: 50 }),
          riskRegisterApi.listActivity(id, { page_size: 50 }),
          riskRegisterApi.listActions(id, { page_size: 50 }),
          riskRegisterApi.listUpstream(id),
        ])
      const nextProfile = profileRes.data
      setProfile(nextProfile)
      setOwnerSearch(nextProfile.risk_owner_name || '')
      setTrendSeries(normalizeTrendSeries(trendsRes.data))
      setNotes(notesRes.data.items ?? [])
      setActivity(activityRes.data.items ?? [])
      setActions(actionsRes.data.items ?? [])
      setUpstream(upstreamRes.data.items ?? [])
      setAssessForm({
        inherent_likelihood: nextProfile.inherent_likelihood ?? 3,
        inherent_impact: nextProfile.inherent_impact ?? 3,
        residual_likelihood: nextProfile.residual_likelihood ?? 3,
        residual_impact: nextProfile.residual_impact ?? 3,
        assessment_notes: '',
        review_notes: nextProfile.review_notes ?? '',
      })
    } catch (err: unknown) {
      trackError(err, { component: 'RiskProfile', action: 'load', extra: { riskId } })
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setNotFound(true)
        setProfile(null)
        setError(null)
        setTrendSeries([])
        setNotes([])
        setActivity([])
        setActions([])
        setUpstream([])
      } else {
        setError(getApiErrorMessage(err, t('risk_register.profile.error')))
        setProfile(null)
        setTrendSeries([])
        setNotes([])
        setActivity([])
        setActions([])
        setUpstream([])
      }
    } finally {
      setLoading(false)
    }
    // t is stable enough for copy; omit from deps to avoid reload loops under test mocks
    // eslint-disable-next-line react-hooks/exhaustive-deps -- riskId drives reload
  }, [riskId])

  useEffect(() => {
    void load()
  }, [load])

  const sparkMax = useMemo(
    () => Math.max(1, ...trendSeries.map((p) => p.avg_residual ?? 0)),
    [trendSeries],
  )

  const handleAssess = async (event: FormEvent) => {
    event.preventDefault()
    const id = Number(riskId)
    if (!Number.isInteger(id) || id <= 0) return

    setAssessing(true)
    setAssessError(null)
    const payload: RiskAssessPayload = {
      inherent_likelihood: assessForm.inherent_likelihood,
      inherent_impact: assessForm.inherent_impact,
      residual_likelihood: assessForm.residual_likelihood,
      residual_impact: assessForm.residual_impact,
    }
    if (assessForm.assessment_notes.trim()) {
      payload.assessment_notes = assessForm.assessment_notes.trim()
    }
    if (assessForm.review_notes.trim()) {
      payload.review_notes = assessForm.review_notes.trim()
    }

    try {
      await riskRegisterApi.assess(id, payload)
      await load()
    } catch (err: unknown) {
      trackError(err, { component: 'RiskProfile', action: 'assess', extra: { riskId } })
      setAssessError(getApiErrorMessage(err, t('risk_register.profile.assess_error')))
    } finally {
      setAssessing(false)
    }
  }

  const submitNote = async () => {
    const id = Number(riskId)
    const trimmed = noteDraft.trim()
    if (!Number.isInteger(id) || id <= 0 || !trimmed) return

    setPostingNote(true)
    setNoteError(null)
    try {
      const res = await riskRegisterApi.createNote(id, trimmed)
      setNotes((prev) => [res.data, ...prev])
      setNoteDraft('')
      const activityRes = await riskRegisterApi.listActivity(id, { page_size: 50 })
      setActivity(activityRes.data.items ?? [])
    } catch (err: unknown) {
      trackError(err, { component: 'RiskProfile', action: 'createNote', extra: { riskId } })
      setNoteError(getApiErrorMessage(err, t('risk_register.profile.notes_error')))
    } finally {
      setPostingNote(false)
    }
  }


  const saveOwner = async (email: string, user?: UserSearchResult) => {
    const id = Number(riskId)
    if (!Number.isInteger(id) || id <= 0 || !user) {
      setOwnerSearch(email)
      return
    }

    setSavingOwner(true)
    setOwnerError(null)
    try {
      const res = await riskRegisterApi.updateOwner(id, {
        risk_owner_id: user.id,
        risk_owner_name: user.full_name || user.email,
      })
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              risk_owner_id: res.data.risk_owner_id,
              risk_owner_name: res.data.risk_owner_name,
            }
          : prev,
      )
      setOwnerSearch(res.data.risk_owner_name || user.full_name || user.email)
      const activityRes = await riskRegisterApi.listActivity(id, { page_size: 50 })
      setActivity(activityRes.data.items ?? [])
    } catch (err: unknown) {
      trackError(err, { component: 'RiskProfile', action: 'updateOwner', extra: { riskId } })
      setOwnerError(getApiErrorMessage(err, t('risk_register.profile.owner_error')))
    } finally {
      setSavingOwner(false)
    }
  }

  const createActionHref = useMemo(() => {
    if (!profile) return '/actions'
    return buildRiskCreateActionHref({
      riskId: profile.id,
      reference: profile.reference,
      title: profile.title,
    })
  }, [profile])

  if (loading) {
    return (
      <div className="p-6" data-testid="risk-profile-loading">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          <span>{t('risk_register.profile.loading')}</span>
        </div>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="space-y-4 p-6" data-testid="risk-profile-not-found">
        <Link
          to="/risk-register"
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          data-testid="risk-profile-back"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('risk_register.profile.back')}
        </Link>
        <Card>
          <CardContent className="flex items-start gap-3 p-6">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-warning" aria-hidden />
            <div>
              <h1 className="text-lg font-semibold text-foreground">
                {t('risk_register.profile.not_found')}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('risk_register.profile.not_found_detail')}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="space-y-4 p-6" data-testid="risk-profile-error">
        <Link
          to="/risk-register"
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          data-testid="risk-profile-back"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('risk_register.profile.back')}
        </Link>
        <Card>
          <CardContent className="space-y-3 p-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" aria-hidden />
              <div>
                <h1 className="text-lg font-semibold text-foreground">
                  {t('risk_register.profile.error')}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {error || t('risk_register.profile.error')}
                </p>
              </div>
            </div>
            <Button variant="secondary" onClick={() => void load()} data-testid="risk-profile-retry">
              {t('risk_register.profile.retry')}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6" data-testid="risk-profile-page">
      <Link
        to="/risk-register"
        className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
        data-testid="risk-profile-back"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('risk_register.profile.back')}
      </Link>

      <header className="space-y-4" data-testid="risk-profile-hero">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <p className="text-sm font-medium text-muted-foreground" data-testid="risk-profile-ref">
              {profile.reference || `RISK-${profile.id}`}
            </p>
            <h1
              className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl"
              data-testid="risk-profile-title"
            >
              {profile.title}
            </h1>
            <div className="flex flex-wrap items-center gap-2">
              {profile.status ? (
                <Badge variant="secondary" data-testid="risk-profile-status">
                  {profile.status}
                </Badge>
              ) : null}
              {profile.category ? (
                <Badge variant="outline" data-testid="risk-profile-category">
                  {profile.category}
                </Badge>
              ) : null}
              {profile.treatment ? (
                <Badge variant="outline" data-testid="risk-profile-treatment">
                  {profile.treatment}
                </Badge>
              ) : null}
              {profile.trend ? (
                <Badge
                  variant={trendBadgeVariant(profile.trend)}
                  className="inline-flex items-center gap-1"
                  data-testid="risk-profile-trend"
                >
                  <TrendIcon trend={profile.trend} />
                  {t(`risk_register.profile.trend.${profile.trend}`)}
                </Badge>
              ) : null}
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div
            className="rounded-lg border border-border bg-muted/30 p-4"
            data-testid="risk-profile-gross"
          >
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('risk_register.profile.gross')}
            </p>
            <p className="mt-1 text-3xl font-bold text-foreground">
              {profile.inherent_score ?? '—'}
            </p>
            {profile.inherent_level ? (
              <Badge className="mt-2" variant={levelBadgeVariant(profile.inherent_level)}>
                {profile.inherent_level}
              </Badge>
            ) : null}
          </div>
          <div
            className="rounded-lg border border-border bg-muted/30 p-4"
            data-testid="risk-profile-net"
          >
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('risk_register.profile.net')}
            </p>
            <p className="mt-1 text-3xl font-bold text-primary">
              {profile.residual_score ?? '—'}
            </p>
            {profile.residual_level ? (
              <Badge className="mt-2" variant={levelBadgeVariant(profile.residual_level)}>
                {profile.residual_level}
              </Badge>
            ) : null}
          </div>
          <div className="rounded-lg border border-border p-4 space-y-2" data-testid="risk-profile-owner">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('risk_register.profile.owner')}
            </p>
            <p className="text-base font-medium text-foreground" data-testid="risk-profile-owner-name">
              {profile.risk_owner_name || t('risk_register.profile.unassigned')}
            </p>
            <div data-testid="risk-profile-owner-picker">
              <UserEmailSearch
                value={ownerSearch}
                onChange={(email, user) => void saveOwner(email, user)}
                placeholder={t('risk_register.profile.owner_search')}
                label={t('risk_register.profile.owner_change')}
              />
              {savingOwner ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {t('risk_register.profile.owner_saving')}
                </p>
              ) : null}
              {ownerError ? (
                <p className="mt-1 text-xs text-destructive" data-testid="risk-profile-owner-error">
                  {ownerError}
                </p>
              ) : null}
            </div>
          </div>
          <div className="rounded-lg border border-border p-4 space-y-2">
            <div data-testid="risk-profile-updated">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {t('risk_register.profile.last_updated')}
              </p>
              <p className="text-sm font-medium text-foreground">
                {formatDate(profile.updated_at)}
              </p>
            </div>
            <div data-testid="risk-profile-reviews">
              <p className="text-xs text-muted-foreground">
                {t('risk_register.profile.last_review')}: {formatDate(profile.last_review_date)}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('risk_register.profile.next_review')}: {formatDate(profile.next_review_date)}
              </p>
            </div>
          </div>
        </div>
      </header>

      <Card data-testid="risk-profile-trend-chart">
        <CardContent className="space-y-3 p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('risk_register.profile.net_trend_title')}
            </p>
            <p className="text-sm text-muted-foreground">{t('risk_register.profile.net_trend_hint')}</p>
          </div>
          {trendSeries.length > 0 ? (
            <div className="flex h-16 items-end gap-1" data-testid="risk-profile-trend-bars">
              {trendSeries.map((point) => (
                <div key={point.month} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                  <div
                    title={`${point.month}: ${point.avg_residual.toFixed(1)}`}
                    className="w-full rounded-t bg-primary/70"
                    style={{
                      height: `${Math.max(8, (point.avg_residual / sparkMax) * 100)}%`,
                    }}
                  />
                  <span className="truncate text-[10px] text-muted-foreground">{point.month}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="risk-profile-trend-empty">
              {t('risk_register.profile.net_trend_empty')}
            </p>
          )}
        </CardContent>
      </Card>

      <Card data-testid="risk-profile-assess">
        <CardContent className="space-y-4 p-4">
          <div>
            <h2 className="text-base font-semibold text-foreground">
              {t('risk_register.profile.assess_title')}
            </h2>
            <p className="text-sm text-muted-foreground">{t('risk_register.profile.assess_hint')}</p>
          </div>
          <form className="space-y-4" onSubmit={(e) => void handleAssess(e)}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">
                  {t('risk_register.profile.inherent_likelihood')}
                </span>
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                  value={assessForm.inherent_likelihood}
                  onChange={(e) =>
                    setAssessForm((f) => ({ ...f, inherent_likelihood: Number(e.target.value) }))
                  }
                  data-testid="risk-profile-assess-inherent-likelihood"
                >
                  {scoreSelectOptions()}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">
                  {t('risk_register.profile.inherent_impact')}
                </span>
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                  value={assessForm.inherent_impact}
                  onChange={(e) =>
                    setAssessForm((f) => ({ ...f, inherent_impact: Number(e.target.value) }))
                  }
                  data-testid="risk-profile-assess-inherent-impact"
                >
                  {scoreSelectOptions()}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">
                  {t('risk_register.profile.residual_likelihood')}
                </span>
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                  value={assessForm.residual_likelihood}
                  onChange={(e) =>
                    setAssessForm((f) => ({ ...f, residual_likelihood: Number(e.target.value) }))
                  }
                  data-testid="risk-profile-assess-residual-likelihood"
                >
                  {scoreSelectOptions()}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">
                  {t('risk_register.profile.residual_impact')}
                </span>
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                  value={assessForm.residual_impact}
                  onChange={(e) =>
                    setAssessForm((f) => ({ ...f, residual_impact: Number(e.target.value) }))
                  }
                  data-testid="risk-profile-assess-residual-impact"
                >
                  {scoreSelectOptions()}
                </select>
              </label>
            </div>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">
                {t('risk_register.profile.assessment_notes')}
              </span>
              <Input
                value={assessForm.assessment_notes}
                onChange={(e) =>
                  setAssessForm((f) => ({ ...f, assessment_notes: e.target.value }))
                }
                data-testid="risk-profile-assess-notes"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">{t('risk_register.profile.review_notes')}</span>
              <Input
                value={assessForm.review_notes}
                onChange={(e) => setAssessForm((f) => ({ ...f, review_notes: e.target.value }))}
                data-testid="risk-profile-assess-review-notes"
              />
            </label>
            {assessError ? (
              <p className="text-sm text-destructive" data-testid="risk-profile-assess-error">
                {assessError}
              </p>
            ) : null}
            <Button type="submit" disabled={assessing} data-testid="risk-profile-assess-submit">
              {assessing ? t('risk_register.profile.assessing') : t('risk_register.profile.assess_submit')}
            </Button>
          </form>
        </CardContent>
      </Card>


      <div className="grid gap-6 lg:grid-cols-2">
        <Card data-testid="risk-profile-actions">
          <CardContent className="space-y-4 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
                  <ClipboardList className="h-4 w-4" aria-hidden />
                  {t('risk_register.profile.actions_title')}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {t('risk_register.profile.actions_hint')}
                </p>
              </div>
              <Button asChild size="sm" data-testid="risk-profile-create-action">
                <Link to={createActionHref}>
                  <Plus className="mr-1 h-4 w-4" aria-hidden />
                  {t('risk_register.profile.actions_create')}
                </Link>
              </Button>
            </div>
            {actions.length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="risk-profile-actions-empty">
                {t('risk_register.profile.actions_empty')}
              </p>
            ) : (
              <ul className="space-y-3" data-testid="risk-profile-actions-list">
                {actions.map((action) => (
                  <li
                    key={action.id}
                    className="rounded-md border border-border bg-muted/30 p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={action.href || `/actions?sourceType=risk&sourceId=${profile.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {action.reference_number || `CAPA-${action.id}`}
                      </Link>
                      {action.status ? <Badge variant="outline">{action.status}</Badge> : null}
                      {action.priority ? <Badge variant="secondary">{action.priority}</Badge> : null}
                    </div>
                    <p className="mt-1 text-foreground">{action.title}</p>
                    {action.due_date ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {t('risk_register.profile.actions_due')}: {formatDate(action.due_date)}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card data-testid="risk-profile-upstream">
          <CardContent className="space-y-4 p-4">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
                <GitBranch className="h-4 w-4" aria-hidden />
                {t('risk_register.profile.upstream_title')}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t('risk_register.profile.upstream_hint')}
              </p>
            </div>
            {upstream.length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="risk-profile-upstream-empty">
                {t('risk_register.profile.upstream_empty')}
              </p>
            ) : (
              <ul className="space-y-3" data-testid="risk-profile-upstream-list">
                {upstream.map((item) => (
                  <li
                    key={`${item.source_type}-${item.source_id}`}
                    className="rounded-md border border-border p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{item.source_type}</Badge>
                      <Link
                        to={item.href}
                        className="font-medium text-primary hover:underline"
                        data-testid={`risk-profile-upstream-link-${item.source_type}-${item.source_id}`}
                      >
                        {item.reference || `#${item.source_id}`}
                      </Link>
                    </div>
                    {item.title ? <p className="mt-1 text-foreground">{item.title}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card data-testid="risk-profile-notes">
          <CardContent className="space-y-4 p-4">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
                <MessageSquare className="h-4 w-4" aria-hidden />
                {t('risk_register.profile.notes_title')}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t('risk_register.profile.notes_hint')}
              </p>
            </div>
            <form
              className="space-y-2"
              onSubmit={(e) => {
                e.preventDefault()
                void submitNote()
              }}
            >
              <Textarea
                value={noteDraft}
                onChange={(e) => {
                  const v = e.target.value
                  setNoteDraft(v.length > MAX_NOTE_BODY_CHARS ? v.slice(0, MAX_NOTE_BODY_CHARS) : v)
                }}
                placeholder={t('risk_register.profile.notes_placeholder')}
                rows={3}
                maxLength={MAX_NOTE_BODY_CHARS}
                disabled={postingNote}
                data-testid="risk-profile-note-input"
              />
              {noteError ? (
                <p className="text-sm text-destructive" data-testid="risk-profile-note-error">
                  {noteError}
                </p>
              ) : null}
              <Button
                type="submit"
                disabled={postingNote || !noteDraft.trim()}
                data-testid="risk-profile-note-submit"
              >
                {postingNote
                  ? t('risk_register.profile.notes_posting')
                  : t('risk_register.profile.notes_submit')}
              </Button>
            </form>
            {notes.length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="risk-profile-notes-empty">
                {t('risk_register.profile.notes_empty')}
              </p>
            ) : (
              <ul className="space-y-3" data-testid="risk-profile-notes-list">
                {notes.map((note) => (
                  <li
                    key={note.id}
                    className="rounded-md border border-border bg-muted/30 p-3 text-sm"
                  >
                    <p className="text-xs text-muted-foreground">
                      {note.created_by_email || `#${note.created_by_id}`}
                      {' · '}
                      {formatRelativeTime(note.created_at)
                        ? `${formatRelativeTime(note.created_at)} · `
                        : ''}
                      {formatDateTime(note.created_at)}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-foreground">{note.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card data-testid="risk-profile-activity">
          <CardContent className="space-y-4 p-4">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
                <History className="h-4 w-4" aria-hidden />
                {t('risk_register.profile.activity_title')}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t('risk_register.profile.activity_hint')}
              </p>
            </div>
            {activity.length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="risk-profile-activity-empty">
                {t('risk_register.profile.activity_empty')}
              </p>
            ) : (
              <ul className="space-y-3" data-testid="risk-profile-activity-list">
                {activity.map((event) => (
                  <li
                    key={event.id}
                    className="rounded-md border border-border p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{event.event_type}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {event.actor_email || `#${event.actor_id}`}
                        {' · '}
                        {formatDateTime(event.created_at)}
                      </span>
                    </div>
                    <p className="mt-2 text-foreground">{event.summary}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {profile.description ? (
        <Card data-testid="risk-profile-description">
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('risk_register.profile.description')}
            </p>
            <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">{profile.description}</p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
