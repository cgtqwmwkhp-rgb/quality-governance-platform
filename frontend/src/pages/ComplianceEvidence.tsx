import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Award,
  Leaf,
  HardHat,
  Search,
  ChevronDown,
  ChevronRight,
  FileText,
  ClipboardCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Link2,
  Sparkles,
  Target,
  ArrowUpRight,
  BookOpen,
  Shield,
  Zap,
  Download,
  Tag,
  Trash2,
  Brain,
  CheckSquare,
} from 'lucide-react'
import {
  complianceApi,
  crossStandardMappingsApi,
  externalAuditRecordsApi,
  getApiErrorMessage,
  type ComplianceClauseRecord,
  type ComplianceCoverageResponse,
  type ComplianceReportResponse,
  type ComplianceStandardRecord,
  type CrossStandardMappingRecord,
  type EvidenceLinkRecord,
  type ExternalAuditRecordSummary,
  type MultiStageAnalysisResult,
  type StatementOfApplicability,
} from '../api/client'
import {
  Button,
  Card,
  CardContent,
  Input,
  Badge,
  EmptyState,
  TableSkeleton,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Textarea,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui'
import { cn } from '../helpers/utils'

/**
 * Maps entity_type values (as stored in ComplianceEvidenceLink) to valid SPA routes.
 *
 * For `audit_finding` we deep-link to the Audits Findings tab pre-filtered by
 * the specific finding ID (?view=findings&findingId=N) so the user lands on the
 * exact finding rather than the general audit board.
 *
 * Using a naive `/${entity_type}s` template produces broken routes such as:
 *   audit_finding → /audit_findings (no route)
 *   policy        → /policys        (no route)
 *   training      → /trainings      (no route — correct is /workforce/training)
 */
const ENTITY_TYPE_ROUTE: Record<string, string> = {
  audit: '/audits',
  incident: '/incidents',
  complaint: '/complaints',
  near_miss: '/near-misses',
  action: '/actions',
  risk: '/risks',
  policy: '/policies',
  document: '/documents',
  training: '/workforce/training',
}

const getEntityRoute = (entityType: string, entityId?: string): string => {
  if (entityType === 'audit_finding' && entityId) {
    return `/audits?view=findings&findingId=${encodeURIComponent(entityId)}`
  }
  if (entityType === 'audit_finding') return '/audits?view=findings'
  return ENTITY_TYPE_ROUTE[entityType] ?? `/${entityType}s`
}

const evidenceTypeConfig: Record<
  string,
  { icon: React.ElementType; label: string; color: string }
> = {
  policy: { icon: BookOpen, label: 'Policy', color: 'bg-purple-500' },
  document: { icon: FileText, label: 'Document', color: 'bg-blue-500' },
  audit: { icon: ClipboardCheck, label: 'Audit', color: 'bg-emerald-500' },
  incident: { icon: AlertTriangle, label: 'Incident', color: 'bg-red-500' },
  action: { icon: Zap, label: 'Action', color: 'bg-yellow-500' },
  risk: { icon: Shield, label: 'Risk', color: 'bg-orange-500' },
  training: { icon: Award, label: 'Training', color: 'bg-cyan-500' },
  audit_finding: { icon: ClipboardCheck, label: 'Audit Finding', color: 'bg-teal-500' },
}

const standardIcons: Record<string, React.ElementType> = {
  iso9001: Award,
  iso14001: Leaf,
  iso45001: HardHat,
  iso27001: Shield,
  planetmark: Leaf,
  uvdb: Award,
}

const standardColors: Record<string, string> = {
  iso9001: 'blue',
  iso14001: 'green',
  iso45001: 'orange',
  iso27001: 'purple',
  planetmark: 'teal',
  uvdb: 'yellow',
}

export default function ComplianceEvidence() {
  const [searchParams] = useSearchParams()
  const clauseFromUrl = (searchParams.get('clause') || '').trim()
  const standardFromUrl = (searchParams.get('standard') || '').trim()

  const [selectedStandard, setSelectedStandard] = useState<string | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedClauses, setExpandedClauses] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<'clauses' | 'evidence' | 'gaps' | 'imported'>('clauses')
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null)
  const [showAutoTagger, setShowAutoTagger] = useState(false)
  const [autoTagText, setAutoTagText] = useState('')
  const [autoTagResults, setAutoTagResults] = useState<ComplianceClauseRecord[]>([])
  const [useAiTagging, setUseAiTagging] = useState(true)
  const [autoTagging, setAutoTagging] = useState(false)
  // Deep analysis (5-stage Genspark pipeline)
  const [deepAnalysisResult, setDeepAnalysisResult] = useState<MultiStageAnalysisResult | null>(null)
  const [deepAnalyzing, setDeepAnalyzing] = useState(false)
  const [showDeepAnalysis, setShowDeepAnalysis] = useState(false)
  // Statement of Applicability
  const [soaData, setSoaData] = useState<StatementOfApplicability | null>(null)
  const [loadingSoA, setLoadingSoA] = useState(false)
  const [showSoA, setShowSoA] = useState(false)
  const [standards, setStandards] = useState<ComplianceStandardRecord[]>([])
  const [clauses, setClauses] = useState<ComplianceClauseRecord[]>([])
  const [coverage, setCoverage] = useState<ComplianceCoverageResponse | null>(null)
  const [report, setReport] = useState<ComplianceReportResponse | null>(null)
  const [evidenceLinks, setEvidenceLinks] = useState<EvidenceLinkRecord[]>([])
  const [mappings, setMappings] = useState<CrossStandardMappingRecord[]>([])
  const [importedRecords, setImportedRecords] = useState<ExternalAuditRecordSummary[]>([])
  const [importedTotal, setImportedTotal] = useState(0)
  const [loadingImported, setLoadingImported] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMappings, setLoadingMappings] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [partialLoadWarning, setPartialLoadWarning] = useState<string | null>(null)
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('')
  const [deletingLinkId, setDeletingLinkId] = useState<number | null>(null)
  // Ref to avoid selectedClauseId as a loadData dependency (prevents double-fetch
  // caused by the auto-select logic inside loadData itself setting selectedClauseId).
  const selectedClauseIdRef = useRef<string | null>(null)

  // Debounce search query to avoid firing an API call on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearchQuery(searchQuery), 350)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const canonicalDataWarning = useMemo(
    () => standards.find((standard) => standard.canonical_data_degraded)?.canonical_data_message ?? null,
    [standards],
  )

  useEffect(() => {
    if (!standardFromUrl) return
    setSelectedStandard(standardFromUrl)
  }, [standardFromUrl])

  // Keep ref in sync with state so loadData can read current value without
  // needing selectedClauseId as a dependency (which would cause infinite loops).
  useEffect(() => {
    selectedClauseIdRef.current = selectedClauseId
  }, [selectedClauseId])

  useEffect(() => {
    if (!clauseFromUrl || clauses.length === 0) return
    const needle = clauseFromUrl.toLowerCase()
    const match = clauses.find(
      (c) =>
        c.clause_number.toLowerCase() === needle ||
        String(c.id).toLowerCase() === needle ||
        c.clause_number.toLowerCase().replace(/\s+/g, '') === needle.replace(/\s+/g, ''),
    )
    if (match) {
      setSelectedClauseId(match.id)
      setViewMode('clauses')
    }
  }, [clauseFromUrl, clauses])

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      setLoading(true)
      setError(null)
      setPartialLoadWarning(null)
      try {
        const standardFilter = selectedStandard === 'all' ? undefined : selectedStandard
        const labels = ['standards', 'clauses', 'coverage', 'report', 'evidence links'] as const
        const settled = await Promise.allSettled([
          complianceApi.listStandards(),
          complianceApi.listClauses(standardFilter, debouncedSearchQuery || undefined),
          complianceApi.getCoverage(standardFilter),
          complianceApi.getReport(standardFilter),
          complianceApi.listEvidenceLinks(),
        ])

        if (cancelled) return

        const failed = labels.filter((_, i) => settled[i].status === 'rejected')
        if (failed.length === labels.length) {
          const first = settled.find((s) => s.status === 'rejected') as PromiseRejectedResult
          setError(getApiErrorMessage(first.reason))
          setStandards([])
          setClauses([])
          setCoverage(null)
          setReport(null)
          setEvidenceLinks([])
        } else {
          if (failed.length > 0) {
            setPartialLoadWarning(
              `Some data could not be loaded: ${failed.join(', ')}. Showing what is available.`,
            )
          }
          const [sr, cr, cov, rep, ev] = settled
          setStandards(sr.status === 'fulfilled' ? sr.value.data : [])
          setClauses(cr.status === 'fulfilled' ? cr.value.data : [])
          setCoverage(cov.status === 'fulfilled' ? cov.value.data : null)
          setReport(rep.status === 'fulfilled' ? rep.value.data : null)
          setEvidenceLinks(ev.status === 'fulfilled' ? ev.value.data : [])

          const reportData = rep.status === 'fulfilled' ? rep.value.data : null
          const clausesData = cr.status === 'fulfilled' ? cr.value.data : []
          // Use ref (not state) to read selectedClauseId inside this effect to
          // avoid adding it to the deps array and causing infinite re-fetches.
          const currentClauseId = selectedClauseIdRef.current
          if (
            reportData &&
            currentClauseId &&
            !clausesData.some((clause) => clause.id === currentClauseId) &&
            reportData.clauses.length > 0
          ) {
            setSelectedClauseId(reportData.clauses[0].clause_id)
          }
          if (reportData && !currentClauseId && reportData.clauses.length > 0) {
            setSelectedClauseId(reportData.clauses[0].clause_id)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadData()

    return () => {
      cancelled = true
    }
  // selectedClauseId intentionally excluded: read via selectedClauseIdRef to prevent
  // the auto-select logic from causing a second fetch on every clause change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearchQuery, selectedStandard])

  useEffect(() => {
    if (viewMode !== 'imported') return
    let cancelled = false
    const loadImported = async () => {
      setLoadingImported(true)
      setError(null)
      try {
        const res = await externalAuditRecordsApi.list({ scheme: 'iso' })
        if (!cancelled) {
          setImportedRecords(res.data.records)
          setImportedTotal(res.data.total)
        }
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err))
      } finally {
        if (!cancelled) setLoadingImported(false)
      }
    }
    void loadImported()
    return () => { cancelled = true }
  }, [viewMode])

  const selectedClause = useMemo(
    () => clauses.find((clause) => clause.id === selectedClauseId) ?? null,
    [clauses, selectedClauseId],
  )

  useEffect(() => {
    let cancelled = false

    const loadMappings = async () => {
      if (!selectedClause) {
        setMappings([])
        return
      }

      setLoadingMappings(true)
      try {
        const response = await crossStandardMappingsApi.list({
          clause: selectedClause.clause_number,
          limit: 500,
        })
        if (!cancelled) {
          setMappings(response.data)
        }
      } catch {
        if (!cancelled) {
          setMappings([])
        }
      } finally {
        if (!cancelled) {
          setLoadingMappings(false)
        }
      }
    }

    void loadMappings()

    return () => {
      cancelled = true
    }
  }, [selectedClause])

  const complianceStats = useMemo(() => {
    return standards.reduce<Record<string, { total: number; covered: number; partial: number; gaps: number }>>(
      (acc, standard) => {
        const byStandard = coverage?.by_standard?.[standard.id]
        const coveredCount = byStandard?.covered ?? standard.covered_clauses
        const fullCoverage = Math.max(standard.covered_clauses - 1, 0)
        acc[standard.id] = {
          total: standard.clause_count,
          covered: Math.max(coveredCount - (coverage?.partial_coverage ?? 0), 0),
          partial: selectedStandard === standard.id ? coverage?.partial_coverage ?? 0 : 0,
          gaps: standard.clause_count - coveredCount,
        }
        if (selectedStandard === 'all') {
          acc[standard.id].covered = fullCoverage
          acc[standard.id].partial = 0
        }
        return acc
      },
      {},
    )
  }, [coverage, selectedStandard, standards])

  const clauseDetailsById = useMemo(() => {
    return new Map(report?.clauses.map((clause) => [clause.clause_id, clause]) ?? [])
  }, [report])

  const getEvidenceForClause = (clauseId: string): EvidenceLinkRecord[] =>
    evidenceLinks.filter((evidence) => evidence.clause_id === clauseId)

  const selectedClauseEvidence = useMemo(
    () =>
      selectedClause
        ? evidenceLinks.filter((evidence) => evidence.clause_id === selectedClause.id)
        : [],
    [evidenceLinks, selectedClause],
  )

  const selectedClauseProvenance = useMemo(() => {
    const counts = selectedClauseEvidence.reduce<Record<string, number>>((acc, evidence) => {
      acc[evidence.entity_type] = (acc[evidence.entity_type] || 0) + 1
      return acc
    }, {})
    return {
      auditLinks: (counts.audit || 0) + (counts.audit_finding || 0),
      actionLinks: counts.action || 0,
      riskLinks: counts.risk || 0,
      totalLinks: selectedClauseEvidence.length,
      mappedFrameworks: mappings.length,
    }
  }, [mappings.length, selectedClauseEvidence])

  const filteredClauses = clauses

  const toggleClause = (clauseId: string) => {
    const newExpanded = new Set(expandedClauses)
    if (newExpanded.has(clauseId)) {
      newExpanded.delete(clauseId)
    } else {
      newExpanded.add(clauseId)
    }
    setExpandedClauses(newExpanded)
  }

  const handleAutoTag = async () => {
    if (!autoTagText.trim()) return
    setAutoTagging(true)
    setDeepAnalysisResult(null)
    try {
      const response = await complianceApi.autoTag(autoTagText, useAiTagging)
      const taggedClauseIds = response.data.map((result) => result.clause_id)
      setAutoTagResults(clauses.filter((clause) => taggedClauseIds.includes(clause.id)))
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setAutoTagging(false)
    }
  }

  const handleDeepAnalysis = async () => {
    if (!autoTagText.trim()) return
    setDeepAnalyzing(true)
    try {
      const response = await complianceApi.analyzeEvidence(autoTagText)
      setDeepAnalysisResult(response.data)
      setShowDeepAnalysis(true)
      // Also populate auto-tag results from primary_results
      const taggedClauseIds = response.data.primary_results.map((r) => r.clause_id)
      setAutoTagResults(clauses.filter((clause) => taggedClauseIds.includes(clause.id)))
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setDeepAnalyzing(false)
    }
  }

  const handleGenerateSoA = async () => {
    setLoadingSoA(true)
    try {
      const response = await complianceApi.getSoA()
      setSoaData(response.data)
      setShowSoA(true)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoadingSoA(false)
    }
  }

  const handleDownloadAuditPack = async () => {
    try {
      const [reportRes, soaRes] = await Promise.all([
        complianceApi.getReport(),
        complianceApi.getSoA(),
      ])
      const pack = {
        generated_at: new Date().toISOString(),
        report: reportRes.data,
        statement_of_applicability: soaRes.data,
      }
      const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `iso-audit-pack-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const handleDeleteLink = async (linkId: number) => {
    setDeletingLinkId(linkId)
    try {
      await complianceApi.deleteEvidenceLink(linkId)
      setEvidenceLinks((prev) => prev.filter((e) => e.id !== linkId))
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setDeletingLinkId(null)
    }
  }

  const getCoverageStatus = (clauseId: string): 'full' | 'partial' | 'none' => {
    const clauseDetail = clauseDetailsById.get(clauseId)
    if (clauseDetail?.status === 'full') return 'full'
    if (clauseDetail?.status === 'partial') return 'partial'
    return 'none'
  }

  const renderClauseTree = (parentId: string | undefined, level: number, standard: string) => {
    const children = filteredClauses.filter(
      (c) =>
        (c.parent_clause ?? undefined) === parentId &&
        (selectedStandard === 'all' || c.standard === selectedStandard),
    )

    if (children.length === 0) return null

    return (
      <div className={cn(level > 0 && 'ml-6 border-l border-border pl-4')}>
        {children.map((clause) => {
          const coverageStatus = getCoverageStatus(clause.id)
          const evidence = getEvidenceForClause(clause.id)
          const isExpanded = expandedClauses.has(clause.id)
          const hasChildren = filteredClauses.some((c) => c.parent_clause === clause.id)
          const StandardIcon = standardIcons[clause.standard] || Award
          const color = standardColors[clause.standard] || 'blue'

          return (
            <div key={clause.id} className="mb-2">
              <div
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all duration-200',
                  selectedClauseId === clause.id
                    ? 'bg-surface ring-2 ring-primary'
                    : 'bg-surface/50 hover:bg-surface',
                )}
                onClick={() => setSelectedClauseId(clause.id)}
                role="button"
                tabIndex={0}
                aria-pressed={selectedClauseId === clause.id}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedClauseId(clause.id)
                  }
                }}
              >
                {hasChildren ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleClause(clause.id)
                    }}
                    className="text-muted-foreground hover:text-foreground"
                    aria-label={isExpanded ? 'Collapse clause' : 'Expand clause'}
                    aria-expanded={isExpanded}
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </button>
                ) : (
                  <div className="w-4" aria-hidden="true" />
                )}

                <div
                  aria-hidden="true"
                  className={cn(
                    'w-2 h-2 rounded-full flex-shrink-0',
                    coverageStatus === 'full'
                      ? 'bg-success'
                      : coverageStatus === 'partial'
                        ? 'bg-warning'
                        : 'bg-destructive',
                  )}
                />

                <StandardIcon className={`w-4 h-4 text-${color}-400 flex-shrink-0`} aria-hidden="true" />

                <span className="text-sm font-medium text-muted-foreground flex-shrink-0">
                  {clause.clause_number}
                </span>
                <span className="text-sm text-foreground flex-grow min-w-0 truncate">{clause.title}</span>

                {evidence.length > 0 && (
                  <Badge variant="secondary" className="flex items-center gap-1 flex-shrink-0">
                    <Link2 className="w-3 h-3" aria-hidden="true" />
                    {evidence.length}
                  </Badge>
                )}
              </div>

              {isExpanded && renderClauseTree(clause.id, level + 1, standard)}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Target className="w-6 h-6 text-primary" aria-hidden="true" />
            ISO Compliance Evidence Center
          </h1>
          <p className="text-muted-foreground mt-1">
            Live repository for compliance evidence, clause coverage, and cross-standard mappings
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Button onClick={() => setShowAutoTagger(true)}>
            <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
            AI Auto-Tagger
          </Button>
          <Button
            variant="outline"
            onClick={handleGenerateSoA}
            disabled={loadingSoA}
            title="Generate ISO 27001:2022 Statement of Applicability"
          >
            {loadingSoA ? (
              <span className="w-4 h-4 mr-2 border-2 border-primary/30 border-t-primary rounded-full animate-spin" aria-hidden="true" />
            ) : (
              <CheckSquare className="w-4 h-4 mr-2" aria-hidden="true" />
            )}
            Generate SoA
          </Button>
          <Button variant="outline" onClick={handleDownloadAuditPack} title="Download full ISO audit evidence pack">
            <Download className="w-4 h-4 mr-2" aria-hidden="true" />
            Audit Pack
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {partialLoadWarning && !error && (
        <div role="status" className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          {partialLoadWarning}
        </div>
      )}

      {canonicalDataWarning && (
        <div role="status" className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="font-medium">Compliance data is running in degraded mode</p>
            <p>{canonicalDataWarning}</p>
          </div>
        </div>
      )}

      {/* Compliance Score Cards */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}><CardContent className="p-6"><TableSkeleton rows={3} columns={1} /></CardContent></Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {standards.map((standard) => {
            const stats = complianceStats[standard.id] ?? {
              total: standard.clause_count,
              covered: 0,
              partial: 0,
              gaps: standard.clause_count,
            }
            const percentage = Math.round(
              stats.total > 0 ? ((stats.covered + stats.partial * 0.5) / stats.total) * 100 : 0,
            )
            const Icon = standardIcons[standard.id]
            const color = standardColors[standard.id]

            return (
              <div
                key={standard.id}
                onClick={() => setSelectedStandard(standard.id)}
                role="button"
                tabIndex={0}
                aria-pressed={selectedStandard === standard.id}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedStandard(standard.id)
                  }
                }}
                className={cn(
                  'p-4 rounded-xl bg-card border-2 cursor-pointer transition-all duration-200',
                  selectedStandard === standard.id
                    ? 'border-primary shadow-lg shadow-primary/20'
                    : 'border-border hover:border-border-strong',
                )}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg bg-${color}-500/20`}>
                      <Icon className={`w-5 h-5 text-${color}-400`} aria-hidden="true" />
                    </div>
                    <div>
                      <h3 className="font-bold text-foreground">{standard.code}</h3>
                      <p className="text-xs text-muted-foreground">
                        {standard.name}
                        {standard.canonical_data_degraded
                          ? ' • canonical enrichment degraded'
                          : standard.has_canonical_standard
                            ? ' • live canonical'
                            : ' • fallback'}
                      </p>
                    </div>
                  </div>
                  <div className={`text-2xl font-bold text-${color}-400`} aria-label={`${percentage}% compliance`}>
                    {percentage}%
                  </div>
                </div>

                <div className="w-full bg-surface rounded-full h-2 mb-3" role="progressbar" aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100}>
                  <div
                    className={`h-2 rounded-full bg-gradient-to-r from-${color}-600 to-${color}-400`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>

                <div className="flex justify-between text-xs">
                  <span className="text-success">{stats.covered} Full</span>
                  <span className="text-warning">{stats.partial} Partial</span>
                  <span className="text-destructive">{stats.gaps} Gaps</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* View Mode Tabs & Search Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex bg-secondary rounded-lg p-1" role="tablist" aria-label="Compliance views">
          {[
            { id: 'clauses', label: 'Clause View', icon: BookOpen },
            { id: 'evidence', label: 'Evidence List', icon: FileText },
            { id: 'gaps', label: 'Gap Analysis', icon: AlertTriangle },
            { id: 'imported', label: 'Imported Audits', icon: ClipboardCheck },
          ].map((tab) => (
            <Button
              key={tab.id}
              variant={viewMode === tab.id ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode(tab.id as typeof viewMode)}
              role="tab"
              aria-selected={viewMode === tab.id}
              className="flex items-center gap-2"
            >
              <tab.icon className="w-4 h-4" aria-hidden="true" />
              {tab.label}
            </Button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" aria-hidden="true" />
            <Input
              type="text"
              placeholder="Search clauses or keywords..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 w-72"
              aria-label="Search clauses"
            />
          </div>

          <Select value={selectedStandard} onValueChange={(value) => setSelectedStandard(value)}>
            <SelectTrigger className="w-40" aria-label="Filter by standard">
              <SelectValue placeholder="All Standards" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Standards</SelectItem>
              {standards.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.code}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Panel */}
        <Card className="lg:col-span-2 max-h-[70vh] overflow-y-auto">
          <CardContent className="p-6">
            {viewMode === 'clauses' && (
              <>
                <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-primary" aria-hidden="true" />
                  Clause Structure
                </h2>
                {loading ? (
                  <TableSkeleton rows={8} columns={1} />
                ) : clauses.length === 0 ? (
                  <EmptyState
                    icon={<BookOpen className="w-8 h-8 text-muted-foreground" />}
                    title="No clauses found"
                    description="Adjust the standard filter or search query to see clauses."
                  />
                ) : selectedStandard === 'all'
                  ? standards.map((standard) => (
                      <div key={standard.id} className="mb-6">
                        <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                          {React.createElement(standardIcons[standard.id], {
                            className: `w-4 h-4 text-${standardColors[standard.id]}-400`,
                            'aria-hidden': 'true',
                          })}
                          {standard.code}
                        </h3>
                        {renderClauseTree(undefined, 0, standard.id)}
                      </div>
                    ))
                  : renderClauseTree(undefined, 0, selectedStandard)}
              </>
            )}

            {viewMode === 'evidence' && (
              <>
                <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-primary" aria-hidden="true" />
                  All Evidence
                  <Badge variant="secondary">{evidenceLinks.length} items</Badge>
                </h2>
                {loading ? (
                  <TableSkeleton rows={5} columns={1} />
                ) : evidenceLinks.length === 0 ? (
                  <EmptyState
                    icon={<FileText className="w-8 h-8 text-muted-foreground" />}
                    title="No evidence items"
                    description="Evidence items will appear here when linked to ISO clauses."
                  />
                ) : (
                  <div className="space-y-3">
                    {evidenceLinks.map((evidence) => {
                      const config =
                        evidenceTypeConfig[evidence.entity_type] ?? evidenceTypeConfig.document
                      const Icon = config.icon

                      return (
                        <div
                          key={evidence.id}
                          className="p-4 bg-surface hover:bg-muted rounded-lg transition-colors border border-border"
                        >
                          <div className="flex items-start gap-3">
                            <div className={`p-2 rounded-lg ${config.color} flex-shrink-0`} aria-hidden="true">
                              <Icon className="w-4 h-4 text-white" />
                            </div>
                            <div className="flex-grow min-w-0">
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <h4 className="font-medium text-foreground truncate">
                                  {evidence.title ?? `${config.label} ${evidence.entity_id}`}
                                </h4>
                                {evidence.linked_by !== 'manual' && (
                                  <Badge variant="secondary" className="flex items-center gap-1 flex-shrink-0">
                                    <Sparkles className="w-3 h-3" aria-hidden="true" />
                                    {evidence.linked_by} {evidence.confidence ?? ''}%
                                  </Badge>
                                )}
                              </div>
                              <p className="text-sm text-muted-foreground mb-2">
                                {evidence.notes ?? `${config.label} linked to clause ${evidence.clause_id}`}
                              </p>
                              <div className="flex items-center gap-2 flex-wrap">
                                {(() => {
                                  const clause = clauses.find((item) => item.id === evidence.clause_id)
                                  if (!clause) return null
                                  const color = standardColors[clause.standard] ?? 'blue'
                                  return (
                                    <span
                                      className={`text-xs bg-${color}-500/20 text-${color}-400 px-2 py-1 rounded-full`}
                                    >
                                      {clause.clause_number}
                                    </span>
                                  )
                                })()}
                              </div>
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <span className="text-xs text-muted-foreground">
                                {new Date(evidence.created_at).toLocaleDateString()}
                              </span>
                              <Link
                                to={getEntityRoute(evidence.entity_type, evidence.entity_id)}
                                className="p-1 rounded text-primary hover:text-primary/80 hover:bg-primary/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ml-1"
                                aria-label={`View ${config.label}`}
                              >
                                <ArrowUpRight className="w-4 h-4" aria-hidden="true" />
                              </Link>
                              <button
                                onClick={() => void handleDeleteLink(evidence.id)}
                                disabled={deletingLinkId === evidence.id}
                                className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50"
                                aria-label={`Unlink ${config.label}`}
                              >
                                <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                              </button>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </>
            )}

            {viewMode === 'imported' && (
              <>
                <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                  <ClipboardCheck className="w-5 h-5 text-primary" aria-hidden="true" />
                  Imported ISO Audits
                  <Badge variant="secondary">{importedTotal}</Badge>
                </h2>
                {loadingImported ? (
                  <TableSkeleton rows={4} columns={1} />
                ) : importedRecords.length === 0 ? (
                  <EmptyState
                    icon={<ClipboardCheck className="w-8 h-8 text-muted-foreground" />}
                    title="No imported ISO audits"
                    description="Import ISO audit reports via the Audits page to see them here."
                  />
                ) : (
                  <div className="space-y-3">
                    {importedRecords.map((record) => (
                      <div
                        key={record.id}
                        className="p-4 bg-surface rounded-lg border border-border hover:border-primary/40 transition-all"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <h4 className="font-medium text-foreground">
                              {record.scheme_label || record.scheme_version || 'ISO Audit'}
                            </h4>
                            <p className="text-sm text-muted-foreground">
                              {record.issuer_name && `${record.issuer_name} · `}
                              {record.report_date
                                ? new Date(record.report_date).toLocaleDateString()
                                : 'Date not available'}
                            </p>
                          </div>
                          <div className="text-right flex-shrink-0">
                            {record.score_percentage != null && (
                              <span className="text-lg font-bold text-primary">
                                {Math.round(record.score_percentage)}%
                              </span>
                            )}
                            <div className={cn(
                              'text-xs mt-1 px-2 py-0.5 rounded-full inline-block',
                              record.outcome_status === 'pass' || record.outcome_status === 'approved'
                                ? 'bg-success/20 text-success'
                                : record.outcome_status === 'fail'
                                  ? 'bg-destructive/20 text-destructive'
                                  : 'bg-warning/20 text-warning',
                            )}>
                              {record.outcome_status || record.status}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                          <span>{record.findings_count ?? 0} findings</span>
                          {(record.major_findings ?? 0) > 0 && (
                            <span className="text-destructive">{record.major_findings} major</span>
                          )}
                          {(record.minor_findings ?? 0) > 0 && (
                            <span className="text-warning">{record.minor_findings} minor</span>
                          )}
                          {(record.observations ?? 0) > 0 && (
                            <span>{record.observations} observations</span>
                          )}
                          {record.import_job_id && (
                            <Link
                              to={`/audits/0/import-review?jobId=${record.import_job_id}`}
                              className="text-primary hover:underline flex items-center gap-1 ml-auto"
                            >
                              View Import <ArrowUpRight className="w-3 h-3" aria-hidden="true" />
                            </Link>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {viewMode === 'gaps' && (
              <>
                <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-destructive" aria-hidden="true" />
                  Gap Analysis — Clauses Needing Evidence
                </h2>
                {loading ? (
                  <TableSkeleton rows={6} columns={1} />
                ) : (coverage?.gap_clauses ?? []).filter(
                    (c) => selectedStandard === 'all' || c.standard === selectedStandard,
                  ).length === 0 ? (
                  <EmptyState
                    icon={<CheckCircle2 className="w-8 h-8 text-success" />}
                    title="No gaps found"
                    description="All clauses have evidence linked for the selected standard."
                  />
                ) : (
                  <div className="space-y-3">
                    {(coverage?.gap_clauses ?? [])
                      .filter((c) => selectedStandard === 'all' || c.standard === selectedStandard)
                      .map((clause) => {
                        const Icon = standardIcons[clause.standard]
                        const color = standardColors[clause.standard]

                        return (
                          <div
                            key={clause.clause_id}
                            className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg hover:bg-destructive/15 transition-all cursor-pointer"
                            onClick={() => setSelectedClauseId(clause.clause_id)}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                setSelectedClauseId(clause.clause_id)
                              }
                            }}
                          >
                            <div className="flex items-center gap-3">
                              <XCircle className="w-5 h-5 text-destructive flex-shrink-0" aria-hidden="true" />
                              <Icon className={`w-4 h-4 text-${color}-400 flex-shrink-0`} aria-hidden="true" />
                              <span className="font-medium text-foreground">{clause.clause_number}</span>
                              <span className="text-muted-foreground truncate">{clause.title}</span>
                            </div>
                            <p className="text-sm text-muted-foreground mt-2 ml-12">
                              Evidence gap for {clause.standard}
                            </p>
                            <div className="flex gap-2 mt-2 ml-12">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setSelectedClauseId(clause.clause_id)
                                  setViewMode('clauses')
                                }}
                              >
                                <Sparkles className="w-3 h-3 mr-1" aria-hidden="true" /> Review Mappings
                              </Button>
                            </div>
                          </div>
                        )
                      })}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Right Panel — Clause Details */}
        <Card className="max-h-[70vh] overflow-y-auto">
          <CardContent className="p-6">
            {selectedClause ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold text-foreground">Clause Details</h2>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedClauseId(null)}
                    aria-label="Close clause details"
                  >
                    <XCircle className="w-5 h-5" aria-hidden="true" />
                  </Button>
                </div>

                <div className="space-y-4">
                  {/* Clause Info */}
                  <div className="p-4 bg-surface rounded-lg border border-border">
                    <div className="flex items-center gap-2 mb-2">
                      {React.createElement(standardIcons[selectedClause.standard], {
                        className: `w-5 h-5 text-${standardColors[selectedClause.standard]}-400`,
                        'aria-hidden': 'true',
                      })}
                      <span className="font-bold text-foreground">{selectedClause.clause_number}</span>
                      <Badge variant="secondary">
                        {standards.find((s) => s.id === selectedClause.standard)?.code}
                      </Badge>
                    </div>
                    <h3 className="text-base font-medium text-foreground mb-2">{selectedClause.title}</h3>
                    <p className="text-sm text-muted-foreground">{selectedClause.description}</p>
                  </div>

                  {/* Keywords */}
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">Keywords</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedClause.keywords.map((keyword, i) => (
                        <Badge key={i} variant="outline">
                          {keyword}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Coverage Status */}
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">Coverage Status</h4>
                    {(() => {
                      const status = getCoverageStatus(selectedClause.id)
                      const evidence = getEvidenceForClause(selectedClause.id)
                      return (
                        <div
                          className={cn(
                            'p-3 rounded-lg flex items-center gap-3',
                            status === 'full'
                              ? 'bg-success/10 border border-success/30'
                              : status === 'partial'
                                ? 'bg-warning/10 border border-warning/30'
                                : 'bg-destructive/10 border border-destructive/30',
                          )}
                        >
                          {status === 'full' ? (
                            <CheckCircle2 className="w-5 h-5 text-success" aria-hidden="true" />
                          ) : status === 'partial' ? (
                            <Clock className="w-5 h-5 text-warning" aria-hidden="true" />
                          ) : (
                            <XCircle className="w-5 h-5 text-destructive" aria-hidden="true" />
                          )}
                          <div>
                            <p
                              className={cn(
                                'font-medium',
                                status === 'full'
                                  ? 'text-success'
                                  : status === 'partial'
                                    ? 'text-warning'
                                    : 'text-destructive',
                              )}
                            >
                              {status === 'full'
                                ? 'Fully Covered'
                                : status === 'partial'
                                  ? 'Partially Covered'
                                  : 'No Evidence'}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {evidence.length} evidence item(s) linked
                            </p>
                          </div>
                        </div>
                      )
                    })()}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-surface border border-border p-3">
                      <p className="text-xs text-muted-foreground">Linked Remediation</p>
                      <p className="mt-1 text-sm text-foreground font-medium">
                        {selectedClauseProvenance.actionLinks} action link(s)
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {selectedClauseProvenance.riskLinks} risk link(s)
                      </p>
                    </div>
                    <div className="rounded-lg bg-surface border border-border p-3">
                      <p className="text-xs text-muted-foreground">Framework Reach</p>
                      <p className="mt-1 text-sm text-foreground font-medium">
                        {selectedClauseProvenance.mappedFrameworks} mapped framework link(s)
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {selectedClauseProvenance.auditLinks} audit evidence item(s)
                      </p>
                    </div>
                  </div>

                  {/* Linked Evidence */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-muted-foreground">Linked Evidence</h4>
                      <span className="text-xs text-muted-foreground">
                        {selectedClauseProvenance.totalLinks} live link(s)
                      </span>
                    </div>
                    {selectedClauseEvidence.length > 0 ? (
                      <div className="space-y-2">
                        {selectedClauseEvidence.map((evidence) => {
                          const config =
                            evidenceTypeConfig[evidence.entity_type] ?? evidenceTypeConfig.document
                          const Icon = config.icon
                          const route = getEntityRoute(evidence.entity_type, evidence.entity_id)
                          const isDeleting = deletingLinkId === evidence.id
                          return (
                            <div
                              key={evidence.id}
                              className="p-3 bg-surface rounded-lg flex items-center gap-3 border border-border hover:border-border-strong transition-colors"
                            >
                              <div className={`p-1.5 rounded ${config.color} flex-shrink-0`} aria-hidden="true">
                                <Icon className="w-3 h-3 text-white" />
                              </div>
                              <div className="flex-grow min-w-0">
                                <p className="text-sm text-foreground truncate">
                                  {evidence.title ?? `${config.label} ${evidence.entity_id}`}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {new Date(evidence.created_at).toLocaleString()}
                                </p>
                              </div>
                              <div className="flex items-center gap-1 flex-shrink-0">
                                <Link
                                  to={route}
                                  className="p-1 rounded text-primary hover:text-primary/80 hover:bg-primary/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                                  aria-label={`View ${config.label} in ${route}`}
                                >
                                  <ArrowUpRight className="w-4 h-4" aria-hidden="true" />
                                </Link>
                                <button
                                  onClick={() => void handleDeleteLink(evidence.id)}
                                  disabled={isDeleting}
                                  className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50 disabled:cursor-not-allowed"
                                  aria-label={`Unlink ${config.label} from this clause`}
                                >
                                  <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                                </button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="p-4 bg-surface/50 rounded-lg border border-border text-center">
                        <p className="text-sm text-muted-foreground">No evidence linked yet</p>
                      </div>
                    )}
                  </div>

                  {/* Cross-Standard Mappings */}
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">Cross-Standard Mappings</h4>
                    {loadingMappings ? (
                      <TableSkeleton rows={3} columns={1} />
                    ) : mappings.length > 0 ? (
                      <div className="space-y-2">
                        {mappings.map((mapping) => (
                          <div
                            key={mapping.id}
                            className="rounded-lg border border-border bg-surface p-3"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm text-foreground">
                                  {mapping.primary_standard} {mapping.primary_clause}{' '}
                                  <span aria-hidden="true">→</span>{' '}
                                  {mapping.mapped_standard} {mapping.mapped_clause}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {mapping.mapping_type} • strength {mapping.mapping_strength}
                                </p>
                              </div>
                              {mapping.annex_sl_element && (
                                <Badge variant="secondary" className="flex-shrink-0">
                                  {mapping.annex_sl_element}
                                </Badge>
                              )}
                            </div>
                            {mapping.mapping_notes && (
                              <p className="mt-2 text-xs text-muted-foreground">{mapping.mapping_notes}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-4 bg-surface/50 rounded-lg border border-border text-center">
                        <p className="text-sm text-muted-foreground">
                          No cross-standard mappings found for this clause yet.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <EmptyState
                icon={<Target className="w-8 h-8 text-muted-foreground" />}
                title="Select a Clause"
                description="Click on any clause in the tree view to see details and linked evidence."
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* AI Auto-Tagger Dialog */}
      <Dialog
        open={showAutoTagger}
        onOpenChange={(open) => {
          setShowAutoTagger(open)
          if (!open) {
            setAutoTagText('')
            setAutoTagResults([])
            setAutoTagging(false)
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" aria-hidden="true" />
              AI Auto-Tagger
            </DialogTitle>
          </DialogHeader>

          <p className="text-muted-foreground text-sm">
            Paste any text (policy, procedure, audit finding, etc.) and the system will
            identify relevant ISO clauses. AI mode uses LLM reasoning for higher accuracy;
            keyword mode is instant.
          </p>

          <Textarea
            value={autoTagText}
            onChange={(e) => setAutoTagText(e.target.value)}
            placeholder="Paste your content here... e.g., 'This procedure describes the process for evaluating and approving new suppliers to ensure quality materials are procured.'"
            rows={6}
            aria-label="Content to auto-tag"
          />

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <div
                role="switch"
                aria-checked={useAiTagging}
                tabIndex={0}
                onClick={() => setUseAiTagging((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setUseAiTagging((v) => !v)
                  }
                }}
                className={cn(
                  'relative w-10 h-6 rounded-full transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                  useAiTagging ? 'bg-primary' : 'bg-muted',
                )}
              >
                <span
                  className={cn(
                    'absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform',
                    useAiTagging ? 'translate-x-4' : 'translate-x-0',
                  )}
                />
              </div>
              <span className="text-sm text-foreground font-medium">
                {useAiTagging ? 'AI-enhanced (LLM reasoning)' : 'Keyword matching (instant)'}
              </span>
            </label>
            {useAiTagging && (
              <span className="text-xs text-muted-foreground">May take 3–8 seconds</span>
            )}
          </div>

          <div className="flex gap-2">
            <Button
              onClick={handleAutoTag}
              disabled={!autoTagText.trim() || autoTagging || deepAnalyzing}
              className="flex-1"
            >
              {autoTagging ? (
                <>
                  <span className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" aria-hidden="true" />
                  {useAiTagging ? 'AI reasoning...' : 'Scanning...'}
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
                  Auto-Tag
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={handleDeepAnalysis}
              disabled={!autoTagText.trim() || deepAnalyzing || autoTagging}
              title="Run 5-stage Genspark analysis: keyword + LLM + cross-standard + quality scoring + conformance statement"
            >
              {deepAnalyzing ? (
                <>
                  <span className="w-4 h-4 mr-2 border-2 border-primary/30 border-t-primary rounded-full animate-spin" aria-hidden="true" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Brain className="w-4 h-4 mr-2" aria-hidden="true" />
                  Deep Analysis
                </>
              )}
            </Button>
          </div>

          {autoTagResults.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                  <Tag className="w-5 h-5 text-primary" aria-hidden="true" />
                  {`Detected ISO Clauses (${autoTagResults.length})`}
                </h3>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {autoTagResults.map((clause) => {
                  const deepResult = deepAnalysisResult?.primary_results.find(r => r.clause_id === clause.id)
                  const Icon = standardIcons[clause.standard]
                  const color = standardColors[clause.standard]
                  return (
                    <div
                      key={clause.id}
                      className="p-3 bg-surface rounded-lg flex items-start gap-3 border border-border"
                    >
                      <Icon className={`w-5 h-5 text-${color}-400 flex-shrink-0 mt-0.5`} aria-hidden="true" />
                      <div className="flex-grow min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-foreground">{clause.clause_number}</span>
                          <span className="text-muted-foreground text-sm truncate">{clause.title}</span>
                          {deepResult?.evidence_quality && (
                            <span className={cn(
                              'text-xs px-1.5 py-0.5 rounded font-medium',
                              deepResult.evidence_quality_code === 'TYPE_1' ? 'bg-success/10 text-success' :
                              deepResult.evidence_quality_code === 'TYPE_2' ? 'bg-info/10 text-info' :
                              'bg-muted text-muted-foreground'
                            )}>
                              {deepResult.evidence_quality}
                            </span>
                          )}
                          {deepResult?.confidence && (
                            <span className="text-xs text-muted-foreground">{deepResult.confidence}%</span>
                          )}
                        </div>
                        {deepResult?.evidence_snippet && (
                          <p className="text-xs text-muted-foreground mt-1 italic line-clamp-1">
                            &ldquo;{deepResult.evidence_snippet}&rdquo;
                          </p>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-shrink-0"
                        onClick={() => {
                          setSelectedClauseId(clause.id)
                          setShowAutoTagger(false)
                        }}
                      >
                        Apply
                      </Button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Deep Analysis Results — Stage 5 conformance statement */}
          {showDeepAnalysis && deepAnalysisResult && (
            <div className="border border-primary/30 rounded-lg p-4 bg-primary/5">
              <h3 className="text-sm font-bold text-foreground mb-3 flex items-center gap-2">
                <Brain className="w-4 h-4 text-primary" aria-hidden="true" />
                5-Stage Genspark Analysis
              </h3>
              <div className="grid grid-cols-3 gap-3 mb-3 text-center">
                <div className="bg-surface rounded p-2">
                  <div className="text-lg font-bold text-foreground">{deepAnalysisResult.total_clauses_matched}</div>
                  <div className="text-xs text-muted-foreground">Clauses matched</div>
                </div>
                <div className="bg-surface rounded p-2">
                  <div className="text-lg font-bold text-foreground">{deepAnalysisResult.standards_covered.length}</div>
                  <div className="text-xs text-muted-foreground">Standards covered</div>
                </div>
                <div className="bg-surface rounded p-2">
                  <div className="text-lg font-bold text-foreground">
                    {deepAnalysisResult.stages.stage_3_cross_standard?.cross_standard_matches.length ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground">Cross-standard links</div>
                </div>
              </div>
              {deepAnalysisResult.stages.stage_5_conformance?.conformance_statement && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                    Auditor Conformance Statement
                  </p>
                  <p className="text-sm text-foreground leading-relaxed italic border-l-2 border-primary pl-3">
                    {deepAnalysisResult.stages.stage_5_conformance.conformance_statement}
                  </p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Statement of Applicability Dialog */}
      <Dialog open={showSoA} onOpenChange={setShowSoA}>
        <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckSquare className="w-5 h-5 text-primary" aria-hidden="true" />
              Statement of Applicability — ISO 27001:2022
            </DialogTitle>
          </DialogHeader>
          {soaData && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{soaData.summary}</p>
                <Button size="sm" variant="outline" onClick={() => {
                  const blob = new Blob([JSON.stringify(soaData, null, 2)], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `soa-iso27001-${new Date().toISOString().slice(0, 10)}.json`
                  document.body.appendChild(a)
                  a.click()
                  document.body.removeChild(a)
                  URL.revokeObjectURL(url)
                }}>
                  <Download className="w-4 h-4 mr-1" aria-hidden="true" />
                  Export
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center text-sm">
                {[
                  { label: 'Implemented', value: soaData.statistics.implemented, color: 'text-success' },
                  { label: 'Partial', value: soaData.statistics.partial, color: 'text-warning' },
                  { label: 'Gap', value: soaData.statistics.not_implemented, color: 'text-destructive' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-surface rounded p-3 border border-border">
                    <div className={cn('text-2xl font-bold', color)}>{value}</div>
                    <div className="text-muted-foreground">{label}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                {soaData.controls.map((control) => (
                  <div
                    key={control.clause_id}
                    className={cn(
                      'p-3 rounded-lg border text-sm',
                      control.implementation_status === 'Implemented' ? 'border-success/30 bg-success/5' :
                      control.implementation_status === 'Partially Implemented' ? 'border-warning/30 bg-warning/5' :
                      'border-destructive/20 bg-destructive/5',
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-16 font-mono text-xs font-bold text-foreground pt-0.5">
                        {control.control_id}
                      </div>
                      <div className="flex-grow min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="font-medium text-foreground">{control.title}</span>
                          <Badge
                            variant={
                              control.implementation_status === 'Implemented' ? 'resolved' :
                              control.implementation_status === 'Partially Implemented' ? 'in-progress' :
                              'destructive'
                            }
                            className="text-xs"
                          >
                            {control.implementation_status}
                          </Badge>
                          {control.evidence_count > 0 && (
                            <span className="text-xs text-muted-foreground">{control.evidence_count} evidence item{control.evidence_count !== 1 ? 's' : ''}</span>
                          )}
                        </div>
                        {control.justification && (
                          <p className="text-xs text-muted-foreground">{control.justification}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
