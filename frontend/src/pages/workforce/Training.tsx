import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Search, Filter, ChevronRight } from 'lucide-react'
import { TableSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import {
  workforceApi,
  auditsApi,
  getApiErrorMessage,
  type InductionRun,
  type AssetType,
} from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'
import { formatScheduledDate } from './dateUtils'

const STATUS_VARIANTS: Record<
  string,
  'success' | 'warning' | 'info' | 'destructive' | 'secondary'
> = {
  completed: 'success',
  in_progress: 'warning',
  draft: 'info',
  cancelled: 'destructive',
}

export default function Training() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [inductions, setInductions] = useState<InductionRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [stageFilter, setStageFilter] = useState('')
  const [engineerFilter, setEngineerFilter] = useState('')
  const [engineerMap, setEngineerMap] = useState<Record<number, string>>({})
  const [templateMap, setTemplateMap] = useState<Record<number, string>>({})
  const [assetTypes, setAssetTypes] = useState<AssetType[]>([])
  const [lookupWarning, setLookupWarning] = useState<string | null>(null)

  useEffect(() => {
    workforceApi
      .listEngineers({ page: '1', page_size: '500' })
      .then((res) => {
        const map: Record<number, string> = {}
        for (const e of res.data?.items || []) {
          map[e.id] =
            e.display_name?.trim() || e.employee_number || e.job_title || `#${e.id}`
        }
        setEngineerMap(map)
      })
      .catch(() => {
        setLookupWarning(
          'Some engineer, template, or asset labels could not be loaded. Training records remain available by ID.',
        )
      })
    auditsApi
      .listTemplates(1, 500, { is_published: true })
      .then((res) => {
        const map: Record<number, string> = {}
        for (const tmpl of res.data?.items || []) {
          map[tmpl.id] = tmpl.name
        }
        setTemplateMap(map)
      })
      .catch(() => {
        setLookupWarning(
          'Some engineer, template, or asset labels could not be loaded. Training records remain available by ID.',
        )
      })
    workforceApi
      .listAssetTypes()
      .then((res) => setAssetTypes(res.data?.items || []))
      .catch(() => {
        setLookupWarning(
          'Some engineer, template, or asset labels could not be loaded. Training records remain available by ID.',
        )
      })
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        // List API supports status / engineer_id / asset_type_id only — never send `search` or `stage`.
        const params: Record<string, string> = { page: '1', page_size: '50' }
        if (statusFilter) params.status = statusFilter
        if (engineerFilter) params.engineer_id = engineerFilter
        const res = await workforceApi.listInductions(params)
        setInductions(res.data.items || [])
      } catch (err: unknown) {
        setError(getApiErrorMessage(err))
        setInductions([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [statusFilter, engineerFilter])

  const filteredInductions = useMemo(() => {
    let rows = inductions
    if (stageFilter) {
      rows = rows.filter((i) => i.stage === stageFilter)
    }
    const q = searchTerm.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((i) => {
      const ref = (i.reference_number || '').toLowerCase()
      const eng = (engineerMap[i.engineer_id] ?? `#${i.engineer_id}`).toLowerCase()
      const tmpl = (templateMap[i.template_id] ?? `#${i.template_id}`).toLowerCase()
      const stage = (i.stage || '').toLowerCase()
      return ref.includes(q) || eng.includes(q) || tmpl.includes(q) || stage.includes(q)
    })
  }, [inductions, stageFilter, searchTerm, engineerMap, templateMap])

  const engineerOptions = useMemo(
    () =>
      Object.entries(engineerMap)
        .map(([id, label]) => ({ id, label }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [engineerMap],
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('workforce.training.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('workforce.training.subtitle')}</p>
        </div>
        <Button onClick={() => navigate('/workforce/training/new')} className="gap-2">
          <Plus className="w-4 h-4" />
          {t('workforce.training.new')}
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('workforce.training.search_placeholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
                aria-label="Search training (client-side)"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
                aria-label={t('common.status')}
              >
                <option value="">{t('workforce.common.all_statuses')}</option>
                <option value="draft">{t('common.draft')}</option>
                <option value="in_progress">{t('common.in_progress')}</option>
                <option value="completed">{t('common.completed')}</option>
                <option value="cancelled">{t('common.cancelled')}</option>
              </select>
              <select
                value={engineerFilter}
                onChange={(e) => setEngineerFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
                aria-label={t('workforce.common.engineer')}
              >
                <option value="">All engineers</option>
                {engineerOptions.map((eng) => (
                  <option key={eng.id} value={eng.id}>
                    {eng.label}
                  </option>
                ))}
              </select>
              <select
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
                aria-label={t('workforce.common.stage')}
                title="Stage is filtered client-side (list API has no stage param)"
              >
                <option value="">{t('workforce.training.all_stages')}</option>
                <option value="stage_1_onsite">{t('workforce.training.stage1')}</option>
                <option value="stage_2_field">{t('workforce.training.stage2')}</option>
              </select>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                disabled
                title="Additional filters are not available yet"
                aria-disabled="true"
              >
                <Filter className="w-4 h-4" />
                {t('workforce.common.filters')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}
          {lookupWarning && (
            <div
              className="mb-4 p-3 rounded-lg bg-amber-500/10 text-amber-900 text-sm"
              data-testid="training-lookup-warning"
            >
              {lookupWarning}
            </div>
          )}
          {loading ? (
            <TableSkeleton rows={6} columns={4} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('workforce.common.reference')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('workforce.common.engineer')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('workforce.common.template')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('workforce.common.asset_type')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('workforce.common.stage')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('common.status')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('common.date')}
                    </th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {filteredInductions.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-muted-foreground">
                        {t('workforce.training.empty')}
                      </td>
                    </tr>
                  ) : (
                    filteredInductions.map((i) => (
                      <tr
                        key={i.id}
                        className={cn(
                          'border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer',
                        )}
                        onClick={() => navigate(`/workforce/training/${i.id}/execute`)}
                      >
                        <td className="py-3 px-4 text-sm font-medium text-foreground">
                          {i.reference_number}
                        </td>
                        <td className="py-3 px-4 text-sm text-foreground">
                          {engineerMap[i.engineer_id] ?? `#${i.engineer_id}`}
                        </td>
                        <td className="py-3 px-4 text-sm text-foreground">
                          {templateMap[i.template_id] ?? `#${i.template_id}`}
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {i.asset_type_id
                            ? (assetTypes.find((at) => at.id === i.asset_type_id)?.name ??
                              `#${i.asset_type_id}`)
                            : '—'}
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {i.stage?.replace(/_/g, ' ') ?? '—'}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant={STATUS_VARIANTS[i.status] || 'secondary'}>
                            {i.status?.replace(/_/g, ' ') ?? '—'}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {formatScheduledDate(i.scheduled_date)}
                        </td>
                        <td className="py-3 px-4">
                          <ChevronRight className="w-4 h-4 text-muted-foreground" />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
