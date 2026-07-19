import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, Search } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type CompliancePeopleResponse,
  type CompliancePeopleStatus,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { EmptyState } from '../components/ui'
import { buildCampaignResultsHref } from './documentCampaignHelpers'

function formatWhen(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString()
}

export function CampaignPeopleChase() {
  const { t } = useTranslation()
  const [status, setStatus] = useState<CompliancePeopleStatus>('overdue')
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<CompliancePeopleResponse | null>(null)

  const loadPeople = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await documentCampaignApi.listCompliancePeople({
        status,
        q: appliedSearch || undefined,
        limit: 50,
        offset: 0,
      })
      setResponse(result.data)
    } catch (err) {
      setResponse(null)
      setError(getApiErrorMessage(err, t('campaigns.chase.load_error', 'Could not load chase list')))
    } finally {
      setLoading(false)
    }
  }, [appliedSearch, status, t])

  useEffect(() => {
    void loadPeople()
  }, [loadPeople])

  return (
    <div className="space-y-4" data-testid="campaign-people-chase">
      <div>
        <h2 className="text-lg font-semibold text-foreground">
          {t('campaigns.chase.title', 'People to chase')}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t('campaigns.chase.subtitle', 'Overdue assignees and quiz failures across active campaigns.')}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant={status === 'overdue' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setStatus('overdue')}
          data-testid="campaign-chase-tab-overdue"
        >
          {t('campaigns.chase.tab_overdue', 'Overdue')}
        </Button>
        <Button
          type="button"
          variant={status === 'quiz_fail' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setStatus('quiz_fail')}
          data-testid="campaign-chase-tab-quiz-fail"
        >
          {t('campaigns.chase.tab_quiz_fail', 'Quiz fail')}
        </Button>
      </div>

      <div className="flex flex-col gap-2 md:flex-row md:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="campaign-chase-search">
            {t('campaigns.chase.search', 'Search people or documents')}
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              id="campaign-chase-search"
              className="pl-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setAppliedSearch(search.trim())
              }}
              placeholder={t('campaigns.chase.search_placeholder', 'Name, email, or document title')}
            />
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setAppliedSearch(search.trim())
            void loadPeople()
          }}
        >
          {t('campaigns.chase.apply', 'Apply')}
        </Button>
      </div>

      {loading && !response ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : error && !response ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
          <Button variant="link" size="sm" className="ml-2 h-auto p-0" onClick={() => void loadPeople()}>
            {t('common.retry', 'Retry')}
          </Button>
        </div>
      ) : !response || response.items.length === 0 ? (
        <EmptyState
          title={t('campaigns.chase.empty_title', 'No one to chase')}
          description={t(
            'campaigns.chase.empty_desc',
            'Empty means no assignees match this filter — not demo data.',
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-muted-foreground">
                <th className="px-3 py-2 font-medium">{t('campaigns.chase.col_person', 'Person')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.chase.col_document', 'Document')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.chase.col_status', 'Status')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.chase.col_due', 'Due')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.chase.col_quiz', 'Quiz')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.chase.col_actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {response.items.map((row) => (
                <tr key={row.assignment_id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2">
                    <p className="font-medium text-foreground">{row.user_name || '—'}</p>
                    <p className="text-xs text-muted-foreground">{row.user_email}</p>
                  </td>
                  <td className="px-3 py-2">
                    <p className="font-medium text-foreground">{row.document_title || `#${row.document_id}`}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('admin.campaign_compliance.campaign_id', { id: row.campaign_id })}
                    </p>
                  </td>
                  <td className="px-3 py-2 capitalize">{row.status}</td>
                  <td className="px-3 py-2">{formatWhen(row.due_at)}</td>
                  <td className="px-3 py-2">
                    {row.quiz_attempts > 0 || row.quiz_score != null ? (
                      <>
                        {row.quiz_score == null ? '—' : `${row.quiz_score}%`}
                        {row.quiz_passed === false ? ` · ${t('campaigns.chase.quiz_fail', 'fail')}` : ''}
                        {row.quiz_attempts > 0 ? (
                          <span className="ml-1 text-xs text-muted-foreground">
                            ({row.quiz_attempts})
                          </span>
                        ) : null}
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Button variant="outline" size="sm" asChild>
                      <Link to={buildCampaignResultsHref(row.document_id, row.campaign_id)}>
                        {t('campaigns.chase.open_results', 'Open results')}
                      </Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 py-2 text-xs text-muted-foreground" data-testid="campaign-chase-total">
            {t('campaigns.chase.showing', {
              defaultValue: 'Showing {{shown}} of {{total}} people',
              shown: response.items.length,
              total: response.total,
            })}
          </p>
        </div>
      )}
    </div>
  )
}
