import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Truck,
  Loader2,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Flag,
  Plus,
  Download,
  RefreshCw,
  BarChart3,
  Calendar,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react'
import {
  vehicleChecklistsApi,
  getApiErrorMessage,
  type VehicleDefect,
  type AnalyticsSummary,
  type TrendDataPoint,
  type HeatmapEntry,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { TableSkeleton } from '../components/ui/SkeletonLoader'

type TabKey = 'daily' | 'monthly' | 'defects'
type ChecklistViewMode = 'records' | 'driver' | 'day' | 'completion'

const getPriorityVariant = (p: string): BadgeVariant => {
  switch (p) {
    case 'P1':
      return 'critical'
    case 'P2':
      return 'high'
    case 'P3':
      return 'medium'
    default:
      return 'secondary'
  }
}

const getStatusVariant = (s: string): BadgeVariant => {
  switch (s) {
    case 'open':
    case 'auto_detected':
      return 'submitted'
    case 'acknowledged':
      return 'acknowledged'
    case 'action_assigned':
      return 'in-progress'
    case 'resolved':
      return 'resolved'
    case 'dismissed':
      return 'closed'
    default:
      return 'secondary'
  }
}

const TECHNICIAN_NAME_KEYS = ['technician', 'driver', 'employee', 'engineer', 'user', 'staff', 'operative']
const TECHNICIAN_ID_KEYS = ['technicianid', 'driverid', 'employeeid', 'userid', 'staffid', 'engineerid']
const VEHICLE_KEYS = ['vanid', 'vanreg', 'vehicle', 'registration', 'reg']
const DATE_KEYS = ['starttimedate', 'date', 'checkdate', 'createdat', 'submittedat']

const normalizeValue = (value: unknown) => String(value ?? '').trim()
const normalizeKey = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, '')

function getRecordValue(record: Record<string, unknown>, keyHints: string[]): string {
  for (const [key, value] of Object.entries(record)) {
    const normalizedKey = normalizeKey(key)
    if (keyHints.some((hint) => normalizedKey.includes(hint))) {
      const normalized = normalizeValue(value)
      if (normalized) return normalized
    }
  }
  return ''
}

