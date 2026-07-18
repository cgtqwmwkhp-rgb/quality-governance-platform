import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Download, ExternalLink, Loader2, Megaphone } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type DocumentCampaign,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { EmptyState } from '../components/ui'
import { CampaignRosterPanel } from './CampaignRosterPanel'

interface DocumentCampaignResultsProps {
  documentId: number
  initialCampaignId?: number | null
}

export function DocumentCampaignResults({
  documentId,
  initialCampaignId = null,
}: DocumentCampaignResultsProps) {
  const { t } = useTranslation()
  const [campaigns, setCampaigns] = useState<DocumentCampaign[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(initialCampaignId)
  const [exporting, setExporting] = useState(false)

  const loadCampaigns = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentCampaignApi.listCampaigns(documentId)
      const rows = response.data ?? []
      setCampaigns(rows)
      setSelectedId((prev) => {
        if (prev && rows.some((c) => c.id === prev)) return prev
        if (initialCampaignId && rows.some((c) => c.id === initialCampaignId)) {
          return initialCampaignId
        }
        return rows[0]?.id ?? null
      })
    } catch (err) {
      setCampaigns([])
      setSelectedId(null)
      setError(
        getApiErrorMessage(err, t('campaigns.results.load_error', 'Could not load campaigns')),
      )
    } finally {
      setLoading(false)
    }
  }, [documentId, initialCampaignId, t])

  useEffect(() => {
    void loadCampaigns()
  }, [loadCampaigns])

  const selected = campaigns.find((c) => c.id === selectedId) ?? null

  const handleExport = async () => {
    if (!selected) return
    setExporting(true)
    try {
      await documentCampaignApi.downloadEvidencePack(selected.id)
      toast.success(t('documents.detail.campaign_evidence_exported', 'Evidence pack downloaded'))
    } catch (err) {
      toast.error(
        getApiErrorMessage(err, t('documents.detail.campaign_evidence_export_error', 'Export failed')),
      )
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        {error}
        <Button variant="link" size="sm" className="ml-2 h-auto p-0" onClick={() => void loadCampaigns()}>
          {t('common.retry', 'Retry')}
        </Button>
      </div>
    )
  }

  if (campaigns.length === 0) {
    return (
      <EmptyState
        icon={<Megaphone className="h-8 w-8 text-muted-foreground" />}
        title={t('campaigns.results.empty_title', 'No campaigns for this document yet')}
        description={t(
          'campaigns.results.empty_desc',
          'Launch a read / quiz / sign campaign from the Share, Quiz & Compliance tab. Results appear here once people are assigned.',
        )}
        action={
          <Button asChild variant="outline">
            <Link to={`/documents/${documentId}?tab=quiz`}>
              {t('campaigns.results.go_launch', 'Go to Share / Quiz / Compliance')}
            </Link>
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-4" data-testid="document-campaign-results">
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>{t('campaigns.results.title', 'Campaign results')}</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground" data-testid="campaign-results-honesty">
              {t(
                'campaigns.results.honesty',
                'Live progress for people assigned to this document — who opened, who completed, who scored. Not a demo feed.',
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label={t('campaigns.results.select_campaign', 'Select campaign')}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={selectedId ?? ''}
              onChange={(e) => setSelectedId(Number(e.target.value))}
              data-testid="campaign-results-selector"
            >
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  #{campaign.id}
                  {campaign.title ? ` · ${campaign.title}` : ''} · {campaign.status}
                  {typeof campaign.completion_rate === 'number'
                    ? ` · ${Math.round(campaign.completion_rate)}%`
                    : ''}
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/campaign-compliance">
                <ExternalLink className="mr-2 h-4 w-4" />
                {t('campaigns.results.open_central', 'Central compliance')}
              </Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleExport()}
              disabled={!selected || exporting}
            >
              {exporting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              {t('campaigns.results.export', 'Export evidence')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {selected ? (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                <span>
                  {t('campaigns.results.meta_status', 'Status')}:{' '}
                  <span className="capitalize text-foreground">{selected.status}</span>
                </span>
                <span>
                  {t('campaigns.results.meta_assigned', 'Assigned')}:{' '}
                  <span className="text-foreground">
                    {selected.total_assigned ?? selected.assigned_count ?? '—'}
                  </span>
                </span>
                <span>
                  {t('campaigns.results.meta_due_days', 'Due within')}:{' '}
                  <span className="text-foreground">{selected.due_within_days}d</span>
                </span>
              </div>
              <CampaignRosterPanel campaignId={selected.id} />
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
