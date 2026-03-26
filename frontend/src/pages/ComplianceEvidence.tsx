import React, { useEffect, useMemo, useState } from 'react'
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
} from 'lucide-react'
import {
  complianceApi,
  crossStandardMappingsApi,
  getApiErrorMessage,
  type ComplianceClauseRecord,
  type ComplianceCoverageResponse,
  type ComplianceReportResponse,
  type ComplianceStandardRecord,
  type CrossStandardMappingRecord,
  type EvidenceLinkRecord,
} from '../api/client'

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
  const [selectedStandard, setSelectedStandard] = useState<string | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedClauses, setExpandedClauses] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<'clauses' | 'evidence' | 'gaps'>('clauses')
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null)
  const [showAutoTagger, setShowAutoTagger] = useState(false)
  const [autoTagText, setAutoTagText] = useState('')
  const [autoTagResults, setAutoTagResults] = useState<ComplianceClauseRecord[]>([])
  const [standards, setStandards] = useState<ComplianceStandardRecord[]>([])
  const [clauses, setClauses] = useState<ComplianceClauseRecord[]>([])
  const [coverage, setCoverage] = useState<ComplianceCoverageResponse | null>(null)
  const [report, setReport] = useState<ComplianceReportResponse | null>(null)
  const [evidenceLinks, setEvidenceLinks] = useState<EvidenceLinkRecord[]>([])
  const [mappings, setMappings] = useState<CrossStandardMappingRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMappings, setLoadingMappings] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canonicalDataWarning = useMemo(
    () => standards.find((standard) => standard.canonical_data_degraded)?.canonical_data_message ?? null,
    [standards],
  )

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        const standardFilter = selectedStandard === 'all' ? undefined : selectedStandard
        const [standardsRes, clausesRes, coverageRes, reportRes, evidenceRes] = await Promise.all([
          complianceApi.listStandards(),
          complianceApi.listClauses(standardFilter, searchQuery || undefined),
          complianceApi.getCoverage(standardFilter),
          complianceApi.getReport(standardFilter),
          complianceApi.listEvidenceLinks(),
        ])

        if (cancelled) return

        setStandards(standardsRes.data)
        setClauses(clausesRes.data)
        setCoverage(coverageRes.data)
        setReport(reportRes.data)
        setEvidenceLinks(evidenceRes.data)

        if (
          selectedClauseId &&
          !clausesRes.data.some((clause) => clause.id === selectedClauseId) &&
          reportRes.data.clauses.length > 0
        ) {
          setSelectedClauseId(reportRes.data.clauses[0].clause_id)
        }
        if (!selectedClauseId && reportRes.data.clauses.length > 0) {
          setSelectedClauseId(reportRes.data.clauses[0].clause_id)
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
  }, [searchQuery, selectedStandard, selectedClauseId])

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
        const response = await crossStandardMappingsApi.list({ clause: selectedClause.clause_number })
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

  // Calculate compliance stats
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

  // Get evidence for a specific clause
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
      auditLinks: counts.audit || 0,
      actionLinks: counts.action || 0,
      riskLinks: counts.risk || 0,
      totalLinks: selectedClauseEvidence.length,
      mappedFrameworks: mappings.length,
    }
  }, [mappings.length, selectedClauseEvidence])

  // Filter clauses based on search and selected standard
  const filteredClauses = clauses

  // Toggle clause expansion
  const toggleClause = (clauseId: string) => {
    const newExpanded = new Set(expandedClauses)
    if (newExpanded.has(clauseId)) {
      newExpanded.delete(clauseId)
    } else {
      newExpanded.add(clauseId)
    }
    setExpandedClauses(newExpanded)
  }

  // Auto-tag handler
  const handleAutoTag = async () => {
    if (autoTagText.trim()) {
      try {
        const response = await complianceApi.autoTag(autoTagText)
        const taggedClauseIds = response.data.map((result) => result.clause_id)
        setAutoTagResults(clauses.filter((clause) => taggedClauseIds.includes(clause.id)))
      } catch (err) {
        setError(getApiErrorMessage(err))
      }
    }
  }

  // Get coverage status for a clause
  const getCoverageStatus = (clauseId: string): 'full' | 'partial' | 'none' => {
    const clauseDetail = clauseDetailsById.get(clauseId)
    if (clauseDetail?.status === 'full') return 'full'
    if (clauseDetail?.status === 'partial') return 'partial'
    return 'none'
  }

  // Render clause tree
  const renderClauseTree = (parentId: string | undefined, level: number, standard: string) => {
    const children = filteredClauses.filter(
      (c) =>
        (c.parent_clause ?? undefined) === parentId &&
        (selectedStandard === 'all' || c.standard === selectedStandard),
    )

    if (children.length === 0) return null

    return (
      <div className={`${level > 0 ? 'ml-6 border-l border-border pl-4' : ''}`}>
        {children.map((clause) => {
          const coverage = getCoverageStatus(clause.id)
          const evidence = getEvidenceForClause(clause.id)
          const isExpanded = expandedClauses.has(clause.id)
          const hasChildren = filteredClauses.some((c) => c.parent_clause === clause.id)
          const StandardIcon = standardIcons[clause.standard] || Award
          const color = standardColors[clause.standard] || 'blue'

          return (
            <div key={clause.id} className="mb-2">
              <div
                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                  selectedClauseId === clause.id
                    ? 'bg-surface ring-2 ring-primary'
                    : 'bg-surface/50 hover:bg-surface'
                }`}
                onClick={() => setSelectedClauseId(clause.id)}
                role="button"
                tabIndex={0}
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
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </button>
                ) : (
                  <div className="w-4" />
                )}

                <div
                  className={`w-2 h-2 rounded-full ${
                    coverage === 'full'
                      ? 'bg-success'
                      : coverage === 'partial'
                        ? 'bg-warning'
                        : 'bg-destructive'
                  }`}
                />

                <StandardIcon className={`w-4 h-4 text-${color}-400`} />

                <span className="text-sm font-medium text-muted-foreground">
                  {clause.clause_number}
                </span>
                <span className="text-sm text-foreground flex-grow">{clause.title}</span>

                {evidence.length > 0 && (
                  <span className="text-xs bg-surface text-muted-foreground px-2 py-1 rounded-full flex items-center gap-1 border border-border">
                    <Link2 className="w-3 h-3" />
                    {evidence.length} evidence
                  </span>
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
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
              <Target className="w-8 h-8 text-primary" />
              ISO Compliance Evidence Center
            </h1>
            <p className="text-muted-foreground mt-1">
              Live repository for compliance evidence, clause coverage, and cross-standard mappings
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAutoTagger(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary-hover transition-all"
            >
              <Sparkles className="w-4 h-4" />
              AI Auto-Tagger
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-secondary border border-border rounded-lg text-secondary-foreground font-medium hover:bg-surface transition-all">
              <Download className="w-4 h-4" />
              {report ? `${report.persisted_evidence_links} persisted links` : 'Evidence report'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {loading && (
          <div className="mb-4 rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
            Loading compliance evidence from live APIs...
          </div>
        )}

        {canonicalDataWarning && (
          <div className="mb-4 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Compliance data is running in degraded mode</p>
              <p>{canonicalDataWarning}</p>
            </div>
          </div>
        )}

        {/* Compliance Score Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedStandard(standard.id)
                  }
                }}
                className={`p-4 rounded-xl bg-card border-2 cursor-pointer transition-all duration-200 ${
                  selectedStandard === standard.id
                    ? `border-primary shadow-lg shadow-primary/20`
                    : 'border-border hover:border-border-strong'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg bg-${color}-500/20`}>
                      <Icon className={`w-5 h-5 text-${color}-400`} />
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
                  <div className={`text-2xl font-bold text-${color}-400`}>{percentage}%</div>
                </div>

                <div className="w-full bg-surface rounded-full h-2 mb-3">
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

        {/* View Mode Tabs & Search */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex bg-secondary rounded-lg p-1">
            {[
              { id: 'clauses', label: 'Clause View', icon: BookOpen },
              { id: 'evidence', label: 'Evidence List', icon: FileText },
              { id: 'gaps', label: 'Gap Analysis', icon: AlertTriangle },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setViewMode(tab.id as typeof viewMode)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  viewMode === tab.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search clauses or keywords..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-80 pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/50 focus:border-primary"
              />
            </div>

            <select
              value={selectedStandard}
              onChange={(e) => setSelectedStandard(e.target.value)}
              className="px-4 py-2 bg-background border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary/50"
            >
              <option value="all">All Standards</option>
              {standards.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Panel - Clause Tree / Evidence List */}
        <div className="lg:col-span-2 bg-card border border-border rounded-xl p-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {viewMode === 'clauses' && (
            <>
              <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-primary" />
                Clause Structure
              </h2>
              {selectedStandard === 'all'
                ? standards.map((standard) => (
                    <div key={standard.id} className="mb-6">
                      <h3 className="text-md font-semibold text-foreground mb-3 flex items-center gap-2">
                        {React.createElement(standardIcons[standard.id], {
                          className: `w-4 h-4 text-${standardColors[standard.id]}-400`,
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
              <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-emerald-400" />
                All Evidence ({evidenceLinks.length} items)
              </h2>
              {evidenceLinks.length === 0 && (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-gray-500 mb-4" />
                  <h3 className="text-lg font-semibold text-gray-400 mb-2">No evidence items</h3>
                  <p className="text-sm text-gray-500">
                    Evidence items will appear here when linked to ISO clauses.
                  </p>
                </div>
              )}
              <div className="space-y-3">
                {evidenceLinks.map((evidence) => {
                  const config =
                    evidenceTypeConfig[evidence.entity_type] ?? evidenceTypeConfig.document
                  const Icon = config.icon

                  return (
                    <div
                      key={evidence.id}
                      className="p-4 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-all cursor-pointer"
                    >
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg ${config.color}`}>
                          <Icon className="w-4 h-4 text-white" />
                        </div>
                        <div className="flex-grow">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-medium text-white">
                              {evidence.title ?? `${config.label} ${evidence.entity_id}`}
                            </h4>
                            {evidence.linked_by !== 'manual' && (
                              <span className="flex items-center gap-1 text-xs bg-purple-500/20 text-purple-400 px-2 py-1 rounded-full">
                                <Sparkles className="w-3 h-3" />
                                {evidence.linked_by} {evidence.confidence ?? ''}%
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-400 mb-2">
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
                        <span className="text-xs text-gray-500">
                          {new Date(evidence.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {viewMode === 'gaps' && (
            <>
              <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                Gap Analysis - Clauses Needing Evidence
              </h2>
              <div className="space-y-3">
                {(coverage?.gap_clauses ?? [])
                  .filter((c) => selectedStandard === 'all' || c.standard === selectedStandard)
                  .map((clause) => {
                    const Icon = standardIcons[clause.standard]
                    const color = standardColors[clause.standard]

                    return (
                      <div
                        key={clause.clause_id}
                        className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-all cursor-pointer"
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
                          <XCircle className="w-5 h-5 text-red-400" />
                          <Icon className={`w-4 h-4 text-${color}-400`} />
                          <span className="font-medium text-white">{clause.clause_number}</span>
                          <span className="text-gray-300">{clause.title}</span>
                        </div>
                        <p className="text-sm text-gray-400 mt-2 ml-12">
                          Evidence gap for {clause.standard}
                        </p>
                        <div className="flex gap-2 mt-2 ml-12">
                          <button className="text-xs bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded-full flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> Review Mappings
                          </button>
                        </div>
                      </div>
                    )
                  })}
              </div>
            </>
          )}
        </div>

        {/* Right Panel - Clause Details */}
        <div className="bg-slate-800 rounded-xl p-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {selectedClause ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-white">Clause Details</h2>
                <button
                  onClick={() => setSelectedClauseId(null)}
                  className="text-gray-400 hover:text-white"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* Clause Info */}
                <div className="p-4 bg-slate-700/50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    {React.createElement(standardIcons[selectedClause.standard], {
                      className: `w-5 h-5 text-${standardColors[selectedClause.standard]}-400`,
                    })}
                    <span className="font-bold text-white">{selectedClause.clause_number}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full bg-${standardColors[selectedClause.standard]}-500/20 text-${standardColors[selectedClause.standard]}-400`}
                    >
                      {standards.find((s) => s.id === selectedClause.standard)?.code}
                    </span>
                  </div>
                  <h3 className="text-lg font-medium text-white mb-2">{selectedClause.title}</h3>
                  <p className="text-sm text-gray-400">{selectedClause.description}</p>
                </div>

                {/* Keywords */}
                <div>
                  <h4 className="text-sm font-medium text-gray-400 mb-2">Keywords</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedClause.keywords.map((keyword, i) => (
                      <span
                        key={i}
                        className="text-xs bg-slate-700 text-gray-300 px-2 py-1 rounded-full"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Coverage Status */}
                <div>
                  <h4 className="text-sm font-medium text-gray-400 mb-2">Coverage Status</h4>
                  {(() => {
                    const status = getCoverageStatus(selectedClause.id)
                    const evidence = getEvidenceForClause(selectedClause.id)
                    return (
                      <div
                        className={`p-3 rounded-lg flex items-center gap-3 ${
                          status === 'full'
                            ? 'bg-emerald-500/20 border border-emerald-500/30'
                            : status === 'partial'
                              ? 'bg-yellow-500/20 border border-yellow-500/30'
                              : 'bg-red-500/20 border border-red-500/30'
                        }`}
                      >
                        {status === 'full' ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        ) : status === 'partial' ? (
                          <Clock className="w-5 h-5 text-yellow-400" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-400" />
                        )}
                        <div>
                          <p
                            className={`font-medium ${
                              status === 'full'
                                ? 'text-emerald-400'
                                : status === 'partial'
                                  ? 'text-yellow-400'
                                  : 'text-red-400'
                            }`}
                          >
                            {status === 'full'
                              ? 'Fully Covered'
                              : status === 'partial'
                                ? 'Partially Covered'
                                : 'No Evidence'}
                          </p>
                          <p className="text-xs text-gray-400">
                            {evidence.length} evidence item(s) linked
                          </p>
                        </div>
                      </div>
                    )
                  })()}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-700/40 p-3">
                    <p className="text-xs text-gray-400">Linked Remediation</p>
                    <p className="mt-1 text-sm text-white">
                      {selectedClauseProvenance.actionLinks} action link(s)
                    </p>
                    <p className="text-xs text-gray-500">
                      {selectedClauseProvenance.riskLinks} risk link(s)
                    </p>
                  </div>
                  <div className="rounded-lg bg-slate-700/40 p-3">
                    <p className="text-xs text-gray-400">Framework Reach</p>
                    <p className="mt-1 text-sm text-white">
                      {selectedClauseProvenance.mappedFrameworks} mapped framework link(s)
                    </p>
                    <p className="text-xs text-gray-500">
                      {selectedClauseProvenance.auditLinks} audit evidence item(s)
                    </p>
                  </div>
                </div>

                {/* Linked Evidence */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-gray-400">Linked Evidence</h4>
                    <span className="text-xs text-gray-400">
                      {selectedClauseProvenance.totalLinks} live link(s)
                    </span>
                  </div>
                  {selectedClauseEvidence.length > 0 ? (
                    <div className="space-y-2">
                      {selectedClauseEvidence.map((evidence) => {
                        const config =
                          evidenceTypeConfig[evidence.entity_type] ?? evidenceTypeConfig.document
                        const Icon = config.icon
                        return (
                          <div
                            key={evidence.id}
                            className="p-3 bg-slate-700/50 rounded-lg flex items-center gap-3"
                          >
                            <div className={`p-1.5 rounded ${config.color}`}>
                              <Icon className="w-3 h-3 text-white" />
                            </div>
                            <div className="flex-grow">
                              <p className="text-sm text-white">
                                {evidence.title ?? `${config.label} ${evidence.entity_id}`}
                              </p>
                              <p className="text-xs text-gray-400">
                                {new Date(evidence.created_at).toLocaleString()}
                              </p>
                            </div>
                            <a
                              href={`/${evidence.entity_type}s`}
                              className="text-emerald-400 hover:text-emerald-300"
                            >
                              <ArrowUpRight className="w-4 h-4" />
                            </a>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="p-4 bg-slate-700/30 rounded-lg text-center">
                      <p className="text-sm text-gray-400">No evidence linked yet</p>
                    </div>
                  )}
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-400 mb-2">Cross-Standard Mappings</h4>
                  {loadingMappings ? (
                    <div className="p-4 bg-slate-700/30 rounded-lg text-sm text-gray-400">
                      Loading live cross-standard mappings...
                    </div>
                  ) : mappings.length > 0 ? (
                    <div className="space-y-2">
                      {mappings.map((mapping) => (
                        <div
                          key={mapping.id}
                          className="rounded-lg border border-slate-700 bg-slate-700/40 p-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-sm text-white">
                                {mapping.primary_standard} {mapping.primary_clause} {'->'}{' '}
                                {mapping.mapped_standard} {mapping.mapped_clause}
                              </p>
                              <p className="text-xs text-gray-400">
                                {mapping.mapping_type} • strength {mapping.mapping_strength}
                              </p>
                            </div>
                            {mapping.annex_sl_element && (
                              <span className="rounded-full bg-primary/20 px-2 py-1 text-xs text-primary">
                                {mapping.annex_sl_element}
                              </span>
                            )}
                          </div>
                          {mapping.mapping_notes && (
                            <p className="mt-2 text-xs text-gray-400">{mapping.mapping_notes}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 bg-slate-700/30 rounded-lg text-sm text-gray-400">
                      No cross-standard mappings found for this clause yet.
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <Target className="w-16 h-16 text-slate-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-400 mb-2">Select a Clause</h3>
              <p className="text-sm text-gray-500">
                Click on any clause in the tree view to see details and linked evidence
              </p>
            </div>
          )}
        </div>
      </div>

      {/* AI Auto-Tagger Modal */}
      {showAutoTagger && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-400" />
                AI Auto-Tagger
              </h2>
              <button
                onClick={() => {
                  setShowAutoTagger(false)
                  setAutoTagText('')
                  setAutoTagResults([])
                }}
                className="text-gray-400 hover:text-white"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            <p className="text-gray-400 mb-4">
              Paste any text content (policy, procedure, audit finding, etc.) and AI will
              automatically identify relevant ISO clauses.
            </p>

            <textarea
              value={autoTagText}
              onChange={(e) => setAutoTagText(e.target.value)}
              placeholder="Paste your content here... e.g., 'This procedure describes the process for evaluating and approving new suppliers to ensure quality materials are procured.'"
              rows={6}
              className="w-full p-4 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4"
            />

            <button
              onClick={handleAutoTag}
              disabled={!autoTagText.trim()}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg text-white font-bold flex items-center justify-center gap-2 hover:from-purple-700 hover:to-pink-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed mb-4"
            >
              <Sparkles className="w-5 h-5" />
              Analyze & Auto-Tag
            </button>

            {autoTagResults.length > 0 && (
              <div>
                <h3 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
                  <Tag className="w-5 h-5 text-emerald-400" />
                  Detected ISO Clauses ({autoTagResults.length})
                </h3>
                <div className="space-y-2">
                  {autoTagResults.map((clause) => {
                    const Icon = standardIcons[clause.standard]
                    const color = standardColors[clause.standard]
                    return (
                      <div
                        key={clause.id}
                        className="p-3 bg-slate-700/50 rounded-lg flex items-center gap-3"
                      >
                        <Icon className={`w-5 h-5 text-${color}-400`} />
                        <span className="font-medium text-white">{clause.clause_number}</span>
                        <span className="text-gray-300 flex-grow">{clause.title}</span>
                        <button
                          className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1 rounded-full"
                          onClick={() => {
                            setSelectedClauseId(clause.id)
                            setShowAutoTagger(false)
                          }}
                        >
                          Apply Tag
                        </button>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