function getChecklistDate(record: Record<string, unknown>): Date | null {
  const rawValue = getRecordValue(record, DATE_KEYS)
  if (!rawValue) return null
  const parsed = new Date(rawValue)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function getTechnicianName(record: Record<string, unknown>): string {
  return getRecordValue(record, TECHNICIAN_NAME_KEYS)
}

function getTechnicianId(record: Record<string, unknown>): string {
  return getRecordValue(record, TECHNICIAN_ID_KEYS)
}

function getVehicleIdentifier(record: Record<string, unknown>): string {
  return getRecordValue(record, VEHICLE_KEYS)
}

function getChecklistStats(record: Record<string, unknown>) {
  let answeredCount = 0
  let passCount = 0
  let failCount = 0

  Object.entries(record).forEach(([key, value]) => {
    if (key.startsWith('_')) return
    const normalized = normalizeValue(value).toLowerCase()
    if (!normalized) return
    if (['pass', 'yes', '1', 'true', 'ok'].includes(normalized)) {
      answeredCount += 1
      passCount += 1
      return
    }
    if (['fail', 'no', '0', 'false'].includes(normalized)) {
      answeredCount += 1
      failCount += 1
    }
  })

  const completionRate = answeredCount > 0 ? Math.round((passCount / answeredCount) * 100) : 0

  return {
    answeredCount,
    passCount,
    failCount,
    completionRate,
    hasIssues: failCount > 0,
  }
}

function toDateInputValue(date: Date): string {
  return date.toISOString().split('T')[0]
}

function getWeekDateRange(weekValue: string): { start: string; end: string } | null {
  if (!weekValue) return null
  const [yearText, weekText] = weekValue.split('-W')
  const year = Number(yearText)
  const week = Number(weekText)
  if (!year || !week) return null

  const firstDay = new Date(Date.UTC(year, 0, 1))
  const dayOffset = firstDay.getUTCDay() || 7
  const monday = new Date(firstDay)
  monday.setUTCDate(firstDay.getUTCDate() + (week - 1) * 7 - (dayOffset - 1))
  const sunday = new Date(monday)
  sunday.setUTCDate(monday.getUTCDate() + 6)

  return {
    start: toDateInputValue(monday),
    end: toDateInputValue(sunday),
  }
}

export default function VehicleChecklists() {
  useTranslation()

  const [activeTab, setActiveTab] = useState<TabKey>('daily')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // Checklist data
  const [checklistItems, setChecklistItems] = useState<Record<string, unknown>[]>([])
  const [checklistPage, setChecklistPage] = useState(1)
  const [checklistPages, setChecklistPages] = useState(1)

  // Defects data
  const [defects, setDefects] = useState<VehicleDefect[]>([])
  const [defectsTotal, setDefectsTotal] = useState(0)
  const [defectsPage, setDefectsPage] = useState(1)
  const [defectsPages, setDefectsPages] = useState(1)

  // Analytics
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [, setTrends] = useState<TrendDataPoint[]>([])
  const [heatmap, setHeatmap] = useState<HeatmapEntry[]>([])

  // Dialogs
  const [showFlagDialog, setShowFlagDialog] = useState(false)
  const [showActionDialog, setShowActionDialog] = useState(false)
  const [showDetailDialog, setShowDetailDialog] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<Record<string, unknown> | null>(null)
  const [selectedDefect, setSelectedDefect] = useState<VehicleDefect | null>(null)
  const [creating, setCreating] = useState(false)

  // Flag defect form
  const [flagForm, setFlagForm] = useState({
    check_field: '',
    check_value: '',
    priority: 'P2',
    notes: '',
    vehicle_reg: '',
  })

  // Action form
  const [actionForm, setActionForm] = useState({
    title: '',
    description: '',
    due_date: '',
    assigned_to_email: '',
  })

  // Priority filter for defects tab
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [viewMode, setViewMode] = useState<ChecklistViewMode>('records')
  const [technicianFilterMode, setTechnicianFilterMode] = useState<'name' | 'id'>('name')
  const [technicianFilter, setTechnicianFilter] = useState('')
  const [vanFilter, setVanFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'flagged' | 'clean'>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selectedWeek, setSelectedWeek] = useState('')

  const pageSize = 250

  const loadChecklists = useCallback(
    async (tab: TabKey, page: number) => {
      if (tab === 'defects') return
      setLoading(true)
      setLoadError('')
      try {
        const fetcher = tab === 'daily' ? vehicleChecklistsApi.listDaily : vehicleChecklistsApi.listMonthly
        const res = await fetcher(page, pageSize)
        const data = res.data
        setChecklistItems(data.items)
        setChecklistPages(data.pages)
      } catch (err) {
        const msg = getApiErrorMessage(err)
        setLoadError(msg)
        console.error('Checklist load error:', msg)
      } finally {
        setLoading(false)
      }
    },
    [pageSize],
  )

  const loadDefects = useCallback(
    async (page: number, priority?: string) => {
      setLoading(true)
      setLoadError('')
      try {
        const res = await vehicleChecklistsApi.listDefects(page, pageSize, priority || undefined)
        const data = res.data
        setDefects(data.items)
        setDefectsTotal(data.total)
        setDefectsPages(data.pages)
      } catch (err) {
        const msg = getApiErrorMessage(err)
        setLoadError(msg)
        console.error('Defects load error:', msg)
      } finally {
        setLoading(false)
      }
    },
    [pageSize],
  )

  const loadAnalytics = useCallback(async () => {
    try {
      const [summaryRes, trendsRes, heatmapRes] = await Promise.allSettled([
        vehicleChecklistsApi.analyticsSummary(),
        vehicleChecklistsApi.analyticsTrends(30),
        vehicleChecklistsApi.analyticsHeatmap(10),
      ])
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value.data)
      if (trendsRes.status === 'fulfilled') setTrends(trendsRes.value.data)
      if (heatmapRes.status === 'fulfilled') setHeatmap(heatmapRes.value.data)
    } catch {
      // Non-blocking
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'defects') {
      loadDefects(defectsPage, priorityFilter)
    } else {
      loadChecklists(activeTab, checklistPage)
    }
    loadAnalytics()
  }, [activeTab, checklistPage, defectsPage, priorityFilter, loadChecklists, loadDefects, loadAnalytics])

  const handleFlagDefect = (record: Record<string, unknown>, field?: string) => {
    setSelectedRecord(record)
    setFlagForm({
      check_field: field || '',
      check_value: field ? String(record[field] ?? '') : '',
      priority: 'P2',
      notes: '',
      vehicle_reg: String(record['vanID'] || record['vanReg'] || record['registration'] || record['reg'] || record['VehicleReg'] || '').trim(),
    })
    setShowFlagDialog(true)
  }

  const submitFlagDefect = async () => {
    if (!selectedRecord) return
    setCreating(true)
    try {
      const pamsId = Number(
        selectedRecord['_pams_id'] || selectedRecord['id'] || selectedRecord['ID'] || 0,
      )
      await vehicleChecklistsApi.createDefect({
        pams_table: activeTab === 'monthly' ? 'monthly' : 'daily',
        pams_record_id: pamsId,
        check_field: flagForm.check_field,
        check_value: flagForm.check_value,
        priority: flagForm.priority,
        notes: flagForm.notes,
        vehicle_reg: flagForm.vehicle_reg,
      })
      toast.success('Defect flagged successfully')
      setShowFlagDialog(false)
      loadAnalytics()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const handleCreateAction = (defect: VehicleDefect) => {
    setSelectedDefect(defect)
    setActionForm({ title: '', description: '', due_date: '', assigned_to_email: '' })
    setShowActionDialog(true)
  }

  const submitCreateAction = async () => {
    if (!selectedDefect) return
    setCreating(true)
    try {
      await vehicleChecklistsApi.createDefectAction(selectedDefect.id, {
        title: actionForm.title,
        description: actionForm.description,
        due_date: actionForm.due_date || undefined,
        assigned_to_email: actionForm.assigned_to_email || undefined,
      })
      toast.success('Action created against defect')
      setShowActionDialog(false)
      loadDefects(defectsPage, priorityFilter)
      loadAnalytics()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const handleExport = async (type: 'daily' | 'monthly' | 'defects') => {
    try {
      const fetcher =
        type === 'daily'
          ? vehicleChecklistsApi.exportDailyCsv
          : type === 'monthly'
            ? vehicleChecklistsApi.exportMonthlyCsv
            : vehicleChecklistsApi.exportDefectsCsv

      const res = await fetcher()
      const blob = new Blob([res.data as BlobPart], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${type}_export.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Export downloaded')
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    }
  }

  const handleSync = async () => {
    try {
      await vehicleChecklistsApi.triggerSync()
      toast.success('PAMS sync queued')
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    }
  }

  const viewRecordDetail = (record: Record<string, unknown>) => {
    setSelectedRecord(record)
    setShowDetailDialog(true)
  }

  const handleWeekChange = (weekValue: string) => {
    setSelectedWeek(weekValue)
    const range = getWeekDateRange(weekValue)
    if (!range) {
      setDateFrom('')
      setDateTo('')
      return
    }
    setDateFrom(range.start)
    setDateTo(range.end)
  }

  const tabs: { key: TabKey; label: string; icon: typeof Calendar }[] = [
    { key: 'daily', label: 'Daily Checklists', icon: Calendar },
    { key: 'monthly', label: 'Monthly Checklists', icon: Calendar },
    { key: 'defects', label: 'Flagged Defects', icon: Flag },
  ]

  const checklistColumns = checklistItems.length > 0
    ? Object.keys(checklistItems[0]).filter((k) => !k.startsWith('_'))
    : []

  const filteredChecklistItems = useMemo(() => {
    return checklistItems.filter((record) => {
      const technicianName = getTechnicianName(record).toLowerCase()
      const technicianId = getTechnicianId(record).toLowerCase()
      const vehicleId = getVehicleIdentifier(record).toLowerCase()
      const checklistDate = getChecklistDate(record)
      const stats = getChecklistStats(record)

      if (technicianFilter.trim()) {
        const target =
          technicianFilterMode === 'name'
            ? technicianName
            : technicianId || `${technicianName} ${technicianId}`.trim()
        if (!target.includes(technicianFilter.trim().toLowerCase())) {
          return false
        }
      }

      if (vanFilter.trim() && !vehicleId.includes(vanFilter.trim().toLowerCase())) {
        return false
      }

      if (statusFilter === 'flagged' && !stats.hasIssues) {
        return false
      }
      if (statusFilter === 'clean' && stats.hasIssues) {
        return false
      }

      if ((dateFrom || dateTo) && checklistDate) {
        const recordDate = toDateInputValue(checklistDate)
        if (dateFrom && recordDate < dateFrom) return false
        if (dateTo && recordDate > dateTo) return false
      } else if ((dateFrom || dateTo) && !checklistDate) {
        return false
      }

      return true
    })
  }, [
    checklistItems,
    technicianFilter,
    technicianFilterMode,
    vanFilter,
    statusFilter,
    dateFrom,
    dateTo,
  ])

  const groupedByDriver = useMemo(() => {
    const groups = new Map<string, { name: string; id: string; records: number; flagged: number; completionTotal: number }>()
    filteredChecklistItems.forEach((record) => {
      const name = getTechnicianName(record) || 'Unassigned technician'
      const id = getTechnicianId(record)
      const key = `${name}::${id}`
      const stats = getChecklistStats(record)
      const current = groups.get(key) || { name, id, records: 0, flagged: 0, completionTotal: 0 }
      current.records += 1
      current.flagged += stats.hasIssues ? 1 : 0
      current.completionTotal += stats.completionRate
      groups.set(key, current)
    })
    return Array.from(groups.values()).sort((a, b) => b.records - a.records)
  }, [filteredChecklistItems])

  const groupedByDay = useMemo(() => {
    const groups = new Map<string, { date: string; records: number; flagged: number; completionTotal: number }>()
    filteredChecklistItems.forEach((record) => {
      const date = getChecklistDate(record)
      const key = date ? toDateInputValue(date) : 'Unknown date'
      const stats = getChecklistStats(record)
      const current = groups.get(key) || { date: key, records: 0, flagged: 0, completionTotal: 0 }
      current.records += 1
      current.flagged += stats.hasIssues ? 1 : 0
      current.completionTotal += stats.completionRate
      groups.set(key, current)
    })
    return Array.from(groups.values()).sort((a, b) => b.date.localeCompare(a.date))
  }, [filteredChecklistItems])

  const completionRows = useMemo(() => {
    return filteredChecklistItems.map((record, index) => {
      const stats = getChecklistStats(record)
      return {
        id: Number(record['_pams_id'] || record['id'] || index),
        technician: getTechnicianName(record) || 'Unassigned technician',
        technicianId: getTechnicianId(record),
        vehicle: getVehicleIdentifier(record) || 'Unknown vehicle',
        date: getChecklistDate(record),
        ...stats,
      }
    })
  }, [filteredChecklistItems])

  const checklistSummaryMetrics = useMemo(() => {
    const distinctTechnicians = new Set(
      filteredChecklistItems.map((record) => `${getTechnicianName(record)}::${getTechnicianId(record)}`),
    )
    const flaggedRecords = filteredChecklistItems.filter((record) => getChecklistStats(record).hasIssues).length
    const averageCompletion = completionRows.length
      ? Math.round(completionRows.reduce((sum, row) => sum + row.completionRate, 0) / completionRows.length)
      : 0
    const totalFailedChecks = completionRows.reduce((sum, row) => sum + row.failCount, 0)
    return {
      records: filteredChecklistItems.length,
      technicians: distinctTechnicians.size,
      flaggedRecords,
      averageCompletion,
      totalFailedChecks,
    }
  }, [filteredChecklistItems, completionRows])

  const visibleDates = useMemo(() => {
    return Array.from(
      new Set(
        filteredChecklistItems
          .map((record) => getChecklistDate(record))
          .filter((date): date is Date => Boolean(date))
          .map((date) => toDateInputValue(date)),
      ),
    )
      .sort()
      .slice(-7)
  }, [filteredChecklistItems])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Truck className="h-6 w-6 text-primary" />
            Van Checklists
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            PAMS vehicle checklist data with governance defect tracking
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleSync}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Sync
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport(activeTab === 'defects' ? 'defects' : activeTab)}
          >
            <Download className="h-4 w-4 mr-1" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Card>
          <CardContent className="p-3 text-center">
            <p className="text-2xl font-bold text-foreground">{checklistSummaryMetrics.records}</p>
            <p className="text-xs text-muted-foreground">Records Shown</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <p className="text-2xl font-bold text-foreground">{checklistSummaryMetrics.technicians}</p>
            <p className="text-xs text-muted-foreground">Technicians</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <p className="text-2xl font-bold text-foreground">{checklistSummaryMetrics.averageCompletion}%</p>
            <p className="text-xs text-muted-foreground">Avg Completion</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <p className="text-2xl font-bold text-red-600">{checklistSummaryMetrics.flaggedRecords}</p>
            <p className="text-xs text-muted-foreground">Flagged Records</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{checklistSummaryMetrics.totalFailedChecks}</p>
            <p className="text-xs text-muted-foreground">Failed Checks</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <p className="text-2xl font-bold text-destructive">{summary?.open_defects ?? 0}</p>
            <p className="text-xs text-muted-foreground">Open Defects</p>
          </CardContent>
        </Card>
      </div>

      {/* Heatmap (top failing checks) */}
      {heatmap.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              Most Frequently Failed Checks
            </h3>
            <div className="flex flex-wrap gap-2">
              {heatmap.map((entry, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-destructive/10 border border-destructive/20"
                >
                  <XCircle className="h-3.5 w-3.5 text-destructive" />
                  <span className="text-xs font-medium text-foreground">{entry.check_field}</span>
                  <Badge variant="destructive">{entry.failure_count}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <div className="border-b border-border">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key)
                if (tab.key === 'defects') setDefectsPage(1)
                else setChecklistPage(1)
              }}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
              {tab.key === 'defects' && summary && summary.open_defects > 0 && (
                <Badge variant="critical" className="ml-1">
                  {summary.open_defects}
                </Badge>
              )}
            </button>
          ))}
        </div>
      </div>

      {activeTab !== 'defects' && (
        <>
          <Card>
            <CardContent className="p-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3">
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Technician filter</p>
                  <Select value={technicianFilterMode} onValueChange={(value) => setTechnicianFilterMode(value as 'name' | 'id')}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="name">By Name</SelectItem>
                      <SelectItem value="id">By ID</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Technician</p>
                  <Input
                    value={technicianFilter}
                    onChange={(event) => setTechnicianFilter(event.target.value)}
                    placeholder={technicianFilterMode === 'name' ? 'Search technician name' : 'Search technician ID'}
                  />
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Van ID / Reg</p>
                  <Input
                    value={vanFilter}
                    onChange={(event) => setVanFilter(event.target.value)}
                    placeholder="Filter by van"
                  />
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">From</p>
                  <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">To</p>
                  <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Week</p>
                  <Input type="week" value={selectedWeek} onChange={(event) => handleWeekChange(event.target.value)} />
                </div>
              </div>

              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-wrap gap-2">
                  {([
                    ['records', 'Raw Records'],
                    ['driver', 'By Driver'],
                    ['day', 'By Day'],
                    ['completion', 'Completion %'],
                  ] as const).map(([mode, label]) => (
                    <Button
                      key={mode}
                      variant={viewMode === mode ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setViewMode(mode)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <div className="flex items-center gap-3">
                  <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as 'all' | 'flagged' | 'clean')}>
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="flagged">Flagged only</SelectItem>
                      <SelectItem value="clean">No issues</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setTechnicianFilter('')
                      setVanFilter('')
                      setStatusFilter('all')
                      setDateFrom('')
                      setDateTo('')
                      setSelectedWeek('')
                    }}
                  >
                    Clear filters
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {visibleDates.length > 0 && (
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Calendar className="h-4 w-4 text-primary" />
                  <h3 className="text-sm font-semibold text-foreground">Visible Week / Date Coverage</h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  {visibleDates.map((date) => (
                    <button
                      key={date}
                      type="button"
                      onClick={() => {
                        setDateFrom(date)
                        setDateTo(date)
                        setSelectedWeek('')
                      }}
                      className="rounded-lg border border-border bg-secondary px-3 py-1.5 text-sm text-foreground hover:border-primary"
                    >
                      {new Date(date).toLocaleDateString()}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Error Banner */}
      {loadError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <p className="text-sm font-medium">{loadError}</p>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : activeTab === 'defects' ? (
        /* Defects Table */
        <Card>
          <CardContent className="p-0">
            <div className="flex items-center gap-3 p-4 border-b border-border">
              <Select
                value={priorityFilter}
                onValueChange={(v) => {
                  setPriorityFilter(v === 'all' ? '' : v)
                  setDefectsPage(1)
                }}
              >
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="All Priorities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Priorities</SelectItem>
                  <SelectItem value="P1">P1 Critical</SelectItem>
                  <SelectItem value="P2">P2 High</SelectItem>
                  <SelectItem value="P3">P3 Medium</SelectItem>
                </SelectContent>
              </Select>
              <span className="text-sm text-muted-foreground ml-auto">
                {defectsTotal} defect{defectsTotal !== 1 ? 's' : ''}
              </span>
            </div>

            {defects.length === 0 ? (
              <div className="p-12 text-center">
                <CheckCircle2 className="h-12 w-12 text-success mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-foreground">No defects flagged</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Review checklists in the Daily or Monthly tabs to flag defects.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="text-left p-3 font-medium text-muted-foreground">Priority</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Vehicle</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Check Field</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Value</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Status</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Source</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Created</th>
                      <th className="text-right p-3 font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {defects.map((defect) => (
                      <tr key={defect.id} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="p-3">
                          <Badge variant={getPriorityVariant(defect.priority)}>
                            {defect.priority}
                          </Badge>
                        </td>
                        <td className="p-3 font-medium text-foreground">
                          {defect.vehicle_reg || '—'}
                        </td>
                        <td className="p-3 text-foreground">{defect.check_field}</td>
                        <td className="p-3 text-muted-foreground">{defect.check_value || '—'}</td>
                        <td className="p-3">
                          <Badge variant={getStatusVariant(defect.status)}>{defect.status}</Badge>
                        </td>
                        <td className="p-3 text-muted-foreground capitalize">{defect.pams_table}</td>
                        <td className="p-3 text-muted-foreground">
                          {defect.created_at
                            ? new Date(defect.created_at).toLocaleDateString()
                            : '—'}
                        </td>
                        <td className="p-3 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleCreateAction(defect)}
                          >
                            <Plus className="h-3.5 w-3.5 mr-1" />
                            Action
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Defects pagination */}
            {defectsPages > 1 && (
              <div className="flex items-center justify-between p-4 border-t border-border">
                <span className="text-sm text-muted-foreground">
                  Page {defectsPage} of {defectsPages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={defectsPage <= 1}
                    onClick={() => setDefectsPage((p) => p - 1)}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={defectsPage >= defectsPages}
                    onClick={() => setDefectsPage((p) => p + 1)}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        /* Checklists Table */
        <Card>
          <CardContent className="p-0">
            <div className="flex items-center gap-3 p-4 border-b border-border">
              <span className="text-sm text-muted-foreground">
                {filteredChecklistItems.length} record{filteredChecklistItems.length !== 1 ? 's' : ''}
              </span>
            </div>

            {filteredChecklistItems.length === 0 ? (
              <div className="p-12 text-center">
                <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-foreground">No checklist data matches these filters</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Adjust the technician, date, or status filters to broaden the view.
                </p>
              </div>
            ) : viewMode === 'driver' ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="text-left p-3 font-medium text-muted-foreground">Driver / Technician</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">ID</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Records</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Flagged</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Avg Completion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedByDriver.map((group) => (
                      <tr key={`${group.name}-${group.id}`} className="border-b border-border/50">
                        <td className="p-3 font-medium text-foreground">{group.name}</td>
                        <td className="p-3 text-muted-foreground">{group.id || '—'}</td>
                        <td className="p-3 text-foreground">{group.records}</td>
                        <td className="p-3 text-foreground">{group.flagged}</td>
                        <td className="p-3 text-foreground">
                          {group.records > 0 ? Math.round(group.completionTotal / group.records) : 0}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : viewMode === 'day' ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="text-left p-3 font-medium text-muted-foreground">Day</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Records</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Flagged</th>
                      <th className="text-left p-3 font-medium text-muted-foreground">Avg Completion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedByDay.map((group) => (
                      <tr key={group.date} className="border-b border-border/50">
                        <td className="p-3 font-medium text-foreground">
                          {group.date === 'Unknown date' ? group.date : new Date(group.date).toLocaleDateString()}
                        </td>
                        <td className="p-3 text-foreground">{group.records}</td>
                        <td className="p-3 text-foreground">{group.flagged}</td>
                        <td className="p-3 text-foreground">
                          {group.records > 0 ? Math.round(group.completionTotal / group.records) : 0}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : viewMode === 'completion' ? (
              <div className="divide-y divide-border">
                {completionRows.map((row) => (
                  <div key={row.id} className="p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="font-medium text-foreground">{row.technician}</p>
                      <p className="text-sm text-muted-foreground">
                        {row.technicianId || 'No technician ID'} • {row.vehicle}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {row.date ? row.date.toLocaleDateString() : 'Unknown date'}
                      </p>
                    </div>
                    <div className="w-full md:w-72">
                      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                        <span>Completion</span>
                        <span>{row.completionRate}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full ${row.hasIssues ? 'bg-orange-500' : 'bg-emerald-500'}`}
                          style={{ width: `${row.completionRate}%` }}
                        />
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {row.passCount} pass / {row.failCount} fail
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      {checklistColumns.slice(0, 12).map((col) => (
                        <th
                          key={col}
                          className="text-left p-3 font-medium text-muted-foreground whitespace-nowrap"
                        >
                          {col.replace(/_/g, ' ')}
                        </th>
                      ))}
                      <th className="text-right p-3 font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredChecklistItems.map((item, idx) => (
                      <tr
                        key={idx}
                        className="border-b border-border/50 hover:bg-muted/30 cursor-pointer"
                        onClick={() => viewRecordDetail(item)}
                      >
                        {checklistColumns.slice(0, 12).map((col) => {
                          const val = item[col]
                          const strVal = val == null ? '' : String(val)
                          const isFailure =
                            strVal.toLowerCase() === 'fail' ||
                            strVal.toLowerCase() === 'no' ||
                            strVal === '0'
                          const isPass =
                            strVal.toLowerCase() === 'pass' ||
                            strVal.toLowerCase() === 'yes' ||
                            strVal === '1'
                          return (
                            <td
                              key={col}
                              className={`p-3 whitespace-nowrap ${
                                isFailure
                                  ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 font-medium'
                                  : isPass
                                    ? 'text-success'
                                    : 'text-foreground'
                              }`}
                            >
                              {strVal || '—'}
                            </td>
                          )
                        })}
                        <td className="p-3 text-right" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleFlagDefect(item)}
                          >
                            <Flag className="h-3.5 w-3.5 mr-1" />
                            Flag
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Checklist pagination */}
            {viewMode === 'records' && checklistPages > 1 && (
              <div className="flex items-center justify-between p-4 border-t border-border">
                <span className="text-sm text-muted-foreground">
                  Page {checklistPage} of {checklistPages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={checklistPage <= 1}
                    onClick={() => setChecklistPage((p) => p - 1)}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={checklistPage >= checklistPages}
                    onClick={() => setChecklistPage((p) => p + 1)}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Record Detail Dialog */}
      <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Checklist Record Detail</DialogTitle>
          </DialogHeader>
          {selectedRecord && (
            <div className="space-y-3">
              {Object.entries(selectedRecord)
                .filter(([k]) => !k.startsWith('_'))
                .map(([key, value]) => {
                  const strVal = value == null ? '' : String(value)
                  const isFailure =
                    strVal.toLowerCase() === 'fail' ||
                    strVal.toLowerCase() === 'no' ||
                    strVal === '0'
                  return (
                    <div
                      key={key}
                      className={`flex items-start justify-between p-2 rounded-lg ${
                        isFailure ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800' : 'bg-muted/30'
                      }`}
                    >
                      <span className="text-sm font-medium text-muted-foreground min-w-[140px]">
                        {key.replace(/_/g, ' ')}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-sm ${isFailure ? 'text-red-700 dark:text-red-400 font-semibold' : 'text-foreground'}`}>
                          {strVal || '—'}
                        </span>
                        {isFailure && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => {
                              setShowDetailDialog(false)
                              handleFlagDefect(selectedRecord, key)
                            }}
                          >
                            <Flag className="h-3 w-3 mr-1" />
                            Flag
                          </Button>
                        )}
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Flag Defect Dialog */}
      <Dialog open={showFlagDialog} onOpenChange={setShowFlagDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Flag Vehicle Defect</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label htmlFor="flag-check-field" className="text-sm font-medium text-foreground">Check Field</label>
              <Input
                id="flag-check-field"
                value={flagForm.check_field}
                onChange={(e) => setFlagForm((f) => ({ ...f, check_field: e.target.value }))}
                placeholder="e.g. brakes, tyres, lights"
              />
            </div>
            <div>
              <label htmlFor="flag-check-value" className="text-sm font-medium text-foreground">Current Value</label>
              <Input
                id="flag-check-value"
                value={flagForm.check_value}
                onChange={(e) => setFlagForm((f) => ({ ...f, check_value: e.target.value }))}
                placeholder="e.g. fail, no, 0"
              />
            </div>
            <div>
              <label htmlFor="flag-vehicle-reg" className="text-sm font-medium text-foreground">Vehicle Registration</label>
              <Input
                id="flag-vehicle-reg"
                value={flagForm.vehicle_reg}
                onChange={(e) => setFlagForm((f) => ({ ...f, vehicle_reg: e.target.value }))}
                placeholder="e.g. AB12 CDE"
              />
            </div>
            <div>
              <label htmlFor="flag-priority" className="text-sm font-medium text-foreground">Priority</label>
              <div className="flex gap-2 mt-1">
                {(['P1', 'P2', 'P3'] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setFlagForm((f) => ({ ...f, priority: p }))}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold border-2 transition-all ${
                      flagForm.priority === p
                        ? p === 'P1'
                          ? 'bg-red-100 dark:bg-red-900/30 border-red-500 text-red-700 dark:text-red-300'
                          : p === 'P2'
                            ? 'bg-orange-100 dark:bg-orange-900/30 border-orange-500 text-orange-700 dark:text-orange-300'
                            : 'bg-yellow-100 dark:bg-yellow-900/30 border-yellow-500 text-yellow-700 dark:text-yellow-300'
                        : 'border-border text-muted-foreground hover:border-primary/50'
                    }`}
                  >
                    {p}
                    <span className="block text-xs font-normal mt-0.5">
                      {p === 'P1' ? 'Critical' : p === 'P2' ? 'High' : 'Medium'}
                    </span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label htmlFor="flag-notes" className="text-sm font-medium text-foreground">Notes</label>
              <Textarea
                id="flag-notes"
                value={flagForm.notes}
                onChange={(e) => setFlagForm((f) => ({ ...f, notes: e.target.value }))}
                placeholder="Describe the defect..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowFlagDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={submitFlagDefect}
              disabled={creating || !flagForm.check_field}
            >
              {creating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Flagging...
                </>
              ) : (
                <>
                  <Flag className="h-4 w-4 mr-1" />
                  Flag Defect
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Action Dialog */}
      <Dialog open={showActionDialog} onOpenChange={setShowActionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Create Action — {selectedDefect?.vehicle_reg || 'Defect'} ({selectedDefect?.priority})
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label htmlFor="action-title" className="text-sm font-medium text-foreground">Title</label>
              <Input
                id="action-title"
                value={actionForm.title}
                onChange={(e) => setActionForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Action title"
              />
            </div>
            <div>
              <label htmlFor="action-description" className="text-sm font-medium text-foreground">Description</label>
              <Textarea
                id="action-description"
                value={actionForm.description}
                onChange={(e) => setActionForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Describe the corrective action..."
                rows={3}
              />
            </div>
            <div>
              <label htmlFor="action-due-date" className="text-sm font-medium text-foreground">Due Date</label>
              <Input
                id="action-due-date"
                type="date"
                value={actionForm.due_date}
                onChange={(e) => setActionForm((f) => ({ ...f, due_date: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="action-assigned-to" className="text-sm font-medium text-foreground">Assign To (email)</label>
              <Input
                id="action-assigned-to"
                type="email"
                value={actionForm.assigned_to_email}
                onChange={(e) => setActionForm((f) => ({ ...f, assigned_to_email: e.target.value }))}
                placeholder="user@company.com"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowActionDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={submitCreateAction}
              disabled={creating || !actionForm.title || !actionForm.description}
            >
              {creating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-1" />
                  Create Action
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Last sync info */}
      {summary?.last_sync && (
        <p className="text-xs text-muted-foreground text-right flex items-center justify-end gap-1">
          <Clock className="h-3 w-3" />
          Last synced: {new Date(summary.last_sync).toLocaleString()}
        </p>
      )}
    </div>
  )
}
