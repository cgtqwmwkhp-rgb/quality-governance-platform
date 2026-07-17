import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../../utils/errorTracker'
import { Plus, Search, Filter, ChevronRight } from 'lucide-react'
import { TableSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import {
  workforceApi,
  auditsApi,
  getApiErrorMessage,
  type AssessmentRun,
  type AssetType,
} from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'
import { formatScheduledDate } from './dateUtils'
import {
  ACTIVE_EMPLOYEES_LIST_PARAMS,
  buildEmployeeLabelMap,
  employeePickerOptionLabel,
} from './employeePickerUtils'

const STATUS_VARIANTS: Record<
  string,
  'success' | 'warning' | 'info' | 'destructive' | 'secondary'
> = {
  completed: 'success',
  in_progress: 'warning',
  scheduled: 'info',
  pending_debrief: 'secondary',
  cancelled: 'destructive',
}

const OUTCOME_VARIANTS: Record<string, 'success' | 'warning' | 'destructive'> = {
  pass: 'success',
  competent: 'success',
  conditional: 'warning',
  fail: 'destructive',
}

export default function Assessments() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [assessments, setAssessments] = useState<AssessmentRun[]>([])
  const [assetTypes, setAssetTypes] = useState<AssetType[]>([])
  const [engineerMap, setEngineerMap] = useState<Record<number, string>>({})
  const [activeEmployees, setActiveEmployees] = useState<
    Array<{ id: number; label: string }>
  >([])
  const [templateMap, setTemplateMap] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [engineerFilter, setEngineerFilter] = useState('')
  const [assetTypeFilter, setAssetTypeFilter] = useState('')

  // Load asset types, engineers, and templates for name resolution
  useEffect(() => {
    workforceApi
      .listAssetTypes()
      .then((res) => setAssetTypes(res.data?.items || []))
      .catch(() => setAssetTypes([]))
    workforceApi
      .listEngineers({ ...ACTIVE_EMPLOYEES_LIST_PARAMS })
      .then((res) => {
        const items = res.data?.items || []
        setEngineerMap(buildEmployeeLabelMap(items))
        setActiveEmployees(
          [...items]
            .map((e) => ({ id: e.id, label: employeePickerOptionLabel(e) }))
            .sort((a, b) => a.label.localeCompare(b.label)),
        )
      })
      .catch(() => {
        setEngineerMap({})
        setActiveEmployees([])
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
      .catch(() => {})
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        // List API supports status / engineer_id / asset_type_id only — never send `search`.
        const params: Record<string, string> = { page: '1', page_size: '50' }
        if (statusFilter) params.status = statusFilter
        if (engineerFilter) params.engineer_id = engineerFilter
        if (assetTypeFilter) params.asset_type_id = assetTypeFilter
        const res = await workforceApi.listAssessments(params)
        setAssessments(res.data.items || [])
      } catch (err) {
        trackError(err, { component: 'Assessments', action: 'load' })
        setError(getApiErrorMessage(err))
        setAssessments([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [statusFilter, engineerFilter, assetTypeFilter])

  const filteredAssessments = useMemo(() => {
    const q = searchTerm.trim().toLowerCase()
    if (!q) return assessments
    return assessments.filter((a) => {
      const ref = (a.reference_number || '').toLowerCase()
      const eng = (engineerMap[a.engineer_id] ?? `#${a.engineer_id}`).toLowerCase()
      const tmpl = (templateMap[a.template_id] ?? `#${a.template_id}`).toLowerCase()
      return ref.includes(q) || eng.includes(q) || tmpl.includes(q)
    })
  }, [assessments, searchTerm, engineerMap, templateMap])

  const rosterEmpty = activeEmployees.length === 0

  return (
    <div className="space-y-6">
      {error && <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{error}</div>}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('workforce.assessments.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('workforce.assessments.subtitle')}</p>
        </div>
        <Button onClick={() => navigate('/workforce/assessments/new')} className="gap-2">
          <Plus className="w-4 h-4" />
          {t('workforce.assessments.new')}
        </Button>
      </div>

      {rosterEmpty && (
        <div
          className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground"
          data-testid="assessments-employees-empty"
        >
          {t('workforce.assessments.employees_empty')}{' '}
          <button
            type="button"
            className="text-primary underline underline-offset-2"
            onClick={() => navigate('/workforce/engineers')}
          >
            {t('workforce.assessments.employees_empty_link')}
          </button>
        </div>
      )}

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('workforce.assessments.search_placeholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
                aria-label="Search assessments (client-side)"
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
                <option value="pending_debrief">
                  {t('workforce.assessments.pending_debrief')}
                </option>
                <option value="completed">{t('common.completed')}</option>
                <option value="cancelled">{t('common.cancelled')}</option>
              </select>
              <select
                value={engineerFilter}
                onChange={(e) => setEngineerFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
                aria-label={t('workforce.common.engineer')}
                disabled={rosterEmpty}
              >
                <option value="">{t('workforce.common.all_employees')}</option>
                {activeEmployees.map((eng) => (
                  <option key={eng.id} value={String(eng.id)}>
                    {eng.label}
                  </option>
                ))}
              </select>
              <select
                value={assetTypeFilter}
                onChange={(e) => setAssetTypeFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
                aria-label={t('workforce.common.asset_type')}
              >
                <option value="">{t('workforce.common.all_asset_types')}</option>
                {assetTypes.map((at) => (
                  <option key={at.id} value={String(at.id)}>
                    {at.name}
                  </option>
                ))}
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
                      {t('common.status')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('common.date')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      {t('workforce.assessments.outcome')}
                    </th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {filteredAssessments.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-muted-foreground">
                        {t('workforce.assessments.empty')}
                      </td>
                    </tr>
                  ) : (
                    filteredAssessments.map((a) => (
                      <tr
                        key={a.id}
                        className={cn(
                          'border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer',
                        )}
                        onClick={() => navigate(`/workforce/assessments/${a.id}/execute`)}
                      >
                        <td className="py-3 px-4 text-sm font-medium text-foreground">
                          {a.reference_number}
                        </td>
                        <td className="py-3 px-4 text-sm text-foreground">
                          {engineerMap[a.engineer_id] ?? `#${a.engineer_id}`}
                        </td>
                        <td className="py-3 px-4 text-sm text-foreground">
                          {templateMap[a.template_id] ?? `#${a.template_id}`}
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {a.asset_type_id
                            ? (assetTypes.find((at) => at.id === a.asset_type_id)?.name ??
                              `#${a.asset_type_id}`)
                            : '—'}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant={STATUS_VARIANTS[a.status] || 'secondary'}>
                            {a.status?.replace(/_/g, ' ') ?? '—'}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {formatScheduledDate(a.scheduled_date)}
                        </td>
                        <td className="py-3 px-4">
                          {a.outcome ? (
                            <Badge variant={OUTCOME_VARIANTS[a.outcome] || 'secondary'}>
                              {a.outcome.replace(/_/g, ' ')}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
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
