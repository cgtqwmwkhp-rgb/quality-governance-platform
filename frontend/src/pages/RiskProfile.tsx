import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, AlertTriangle, Loader2 } from 'lucide-react'
import { getApiErrorMessage, riskRegisterApi } from '../api/client'
import type { RiskProfile } from '../api/riskRegisterClient'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Card, CardContent } from '../components/ui/Card'
import { trackError } from '../utils/errorTracker'

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

export default function RiskProfile() {
  const { t } = useTranslation()
  const { riskId } = useParams<{ riskId: string }>()
  const [profile, setProfile] = useState<RiskProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(async () => {
    const id = Number(riskId)
    if (!Number.isInteger(id) || id <= 0) {
      setNotFound(true)
      setLoading(false)
      setProfile(null)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    setNotFound(false)
    try {
      const res = await riskRegisterApi.getProfile(id)
      setProfile(res.data)
    } catch (err: unknown) {
      trackError(err, { component: 'RiskProfile', action: 'load', extra: { riskId } })
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setNotFound(true)
        setProfile(null)
        setError(null)
      } else {
        setError(getApiErrorMessage(err, t('risk_register.profile.error')))
        setProfile(null)
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
          <div className="rounded-lg border border-border p-4" data-testid="risk-profile-owner">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('risk_register.profile.owner')}
            </p>
            <p className="mt-2 text-base font-medium text-foreground">
              {profile.risk_owner_name || t('risk_register.profile.unassigned')}
            </p>
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
