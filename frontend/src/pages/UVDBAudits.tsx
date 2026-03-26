import { useState, useEffect, useCallback } from 'react'
import {
  Shield,
  Leaf,
  HardHat,
  Lock,
  ChevronRight,
  FileText,
  Users,
  Building2,
  Truck,
  Wrench,
  BarChart3,
  RefreshCw,
  Plus,
  Search,
  Filter,
  Download,
  Calendar,
  Award,
  ClipboardList,
  ExternalLink,
  Link2,
  XCircle,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  uvdbApi,
  ErrorClass,
  createApiError,
  isSetupRequired,
  SetupRequiredResponse,
} from '../api/client'
import { SetupRequiredPanel } from '../components/ui/SetupRequiredPanel'

interface UVDBSection {
  number: string
  title: string
  max_score: number
  question_count: number
  iso_mapping: Record<string, string>
}

interface UVDBAudit {
  id: number
  audit_reference: string
  company_name: string
  audit_type: string
  audit_date: string | null
  status: string
  percentage_score: number | null
  lead_auditor: string | null
}

interface UVDBDashboardState {
  total_audits: number
  active_audits: number
  completed_audits: number
  average_score: number
  protocol_name: string
  protocol_version: string
}

interface UVDBIsoMappingRow {
  uvdb_section: string
  uvdb_question: string
  uvdb_text: string
  iso_9001: string[]
  iso_14001: string[]
  iso_45001: string[]
  iso_27001: string[]
}

// Bounded error state for deterministic UX
type LoadState = 'idle' | 'loading' | 'success' | 'error' | 'setup_required'

