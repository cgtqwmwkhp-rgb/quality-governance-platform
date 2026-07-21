/**
 * Assurance Certificate Shelf
 *
 * Unified expiry-driven readiness view across compliance register,
 * Planet Mark, UVDB Achilles, and Governance Library masters.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Award,
  BookOpen,
  ExternalLink,
  Leaf,
  RefreshCw,
  Shield,
} from 'lucide-react'
import { complianceAutomationApi, getApiErrorMessage } from '../api/client'
import { cn } from '../helpers/utils'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState } from '../components/ui'
import { toast } from '../contexts/ToastContext'
import {
  ASSURANCE_CERT_READINESS_COLORS,
  ASSURANCE_CERT_READINESS_LABELS,
  ASSURANCE_CERT_SCHEME_LABELS,
  formatAssuranceCertExpiry,
  type AssuranceCertReadinessStatus,
  type AssuranceCertShelfItem,
  type AssuranceCertShelfResponse,
} from './assuranceCertShelfHelpers'

const SCHEME_FILTERS = ['all', 'register', 'planet_mark', 'uvdb_achilles', 'library'] as const
const STATUS_FILTERS: Array<'all' | AssuranceCertReadinessStatus> = [
  'all',
  'valid',
  'due_soon',
  'expired',
  'unknown',
]

function schemeIcon(scheme: string) {
  switch (scheme) {
    case 'planet_mark':
      return Leaf
    case 'uvdb_achilles':
      return Award
    case 'library':
      return BookOpen
    default:
      return Shield
  }
}

export default function AssuranceCertShelf() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [shelf, setShelf] = useState<AssuranceCertShelfResponse | null>(null)
  const [schemeFilter, setSchemeFilter] = useState<(typeof SCHEME_FILTERS)[number]>('all')
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all')

  const loadShelf = useCallback(async () => {
    setLoading(true)
    try {
      const response = await complianceAutomationApi.getAssuranceCertShelf({
        scheme: schemeFilter === 'all' ? undefined : schemeFilter,
        readiness_status: statusFilter === 'all' ? undefined : statusFilter,
      })
      setShelf(response.data)
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Unable to load assurance certificate shelf'))
      setShelf(null)
    } finally {
      setLoading(false)
    }
  }, [schemeFilter, statusFilter])

  useEffect(() => {
    void loadShelf()
  }, [loadShelf])

  const summaryCards = useMemo(() => {
    const summary = shelf?.summary
    if (!summary) return []
    return [
      { key: 'valid', label: 'Valid', value: summary.valid, tone: 'text-success' },
      { key: 'due_soon', label: 'Due soon', value: summary.due_soon, tone: 'text-warning' },
      { key: 'expired', label: 'Expired', value: summary.expired, tone: 'text-destructive' },
      { key: 'unknown', label: 'Unknown', value: summary.unknown, tone: 'text-muted-foreground' },
    ]
  }, [shelf])

  const items = shelf?.items ?? []

  return (
    <div className="space-y-6" data-testid="assurance-cert-shelf-page">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            {t('assurance.cert_shelf.title', 'Certificate shelf')}
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
            {t(
              'assurance.cert_shelf.subtitle',
              'Readiness across Library masters and external assurance systems of record (UVDB, Planet Mark).',
            )}
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadShelf()} data-testid="assurance-cert-shelf-refresh">
          <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
          {t('common.refresh', 'Refresh')}
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="assurance-cert-shelf-summary">
        {summaryCards.map((card) => (
          <Card key={card.key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{card.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={cn('text-2xl font-semibold', card.tone)}>{card.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap gap-2" data-testid="assurance-cert-shelf-scheme-filters">
        {SCHEME_FILTERS.map((scheme) => (
          <button
            key={scheme}
            type="button"
            onClick={() => setSchemeFilter(scheme)}
            className={cn(
              'px-3 py-1.5 rounded-full text-sm border transition-colors',
              schemeFilter === scheme
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border hover:bg-accent',
            )}
          >
            {scheme === 'all'
              ? t('common.all', 'All schemes')
              : ASSURANCE_CERT_SCHEME_LABELS[scheme] ?? scheme}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2" data-testid="assurance-cert-shelf-status-filters">
        {STATUS_FILTERS.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => setStatusFilter(status)}
            className={cn(
              'px-3 py-1.5 rounded-full text-sm border transition-colors',
              statusFilter === status
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border hover:bg-accent',
            )}
          >
            {status === 'all'
              ? t('campaigns.roster.filter_all_statuses', 'All statuses')
              : ASSURANCE_CERT_READINESS_LABELS[status]}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader className="border-b border-border">
          <CardTitle className="text-base">
            {t('assurance.cert_shelf.list_title', 'Certificates and assurance credentials')}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <p className="p-6 text-sm text-muted-foreground">{t('common.loading', 'Loading…')}</p>
          ) : items.length === 0 ? (
            <div data-testid="assurance-cert-shelf-empty">
              <EmptyState
                icon={<Award className="w-8 h-8 text-muted-foreground" />}
                title={t('assurance.cert_shelf.empty.title', 'No certificates on the shelf yet')}
                description={t(
                  'assurance.cert_shelf.empty.description',
                  'Add register certificates in Monitoring, record Planet Mark / UVDB expiry dates in their modules, or file statutory masters in the Governance Library with an expiry date.',
                )}
              />
            </div>
          ) : (
            <div className="divide-y divide-border" data-testid="assurance-cert-shelf-list">
              {items.map((item) => (
                <AssuranceCertShelfRow key={item.shelf_key} item={item} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function AssuranceCertShelfRow({ item }: { item: AssuranceCertShelfItem }) {
  const SchemeIcon = schemeIcon(item.scheme)
  const readiness = item.readiness_status

  return (
    <div className="p-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-start gap-3 min-w-0">
        <div className="p-2 rounded-lg bg-accent">
          <SchemeIcon className="w-5 h-5 text-foreground" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-foreground truncate">{item.name}</h3>
            {item.is_critical && (
              <Badge variant="destructive" className="text-xs">
                Critical
              </Badge>
            )}
            {item.is_external_sor && (
              <Badge variant="outline" className="text-xs">
                External SoR
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {ASSURANCE_CERT_SCHEME_LABELS[item.scheme] ?? item.scheme}
            {item.issuing_body ? ` • ${item.issuing_body}` : ''}
            {item.reference_number ? ` • ${item.reference_number}` : ''}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 lg:justify-end">
        <span className={cn('px-2 py-1 rounded text-xs font-medium', ASSURANCE_CERT_READINESS_COLORS[readiness])}>
          {ASSURANCE_CERT_READINESS_LABELS[readiness]}
        </span>
        <span className="text-sm text-muted-foreground">
          Expires: {formatAssuranceCertExpiry(item.expiry_date)}
        </span>
        <div className="flex items-center gap-2">
          {item.detail_path && (
            <Link
              to={item.detail_path}
              className="text-sm text-primary hover:underline"
              data-testid={`assurance-cert-detail-${item.shelf_key}`}
            >
              Open module
            </Link>
          )}
          {item.library_path && (
            <Link
              to={item.library_path}
              className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              data-testid={`assurance-cert-library-${item.shelf_key}`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              Library
            </Link>
          )}
          {item.external_url && (
            <a
              href={item.external_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              data-testid={`assurance-cert-external-${item.shelf_key}`}
            >
              <ExternalLink className="w-3.5 h-3.5" />
              External
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
