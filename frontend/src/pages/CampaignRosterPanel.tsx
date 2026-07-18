import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2, Search } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type CampaignRosterResponse,
  type CampaignRosterRow,
  type CampaignRosterSummary,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { EmptyState } from '../components/ui'

export type RosterStatusFilter = '' | 'pending' | 'completed' | 'overdue' | 'expired'
export type RosterOpenedFilter = '' | 'opened' | 'not_opened'
export type RosterQuizFilter = '' | 'passed' | 'failed'

function formatWhen(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString()
}

function quizLabel(row: CampaignRosterRow): string {
  if (row.quiz_attempts <= 0 && row.quiz_score == null) return '—'
  const score = row.quiz_score == null ? '—' : `${row.quiz_score}%`
  if (row.quiz_passed === true) return `${score} · pass`
  if (row.quiz_passed === false) return `${score} · fail`
  return score
}

interface CampaignRosterPanelProps {
  campaignId: number
  compact?: boolean
}

export function CampaignRosterPanel({ campaignId, compact = false }: CampaignRosterPanelProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [roster, setRoster] = useState<CampaignRosterResponse | null>(null)
  const [statusFilter, setStatusFilter] = useState<RosterStatusFilter>('')
  const [openedFilter, setOpenedFilter] = useState<RosterOpenedFilter>('')
  const [quizFilter, setQuizFilter] = useState<RosterQuizFilter>('')
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')

  const loadRoster = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const opened =
        openedFilter === 'opened' ? true : openedFilter === 'not_opened' ? false : undefined
      const quizPassed =
        quizFilter === 'passed' ? true : quizFilter === 'failed' ? false : undefined
      const response = await documentCampaignApi.listCampaignRoster(campaignId, {
        status: statusFilter || undefined,
        q: appliedSearch || undefined,
        opened,
        quiz_passed: quizPassed,
        limit: 100,
        offset: 0,
      })
      setRoster(response.data)
    } catch (err) {
      setRoster(null)
      setError(getApiErrorMessage(err, t('campaigns.roster.load_error', 'Could not load roster')))
    } finally {
      setLoading(false)
    }
  }, [appliedSearch, campaignId, openedFilter, quizFilter, statusFilter, t])

  useEffect(() => {
    void loadRoster()
  }, [loadRoster])

  const summary: CampaignRosterSummary | null = roster?.summary ?? null

  return (
    <div className="space-y-4" data-testid="campaign-roster-panel">
      {summary ? (
        <div
          className={`grid gap-3 ${compact ? 'grid-cols-2 md:grid-cols-4' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-6'}`}
          data-testid="campaign-roster-kpis"
        >
          {[
            {
              label: t('campaigns.roster.kpi_completion', 'Completion'),
              value: `${Math.round(summary.completion_rate)}%`,
            },
            {
              label: t('campaigns.roster.kpi_opened', 'Opened'),
              value: `${Math.round(summary.open_rate)}%`,
            },
            {
              label: t('campaigns.roster.kpi_pending', 'Pending'),
              value: String(summary.pending),
            },
            {
              label: t('campaigns.roster.kpi_overdue', 'Overdue'),
              value: String(summary.overdue),
            },
            {
              label: t('campaigns.roster.kpi_quiz_pass', 'Quiz pass'),
              value: String(summary.quiz_pass_count),
            },
            {
              label: t('campaigns.roster.kpi_quiz_fail', 'Quiz fail'),
              value: String(summary.quiz_fail_count),
            },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="rounded-lg border border-border bg-card px-3 py-2"
            >
              <p className="text-xs text-muted-foreground">{kpi.label}</p>
              <p className="text-lg font-semibold text-foreground">{kpi.value}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex flex-col gap-2 md:flex-row md:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor={`roster-search-${campaignId}`}>
            {t('campaigns.roster.search', 'Search people')}
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              id={`roster-search-${campaignId}`}
              className="pl-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setAppliedSearch(search.trim())
              }}
              placeholder={t('campaigns.roster.search_placeholder', 'Name or email')}
            />
          </div>
        </div>
        <select
          aria-label={t('campaigns.roster.filter_status', 'Status')}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as RosterStatusFilter)}
        >
          <option value="">{t('campaigns.roster.filter_all_statuses', 'All statuses')}</option>
          <option value="pending">Pending</option>
          <option value="overdue">Overdue</option>
          <option value="completed">Completed</option>
          <option value="expired">Expired</option>
        </select>
        <select
          aria-label={t('campaigns.roster.filter_opened', 'Opened')}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          value={openedFilter}
          onChange={(e) => setOpenedFilter(e.target.value as RosterOpenedFilter)}
        >
          <option value="">{t('campaigns.roster.filter_all_opened', 'Opened: any')}</option>
          <option value="opened">{t('campaigns.roster.filter_opened_yes', 'Opened')}</option>
          <option value="not_opened">{t('campaigns.roster.filter_opened_no', 'Not opened')}</option>
        </select>
        <select
          aria-label={t('campaigns.roster.filter_quiz', 'Quiz')}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          value={quizFilter}
          onChange={(e) => setQuizFilter(e.target.value as RosterQuizFilter)}
        >
          <option value="">{t('campaigns.roster.filter_all_quiz', 'Quiz: any')}</option>
          <option value="passed">{t('campaigns.roster.filter_quiz_pass', 'Passed')}</option>
          <option value="failed">{t('campaigns.roster.filter_quiz_fail', 'Failed')}</option>
        </select>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setAppliedSearch(search.trim())
            void loadRoster()
          }}
        >
          {t('campaigns.roster.apply', 'Apply')}
        </Button>
      </div>

      {loading && !roster ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : error && !roster ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
          <Button variant="link" size="sm" className="ml-2 h-auto p-0" onClick={() => void loadRoster()}>
            {t('common.retry', 'Retry')}
          </Button>
        </div>
      ) : !roster || roster.items.length === 0 ? (
        <EmptyState
          title={t('campaigns.roster.empty_title', 'No matching assignees')}
          description={t(
            'campaigns.roster.empty_desc',
            'Empty means no people match these filters — not demo data. Launch a campaign or clear filters.',
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-muted-foreground">
                <th className="px-3 py-2 font-medium">{t('campaigns.roster.col_person', 'Person')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.roster.col_status', 'Status')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.roster.col_opened', 'Opened')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.roster.col_quiz', 'Quiz')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.roster.col_completed', 'Completed')}</th>
                <th className="px-3 py-2 font-medium">{t('campaigns.roster.col_reminders', 'Reminders')}</th>
              </tr>
            </thead>
            <tbody>
              {roster.items.map((row) => (
                <tr key={row.assignment_id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2">
                    <p className="font-medium text-foreground">{row.user_name || '—'}</p>
                    <p className="text-xs text-muted-foreground">{row.user_email}</p>
                  </td>
                  <td className="px-3 py-2 capitalize">{row.status}</td>
                  <td className="px-3 py-2">{formatWhen(row.first_opened_at)}</td>
                  <td className="px-3 py-2">
                    {quizLabel(row)}
                    {row.quiz_attempts > 0 ? (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({row.quiz_attempts} {t('campaigns.roster.attempts', 'attempts')})
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">{formatWhen(row.completed_at)}</td>
                  <td className="px-3 py-2">{row.reminders_sent}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 py-2 text-xs text-muted-foreground" data-testid="campaign-roster-total">
            {t('campaigns.roster.showing', {
              defaultValue: 'Showing {{shown}} of {{total}} assignees',
              shown: roster.items.length,
              total: roster.total,
            })}
          </p>
        </div>
      )}
    </div>
  )
}
