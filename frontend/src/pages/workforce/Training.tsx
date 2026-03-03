import { useState, useEffect } from 'react'
import { Plus, Search, Filter, ChevronRight, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { workforceApi, auditsApi, getApiErrorMessage, type InductionRun, type AssetType } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'

const STATUS_VARIANTS: Record<string, 'success' | 'warning' | 'info' | 'destructive' | 'secondary'> = {
  completed: 'success',
  in_progress: 'warning',
  draft: 'info',
  cancelled: 'destructive',
}

export default function Training() {
  const navigate = useNavigate()
  const [inductions, setInductions] = useState<InductionRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [stageFilter, setStageFilter] = useState('')
  const [engineerMap, setEngineerMap] = useState<Record<number, string>>({})
  const [templateMap, setTemplateMap] = useState<Record<number, string>>({})
  const [assetTypes, setAssetTypes] = useState<AssetType[]>([])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  useEffect(() => {
    workforceApi.listEngineers({ page: '1', page_size: '500' })
      .then((res) => {
        const map: Record<number, string> = {}
        for (const e of res.data?.items || []) {
          map[e.id] = e.employee_number || e.job_title || `#${e.id}`
        }
        setEngineerMap(map)
      })
      .catch(() => {})
    auditsApi.listTemplates(1, 500, { is_published: true })
      .then((res) => {
        const map: Record<number, string> = {}
        for (const t of res.data?.items || []) {
          map[t.id] = t.name
        }
        setTemplateMap(map)
      })
      .catch(() => {})
    workforceApi.listAssetTypes()
      .then((res) => setAssetTypes(res.data?.items || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const params: Record<string, string> = { page: '1', page_size: '50' }
        if (debouncedSearch) params.search = debouncedSearch
        if (statusFilter) params.status = statusFilter
        if (stageFilter) params.stage = stageFilter
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
  }, [debouncedSearch, statusFilter, stageFilter])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Training & Inductions</h1>
          <p className="text-muted-foreground mt-1">
            Manage training and induction runs for engineers
          </p>
        </div>
        <Button onClick={() => navigate('/workforce/training/new')} className="gap-2">
          <Plus className="w-4 h-4" />
          New Training
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search by reference, engineer..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
              >
                <option value="">All statuses</option>
                <option value="draft">Draft</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <select
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
              >
                <option value="">All stages</option>
                <option value="stage_1_onsite">Stage 1 (On-site)</option>
                <option value="stage_2_field">Stage 2 (Field)</option>
              </select>
              <Button variant="outline" size="sm" className="gap-2">
                <Filter className="w-4 h-4" />
                Filters
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
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Reference</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Engineer</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Template</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Asset Type</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Stage</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Date</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {inductions.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-muted-foreground">
                        No training runs found. Create one to get started.
                      </td>
                    </tr>
                  ) : (
                    inductions.map((i) => (
                      <tr
                        key={i.id}
                        className={cn(
                          "border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer",
                        )}
                        onClick={() => navigate(`/workforce/training/${i.id}/execute`)}
                      >
                        <td className="py-3 px-4 text-sm font-medium text-foreground">{i.reference_number}</td>
                        <td className="py-3 px-4 text-sm text-foreground">{engineerMap[i.engineer_id] ?? `#${i.engineer_id}`}</td>
                        <td className="py-3 px-4 text-sm text-foreground">{templateMap[i.template_id] ?? `#${i.template_id}`}</td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">{i.asset_type_id ? (assetTypes.find(at => at.id === i.asset_type_id)?.name ?? `#${i.asset_type_id}`) : '—'}</td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">{i.stage?.replace(/_/g, ' ') ?? '—'}</td>
                        <td className="py-3 px-4">
                          <Badge variant={STATUS_VARIANTS[i.status] || 'secondary'}>
                            {i.status?.replace(/_/g, ' ') ?? '—'}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {i.scheduled_date ? new Date(i.scheduled_date).toLocaleDateString() : '—'}
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