export default function UVDBAudits() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<'dashboard' | 'protocol' | 'audits' | 'mapping'>(
    'dashboard',
  )
  const [sections, setSections] = useState<UVDBSection[]>([])
  const [audits, setAudits] = useState<UVDBAudit[]>([])
  const [isoMappings, setIsoMappings] = useState<UVDBIsoMappingRow[]>([])
  const [dashboard, setDashboard] = useState<UVDBDashboardState | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [errorClass, setErrorClass] = useState<ErrorClass | null>(null)
  const [setupRequired, setSetupRequired] = useState<SetupRequiredResponse | null>(null)
  const [showCreateAuditForm, setShowCreateAuditForm] = useState(false)
  const [isCreatingAudit, setIsCreatingAudit] = useState(false)
  const [createAuditError, setCreateAuditError] = useState<string | null>(null)
  const [createAuditSuccess, setCreateAuditSuccess] = useState<string | null>(null)
  const [createAuditForm, setCreateAuditForm] = useState({
    company_name: 'Plantexpand Limited',
    audit_type: 'B2',
    audit_date: new Date().toISOString().split('T')[0] ?? '',
    lead_auditor: '',
  })

  // Transform API section to component type
  const transformSection = (apiSection: {
    number: string
    title: string
    max_score: number
    question_count: number
    iso_mapping: Record<string, string>
  }): UVDBSection => ({
    number: apiSection.number,
    title: apiSection.title,
    max_score: apiSection.max_score,
    question_count: apiSection.question_count,
    iso_mapping: apiSection.iso_mapping || {},
  })

  // Transform API audit to component type
  const transformAudit = (apiAudit: {
    id: number
    audit_reference: string
    company_name: string
    audit_type: string
    audit_date: string | null
    status: string
    percentage_score: number | null
    lead_auditor: string | null
  }): UVDBAudit => ({
    id: apiAudit.id,
    audit_reference: apiAudit.audit_reference,
    company_name: apiAudit.company_name,
    audit_type: apiAudit.audit_type,
    audit_date: apiAudit.audit_date,
    status: apiAudit.status,
    percentage_score: apiAudit.percentage_score,
    lead_auditor: apiAudit.lead_auditor,
  })

  const loadData = useCallback(async (isRetry = false) => {
      setLoadState('loading')
      setErrorClass(null)
      setSetupRequired(null)
      setCreateAuditError(null)

      try {
        const [dashboardResponse, sectionsResponse, auditsResponse, mappingResponse] = await Promise.all([
          uvdbApi.getDashboard(),
          uvdbApi.listSections(),
          uvdbApi.listAudits({ skip: 0, limit: 50 }),
          uvdbApi.getISOMapping(),
        ])

        if (isSetupRequired(dashboardResponse.data)) {
          setSetupRequired(dashboardResponse.data)
          setLoadState('setup_required')
          return
        }
        if (isSetupRequired(auditsResponse.data)) {
          setSetupRequired(auditsResponse.data)
          setLoadState('setup_required')
          return
        }
        if (isSetupRequired(sectionsResponse.data)) {
          setSetupRequired(sectionsResponse.data)
          setLoadState('setup_required')
          return
        }
        if (isSetupRequired(mappingResponse.data)) {
          setSetupRequired(mappingResponse.data)
          setLoadState('setup_required')
          return
        }

        setDashboard({
          total_audits: dashboardResponse.data.summary.total_audits,
          active_audits: dashboardResponse.data.summary.active_audits,
          completed_audits: dashboardResponse.data.summary.completed_audits,
          average_score: dashboardResponse.data.summary.average_score,
          protocol_name: dashboardResponse.data.protocol.name,
          protocol_version: dashboardResponse.data.protocol.version,
        })

        const transformedSections = sectionsResponse.data.sections.map(transformSection)
        transformedSections.sort((a, b) => parseInt(a.number) - parseInt(b.number))
        const mappings = mappingResponse.data.mappings
        const enrichedSections = transformedSections.map((section) => {
          const sectionMappings = mappings.filter((mapping) => mapping.uvdb_section === section.number)
          if (sectionMappings.length === 0) return section
          return {
            ...section,
            iso_mapping: {
              ...(sectionMappings.some((mapping) => mapping.iso_9001.length > 0) ? { '9001': 'aligned' } : {}),
              ...(sectionMappings.some((mapping) => mapping.iso_14001.length > 0) ? { '14001': 'aligned' } : {}),
              ...(sectionMappings.some((mapping) => mapping.iso_45001.length > 0) ? { '45001': 'aligned' } : {}),
              ...(sectionMappings.some((mapping) => mapping.iso_27001.length > 0) ? { '27001': 'aligned' } : {}),
            },
          }
        })
        setSections(enrichedSections)

        const transformedAudits = auditsResponse.data.audits.map(transformAudit)
        transformedAudits.sort((a, b) => b.id - a.id)
        setAudits(transformedAudits)
        setIsoMappings(mappings)

        setLoadState('success')
      } catch (err) {
        const apiError = createApiError(err)
        setErrorClass(apiError.error_class)

        // Auto-retry once for transient network errors
        if (
          !isRetry &&
          (apiError.error_class === ErrorClass.NETWORK_ERROR ||
            apiError.error_class === ErrorClass.SERVER_ERROR)
        ) {
          await loadData(true)
          return
        }

        setLoadState('error')
      }
    }, [])

  const handleOpenCreateAuditForm = () => {
    setCreateAuditError(null)
    setCreateAuditSuccess(null)
    setCreateAuditForm((prev) => ({
      ...prev,
      company_name: audits[0]?.company_name || prev.company_name || 'Plantexpand Limited',
    }))
    setShowCreateAuditForm(true)
  }

  const handleCreateAudit = async (event: React.FormEvent) => {
    event.preventDefault()
    setCreateAuditError(null)
    setCreateAuditSuccess(null)

    if (!createAuditForm.company_name.trim()) {
      setCreateAuditError('Company name is required.')
      return
    }

    setIsCreatingAudit(true)
    try {
      const response = await uvdbApi.createAudit({
        company_name: createAuditForm.company_name.trim(),
        audit_type: createAuditForm.audit_type.trim() || 'B2',
        audit_date: createAuditForm.audit_date || undefined,
        lead_auditor: createAuditForm.lead_auditor.trim() || undefined,
      })
      setCreateAuditSuccess(`Audit ${response.data.audit_reference} created successfully.`)
      setShowCreateAuditForm(false)
      setActiveTab('audits')
      await loadData()
    } catch (err) {
      const apiError = createApiError(err)
      setCreateAuditError(apiError.detail || 'Failed to create UVDB audit.')
    } finally {
      setIsCreatingAudit(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [loadData])

  const totalMaxScore = sections.reduce((sum, s) => sum + s.max_score, 0)

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-success/10 text-success'
      case 'in_progress':
        return 'bg-info/10 text-info'
      case 'scheduled':
        return 'bg-warning/10 text-warning'
      case 'expired':
        return 'bg-destructive/10 text-destructive'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const getSectionIcon = (number: string) => {
    const icons: Record<string, React.ElementType> = {
      '1': Shield,
      '2': ClipboardList,
      '3': HardHat,
      '4': HardHat,
      '5': HardHat,
      '6': Users,
      '7': Users,
      '8': Leaf,
      '9': Leaf,
      '10': Leaf,
      '11': Truck,
      '12': Building2,
      '13': Wrench,
      '14': Wrench,
      '15': BarChart3,
    }
    return icons[number] || FileText
  }

  const getSectionColor = (number: string) => {
    const colors: Record<string, string> = {
      '1': 'bg-blue-500',
      '2': 'bg-blue-500',
      '3': 'bg-orange-500',
      '4': 'bg-orange-500',
      '5': 'bg-orange-500',
      '6': 'bg-orange-500',
      '7': 'bg-orange-500',
      '8': 'bg-emerald-500',
      '9': 'bg-emerald-500',
      '10': 'bg-emerald-500',
      '11': 'bg-emerald-500',
      '12': 'bg-purple-500',
      '13': 'bg-purple-500',
      '14': 'bg-yellow-500',
      '15': 'bg-gray-500',
    }
    return colors[number] || 'bg-gray-500'
  }

  if (loadState === 'setup_required' && setupRequired) {
    return (
      <div className="min-h-screen bg-background text-foreground p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center gap-3">
              <Award className="w-8 h-8 text-warning" />
              {t('uvdb.title')}
            </h1>
            <p className="text-muted-foreground">{t('uvdb.subtitle')}</p>
          </div>
        </div>
        <SetupRequiredPanel
          response={setupRequired}
          onRetry={() => {
            loadData()
          }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center gap-3">
            <Award className="w-8 h-8 text-warning" />
            {t('uvdb.title')}
          </h1>
          <p className="text-muted-foreground">{t('uvdb.subtitle')}</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button className="flex items-center gap-2 px-4 py-2 bg-secondary border border-border hover:bg-surface rounded-lg transition-colors">
            <Download className="w-4 h-4" />
            {t('uvdb.export_protocol')}
          </button>
          <button
            onClick={handleOpenCreateAuditForm}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('uvdb.new_audit')}
          </button>
        </div>
      </div>

      {createAuditSuccess ? (
        <div className="mb-6 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
          {createAuditSuccess}
        </div>
      ) : null}

      {showCreateAuditForm ? (
        <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between gap-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Create UVDB Audit</h2>
              <p className="text-sm text-muted-foreground">
                Create a new Achilles Verify B2 audit and refresh the audit history automatically.
              </p>
            </div>
            <button
              onClick={() => setShowCreateAuditForm(false)}
              className="rounded-lg p-2 text-muted-foreground hover:bg-surface hover:text-foreground"
              aria-label="Close create UVDB audit form"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCreateAudit}>
            <label className="space-y-2 text-sm text-foreground">
              <span className="font-medium">Company Name</span>
              <input
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
                value={createAuditForm.company_name}
                onChange={(e) => setCreateAuditForm((prev) => ({ ...prev, company_name: e.target.value }))}
              />
            </label>
            <label className="space-y-2 text-sm text-foreground">
              <span className="font-medium">Audit Type</span>
              <input
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
                value={createAuditForm.audit_type}
                onChange={(e) => setCreateAuditForm((prev) => ({ ...prev, audit_type: e.target.value }))}
              />
            </label>
            <label className="space-y-2 text-sm text-foreground">
              <span className="font-medium">Audit Date</span>
              <input
                type="date"
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
                value={createAuditForm.audit_date}
                onChange={(e) => setCreateAuditForm((prev) => ({ ...prev, audit_date: e.target.value }))}
              />
            </label>
            <label className="space-y-2 text-sm text-foreground">
              <span className="font-medium">Lead Auditor</span>
              <input
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
                value={createAuditForm.lead_auditor}
                onChange={(e) => setCreateAuditForm((prev) => ({ ...prev, lead_auditor: e.target.value }))}
              />
            </label>
            <div className="md:col-span-2 flex flex-col gap-3">
              {createAuditError ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {createAuditError}
                </div>
              ) : null}
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setShowCreateAuditForm(false)}
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingAudit}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
                >
                  {isCreatingAudit ? 'Creating audit...' : 'Create Audit'}
                </button>
              </div>
            </div>
          </form>
        </div>
      ) : null}

      {/* Protocol Info Banner */}
      <div className="bg-gradient-to-r from-primary to-primary-hover rounded-xl p-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary-foreground mb-1">
              {dashboard?.protocol_name || t('uvdb.protocol_ref')}
            </h2>
            <p className="text-primary-foreground/80">
              {dashboard ? `${t('uvdb.protocol_version')} ${dashboard.protocol_version}` : t('uvdb.protocol_version')}
            </p>
          </div>
          <div className="mt-4 md:mt-0 flex items-center gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-foreground">{sections.length}</div>
              <div className="text-primary-foreground/80 text-sm">{t('uvdb.sections')}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-foreground">{totalMaxScore}</div>
              <div className="text-primary-foreground/80 text-sm">{t('uvdb.max_score')}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-foreground">{dashboard?.active_audits ?? 0}</div>
              <div className="text-primary-foreground/80 text-sm">Active audits</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border pb-2 overflow-x-auto">
        {[
          { id: 'dashboard', labelKey: 'uvdb.tab.dashboard', icon: BarChart3 },
          { id: 'protocol', labelKey: 'uvdb.tab.protocol', icon: ClipboardList },
          { id: 'audits', labelKey: 'uvdb.tab.audit_history', icon: Calendar },
          { id: 'mapping', labelKey: 'uvdb.tab.iso_mapping', icon: Link2 },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-surface hover:text-foreground'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t(tab.labelKey)}
            </button>
          )
        })}
      </div>

      {/* Loading State */}
      {loadState === 'loading' && (
        <div className="flex flex-col items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-warning animate-spin mb-4" />
          <p className="text-muted-foreground">{t('uvdb.loading')}</p>
        </div>
      )}

      {/* Error State */}
      {loadState === 'error' && (
        <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
          <XCircle className="w-12 h-12 text-destructive mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">{t('uvdb.failed_to_load')}</h3>
          <p className="text-muted-foreground mb-4">
            {errorClass === ErrorClass.NETWORK_ERROR && t('uvdb.error_network')}
            {errorClass === ErrorClass.SERVER_ERROR && t('uvdb.error_server')}
            {errorClass === ErrorClass.AUTH_ERROR && t('uvdb.error_auth')}
            {errorClass === ErrorClass.NOT_FOUND && t('uvdb.error_not_found')}
            {(errorClass === ErrorClass.UNKNOWN || !errorClass) && t('uvdb.error_unknown')}
          </p>
          <button
            onClick={() => {
              setRetryCount(0)
              loadData()
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            {t('uvdb.try_again')}
          </button>
        </div>
      )}

      {/* Empty State */}
      {loadState === 'success' && sections.length === 0 && audits.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
          <Award className="w-12 h-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">{t('uvdb.no_data')}</h3>
          <p className="text-muted-foreground mb-4">{t('uvdb.no_data_description')}</p>
          <button
            onClick={handleOpenCreateAuditForm}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('uvdb.new_audit')}
          </button>
        </div>
      )}

      {loadState === 'success' && (sections.length > 0 || audits.length > 0) && (
        <>
          {/* Dashboard Tab */}
          {activeTab === 'dashboard' && (
            <div className="space-y-6">
              {/* ISO Alignment Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  {
                    standard: 'ISO 9001:2015',
                    titleKey: 'uvdb.quality',
                    icon: Shield,
                    color: 'bg-blue-500',
                    sections: '1.1, 2.1-2.5, 12-13',
                  },
                  {
                    standard: 'ISO 14001:2015',
                    titleKey: 'uvdb.environmental',
                    icon: Leaf,
                    color: 'bg-emerald-500',
                    sections: '1.3, 8-11, 15',
                  },
                  {
                    standard: 'ISO 45001:2018',
                    titleKey: 'uvdb.ohs',
                    icon: HardHat,
                    color: 'bg-orange-500',
                    sections: '1.2, 3-7, 14, 15',
                  },
                  {
                    standard: 'ISO 27001:2022',
                    titleKey: 'uvdb.info_security',
                    icon: Lock,
                    color: 'bg-purple-500',
                    sections: '2.3',
                  },
                ].map((iso) => {
                  const Icon = iso.icon
                  return (
                    <div
                      key={iso.standard}
                      className="bg-slate-800 rounded-xl p-5 border border-slate-700"
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <div className={`p-2 ${iso.color} rounded-lg`}>
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <div className="font-bold text-white">{iso.standard}</div>
                          <div className="text-xs text-gray-400">{t(iso.titleKey)}</div>
                        </div>
                      </div>
                      <div className="text-sm text-gray-300">
                        <span className="text-gray-400">UVDB Sections:</span> {iso.sections}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Recent Audits */}
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-white">{t('uvdb.audit_status')}</h3>
                    <p className="text-sm text-gray-400">Plantexpand Limited (00019685)</p>
                  </div>
                  <Award className="w-8 h-8 text-yellow-400" />
                </div>
                <div className="p-4 space-y-4">
                  {audits.map((audit) => (
                    <div
                      key={audit.id}
                      className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-yellow-500/20 rounded-lg">
                          <FileText className="w-5 h-5 text-yellow-400" />
                        </div>
                        <div>
                          <div className="font-medium text-white">{audit.audit_reference}</div>
                          <div className="text-sm text-gray-400">
                            {audit.audit_type} Audit • {audit.audit_date || 'TBD'} •{' '}
                            {audit.lead_auditor}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {audit.percentage_score != null && (
                          <div className="text-right">
                            <div className="text-2xl font-bold text-emerald-400">
                              {audit.percentage_score}%
                            </div>
                            <div className="text-xs text-gray-400">{t('uvdb.audit_score')}</div>
                          </div>
                        )}
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(audit.status)}`}
                        >
                          {audit.status}
                        </span>
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* KPI Summary */}
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">{t('uvdb.audit_status')}</h3>
                </div>
                <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: 'Total audits', value: dashboard?.total_audits ?? audits.length },
                    { label: 'Active', value: dashboard?.active_audits ?? 0 },
                    { label: 'Completed', value: dashboard?.completed_audits ?? 0 },
                    { label: 'Average score', value: `${dashboard?.average_score ?? 0}%` },
                  ].map((kpi) => (
                    <div key={kpi.label} className="bg-slate-700/50 rounded-lg p-4 text-center">
                      <div className="text-2xl font-bold text-white">{kpi.value}</div>
                      <div className="text-xs text-gray-400">{kpi.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Protocol Sections Tab */}
          {activeTab === 'protocol' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sections.map((section) => {
                const Icon = getSectionIcon(section.number)
                const bgColor = getSectionColor(section.number)
                return (
                  <div
                    key={section.number}
                    className="bg-slate-800 rounded-xl p-5 border border-slate-700 hover:border-slate-500 transition-colors cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className={`p-3 ${bgColor} rounded-xl`}>
                        <Icon className="w-6 h-6 text-white" />
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold text-white">{section.max_score}</div>
                        <div className="text-xs text-gray-400">{t('uvdb.max_score')}</div>
                      </div>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      Section {section.number}
                    </div>
                    <div className="text-sm text-gray-300 mb-4">{section.title}</div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">{section.question_count} Questions</span>
                      <div className="flex gap-1">
                        {Object.keys(section.iso_mapping).map((iso) => (
                          <span
                            key={iso}
                            className={`px-2 py-0.5 rounded text-xs ${
                              iso === '9001'
                                ? 'bg-blue-500/20 text-blue-400'
                                : iso === '14001'
                                  ? 'bg-emerald-500/20 text-emerald-400'
                                  : iso === '45001'
                                    ? 'bg-orange-500/20 text-orange-400'
                                    : 'bg-purple-500/20 text-purple-400'
                            }`}
                          >
                            {iso}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Audit History Tab */}
          {activeTab === 'audits' && (
            <div className="bg-slate-800 rounded-xl border border-slate-700">
              <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder={t('uvdb.search_placeholder')}
                      className="pl-10 pr-4 py-2 bg-slate-600 border border-slate-500 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
                    />
                  </div>
                  <button className="flex items-center gap-2 px-3 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors">
                    <Filter className="w-4 h-4" />
                    {t('uvdb.filter')}
                  </button>
                </div>
                <button className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors">
                  <Plus className="w-4 h-4" />
                  {t('uvdb.new_audit')}
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-700/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.reference')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.company')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.type')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.date')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.lead_auditor')}
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.score')}
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.status')}
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.actions')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {audits.map((audit) => (
                      <tr key={audit.id} className="hover:bg-slate-700/50">
                        <td className="px-4 py-3 font-medium text-white">
                          {audit.audit_reference}
                        </td>
                        <td className="px-4 py-3 text-gray-300">{audit.company_name}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs font-medium">
                            {audit.audit_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{audit.audit_date || 'TBD'}</td>
                        <td className="px-4 py-3 text-gray-300">{audit.lead_auditor}</td>
                        <td className="px-4 py-3 text-center">
                          {audit.percentage_score != null ? (
                            <span className="text-emerald-400 font-bold">
                              {audit.percentage_score}%
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(audit.status)}`}
                          >
                            {audit.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            aria-label="Open external link"
                            className="p-2 hover:bg-slate-600 rounded-lg transition-colors"
                          >
                            <ExternalLink className="w-4 h-4 text-gray-400" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ISO Cross-Mapping Tab */}
          {activeTab === 'mapping' && (
            <div className="bg-slate-800 rounded-xl border border-slate-700">
              <div className="p-4 bg-slate-700 border-b border-slate-600">
                <h3 className="font-bold text-white">{t('uvdb.iso_cross_mapping')}</h3>
                <p className="text-sm text-gray-400">{t('uvdb.iso_mapping_subtitle')}</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-700/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.uvdb_section')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                        {t('uvdb.topic')}
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        ISO 9001
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        ISO 14001
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        ISO 45001
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                        ISO 27001
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {isoMappings.map((row) => (
                      <tr
                        key={`${row.uvdb_section}-${row.uvdb_question}`}
                        className="hover:bg-slate-700/50"
                      >
                        <td className="px-4 py-3 font-medium text-white">{row.uvdb_section}</td>
                        <td className="px-4 py-3 text-gray-300">{row.uvdb_text}</td>
                        <td className="px-4 py-3 text-center">
                          {row.iso_9001.length > 0 && (
                            <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                              {row.iso_9001.join(', ')}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.iso_14001.length > 0 && (
                            <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                              {row.iso_14001.join(', ')}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.iso_45001.length > 0 && (
                            <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-xs">
                              {row.iso_45001.join(', ')}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.iso_27001.length > 0 && (
                            <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                              {row.iso_27001.join(', ')}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {isoMappings.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-6 text-center text-gray-400">
                          No ISO cross-mapping data is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
