import React, { useState, useMemo, useCallback, useEffect } from 'react';
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
  Plus,
  Tag,
} from 'lucide-react';
import { ISO_STANDARDS, ISOClause, getAllClauses } from '../data/isoStandards';
import { complianceApi, AutoTagResult } from '../api/client';

// Evidence types that can be linked to ISO clauses
type EvidenceType = 'policy' | 'document' | 'audit' | 'incident' | 'action' | 'risk' | 'training';

interface EvidenceItem {
  id: string;
  type: EvidenceType;
  title: string;
  description: string;
  date: string;
  status: 'active' | 'draft' | 'archived';
  linkedClauses: string[];
  autoTagged: boolean;
  confidence?: number;
  link: string;
}

// Evidence items are loaded from the API on mount

const evidenceTypeConfig: Record<EvidenceType, { icon: React.ElementType; label: string; color: string }> = {
  policy: { icon: BookOpen, label: 'Policy', color: 'bg-purple-500' },
  document: { icon: FileText, label: 'Document', color: 'bg-blue-500' },
  audit: { icon: ClipboardCheck, label: 'Audit', color: 'bg-emerald-500' },
  incident: { icon: AlertTriangle, label: 'Incident', color: 'bg-red-500' },
  action: { icon: Zap, label: 'Action', color: 'bg-yellow-500' },
  risk: { icon: Shield, label: 'Risk', color: 'bg-orange-500' },
  training: { icon: Award, label: 'Training', color: 'bg-cyan-500' },
};

const standardIcons: Record<string, React.ElementType> = {
  iso9001: Award,
  iso14001: Leaf,
  iso45001: HardHat,
  iso27001: Shield,
  planetmark: Leaf,
  uvdb: Award,
};

const standardColors: Record<string, string> = {
  iso9001: 'blue',
  iso14001: 'green',
  iso45001: 'orange',
  iso27001: 'purple',
  planetmark: 'teal',
  uvdb: 'yellow',
};

export default function ComplianceEvidence() {
  const [selectedStandard, setSelectedStandard] = useState<string | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedClauses, setExpandedClauses] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'clauses' | 'evidence' | 'gaps'>('clauses');
  const [selectedClause, setSelectedClause] = useState<ISOClause | null>(null);
  const [showAutoTagger, setShowAutoTagger] = useState(false);
  const [autoTagText, setAutoTagText] = useState('');
  const [autoTagResults, setAutoTagResults] = useState<ISOClause[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([]);

  useEffect(() => {
    const fetchEvidence = async () => {
      try {
        const [coverageRes] = await Promise.allSettled([
          complianceApi.getCoverage(),
          complianceApi.getGaps(),
        ]);

        // Build evidence items from coverage data if available
        const items: EvidenceItem[] = [];
        if (coverageRes.status === 'fulfilled' && coverageRes.value.data) {
          const data = coverageRes.value.data as any;
          if (data.covered_clauses && Array.isArray(data.covered_clauses)) {
            data.covered_clauses.forEach((link: any, idx: number) => {
              items.push({
                id: `ev-${idx}`,
                type: (link.entity_type || 'document') as EvidenceType,
                title: link.entity_name || link.entity_type || 'Linked Evidence',
                description: `Evidence linked to clause ${link.clause_id}`,
                date: link.created_at || new Date().toISOString().split('T')[0],
                status: 'active',
                linkedClauses: [link.clause_id],
                autoTagged: link.linked_by === 'auto',
                confidence: link.confidence ? link.confidence * 100 : undefined,
                link: '#',
              });
            });
          }
        }

        setEvidenceItems(items);
      } catch (err) {
        console.error('Failed to fetch compliance evidence:', err);
        setEvidenceItems([]);
      } finally {
        // loading complete
      }
    };

    fetchEvidence();
  }, []);

  const complianceStats = useMemo(() => {
    const stats: Record<string, { total: number; covered: number; partial: number; gaps: number }> = {};
    
    ISO_STANDARDS.forEach(standard => {
      const hasSubClauses = standard.clauses.some(c => c.level === 2);
      const mainClauses = hasSubClauses
        ? standard.clauses.filter(c => c.level === 2)
        : standard.clauses.filter(c => c.level === 1);

      const fullyCovered = mainClauses.filter(c => {
        const evidence = evidenceItems.filter(e => e.linkedClauses.includes(c.id));
        return evidence.length >= 2;
      }).length;

      const partiallyCovered = mainClauses.filter(c => {
        const evidence = evidenceItems.filter(e => e.linkedClauses.includes(c.id));
        return evidence.length === 1;
      }).length;
      
      stats[standard.id] = {
        total: mainClauses.length,
        covered: fullyCovered,
        partial: partiallyCovered,
        gaps: mainClauses.length - fullyCovered - partiallyCovered,
      };
    });
    
    return stats;
  }, [evidenceItems]);

  const getEvidenceForClause = (clauseId: string): EvidenceItem[] => {
    return evidenceItems.filter(e => e.linkedClauses.includes(clauseId));
  };

  // Filter clauses based on search and selected standard
  const filteredClauses = useMemo(() => {
    let clauses = selectedStandard === 'all' 
      ? getAllClauses() 
      : ISO_STANDARDS.find(s => s.id === selectedStandard)?.clauses || [];

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      clauses = clauses.filter(c => 
        c.title.toLowerCase().includes(query) ||
        c.clauseNumber.includes(query) ||
        c.keywords.some(k => k.toLowerCase().includes(query))
      );
    }

    return clauses;
  }, [selectedStandard, searchQuery]);

  // Toggle clause expansion
  const toggleClause = (clauseId: string) => {
    const newExpanded = new Set(expandedClauses);
    if (newExpanded.has(clauseId)) {
      newExpanded.delete(clauseId);
    } else {
      newExpanded.add(clauseId);
    }
    setExpandedClauses(newExpanded);
  };

  const [autoTagging, setAutoTagging] = useState(false);
  const [apiTagResults, setApiTagResults] = useState<AutoTagResult[]>([]);

  const handleAutoTag = useCallback(async () => {
    if (!autoTagText.trim()) return;
    try {
      setAutoTagging(true);
      const results = await complianceApi.autoTag(autoTagText, false);
      const arr = Array.isArray(results) ? results : [];
      setApiTagResults(arr);
      const allClauses = getAllClauses();
      const mapped = arr
        .map(r => allClauses.find(c => c.id === r.clause_id))
        .filter((c): c is ISOClause => c !== undefined);
      setAutoTagResults(mapped);
    } catch (err) {
      console.error('Auto-tag failed', err);
    } finally {
      setAutoTagging(false);
    }
  }, [autoTagText]);

  // Get coverage status for a clause
  const getCoverageStatus = (clauseId: string): 'full' | 'partial' | 'none' => {
    const evidence = getEvidenceForClause(clauseId);
    if (evidence.length >= 2) return 'full';
    if (evidence.length === 1) return 'partial';
    return 'none';
  };

  // Render clause tree
  const renderClauseTree = (parentId: string | undefined, level: number, standard: string) => {
    const children = filteredClauses.filter(c => 
      c.parentClause === parentId && 
      (selectedStandard === 'all' || c.standard === selectedStandard)
    );

    if (children.length === 0) return null;

    return (
      <div className={`${level > 0 ? 'ml-6 border-l border-border pl-4' : ''}`}>
        {children.map(clause => {
          const coverage = getCoverageStatus(clause.id);
          const evidence = getEvidenceForClause(clause.id);
          const isExpanded = expandedClauses.has(clause.id);
          const hasChildren = filteredClauses.some(c => c.parentClause === clause.id);
          const StandardIcon = standardIcons[clause.standard] || Award;
          const color = standardColors[clause.standard] || 'blue';

          return (
            <div key={clause.id} className="mb-2">
              <div 
                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                  selectedClause?.id === clause.id 
                    ? 'bg-surface ring-2 ring-primary' 
                    : 'bg-surface/50 hover:bg-surface'
                }`}
                onClick={() => setSelectedClause(clause)}
              >
                {hasChildren ? (
                  <button 
                    onClick={(e) => { e.stopPropagation(); toggleClause(clause.id); }}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </button>
                ) : (
                  <div className="w-4" />
                )}

                <div className={`w-2 h-2 rounded-full ${
                  coverage === 'full' ? 'bg-success' : 
                  coverage === 'partial' ? 'bg-warning' : 
                  'bg-destructive'
                }`} />

                <StandardIcon className={`w-4 h-4 text-${color}-400`} />

                <span className="text-sm font-medium text-muted-foreground">{clause.clauseNumber}</span>
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
          );
        })}
      </div>
    );
  };

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
              Central repository for all compliance evidence mapped to ISO standards
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
              Export Report
            </button>
          </div>
        </div>

        {/* Compliance Score Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {ISO_STANDARDS.map(standard => {
            const stats = complianceStats[standard.id];
            const percentage = stats.total > 0
              ? Math.round((stats.covered + stats.partial * 0.5) / stats.total * 100)
              : 0;
            const Icon = standardIcons[standard.id];
            const color = standardColors[standard.id];

            return (
              <div 
                key={standard.id}
                onClick={() => setSelectedStandard(standard.id)}
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
                      <p className="text-xs text-muted-foreground">{standard.name}</p>
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
            );
          })}
        </div>

        {/* View Mode Tabs & Search */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex bg-secondary rounded-lg p-1">
            {[
              { id: 'clauses', label: 'Clause View', icon: BookOpen },
              { id: 'evidence', label: 'Evidence List', icon: FileText },
              { id: 'gaps', label: 'Gap Analysis', icon: AlertTriangle },
            ].map(tab => (
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
              {ISO_STANDARDS.map(s => (
                <option key={s.id} value={s.id}>{s.code}</option>
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
              {selectedStandard === 'all' ? (
                ISO_STANDARDS.map(standard => (
                  <div key={standard.id} className="mb-6">
                    <h3 className="text-md font-semibold text-foreground mb-3 flex items-center gap-2">
                      {React.createElement(standardIcons[standard.id], { className: `w-4 h-4 text-${standardColors[standard.id]}-400` })}
                      {standard.code}
                    </h3>
                    {renderClauseTree(undefined, 0, standard.id)}
                  </div>
                ))
              ) : (
                renderClauseTree(undefined, 0, selectedStandard)
              )}
            </>
          )}

          {viewMode === 'evidence' && (
            <>
              <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-success" />
                All Evidence ({evidenceItems.length} items)
              </h2>
              <div className="space-y-3">
                {evidenceItems.map(evidence => {
                  const config = evidenceTypeConfig[evidence.type];
                  const Icon = config.icon;

                  return (
                    <div 
                      key={evidence.id}
                      className="p-4 bg-surface/50 rounded-lg hover:bg-surface transition-all cursor-pointer"
                    >
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg ${config.color}`}>
                          <Icon className="w-4 h-4 text-white" />
                        </div>
                        <div className="flex-grow">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-medium text-foreground">{evidence.title}</h4>
                            {evidence.autoTagged && (
                              <span className="flex items-center gap-1 text-xs bg-purple-500/20 text-purple-400 px-2 py-1 rounded-full">
                                <Sparkles className="w-3 h-3" />
                                Auto-tagged {evidence.confidence}%
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mb-2">{evidence.description}</p>
                          <div className="flex items-center gap-2 flex-wrap">
                            {evidence.linkedClauses.map(clauseId => {
                              const clause = getAllClauses().find(c => c.id === clauseId);
                              if (!clause) return null;
                              const color = standardColors[clause.standard];
                              return (
                                <span 
                                  key={clauseId}
                                  className={`text-xs bg-${color}-500/20 text-${color}-400 px-2 py-1 rounded-full`}
                                >
                                  {clause.clauseNumber}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                        <span className="text-xs text-muted-foreground">{evidence.date}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {viewMode === 'gaps' && (
            <>
              <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-destructive" />
                Gap Analysis - Clauses Needing Evidence
              </h2>
              <div className="space-y-3">
                {getAllClauses()
                  .filter(c => {
                    const standard = ISO_STANDARDS.find(s => s.id === c.standard);
                    const hasSubClauses = standard?.clauses.some(cl => cl.level === 2);
                    const targetLevel = hasSubClauses ? 2 : 1;
                    return c.level === targetLevel && getCoverageStatus(c.id) === 'none';
                  })
                  .filter(c => selectedStandard === 'all' || c.standard === selectedStandard)
                  .map(clause => {
                    const Icon = standardIcons[clause.standard];
                    const color = standardColors[clause.standard];

                    return (
                      <div 
                        key={clause.id}
                        className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-all cursor-pointer"
                        onClick={() => setSelectedClause(clause)}
                      >
                        <div className="flex items-center gap-3">
                          <XCircle className="w-5 h-5 text-destructive" />
                          <Icon className={`w-4 h-4 text-${color}-400`} />
                          <span className="font-medium text-foreground">{clause.clauseNumber}</span>
                          <span className="text-muted-foreground">{clause.title}</span>
                        </div>
                        <p className="text-sm text-muted-foreground mt-2 ml-12">{clause.description}</p>
                        <div className="flex gap-2 mt-2 ml-12">
                          <button className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1 rounded-full flex items-center gap-1">
                            <Plus className="w-3 h-3" /> Add Evidence
                          </button>
                          <button className="text-xs bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded-full flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> Find Matches
                          </button>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </>
          )}
        </div>

        {/* Right Panel - Clause Details */}
        <div className="bg-card border border-border rounded-xl p-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {selectedClause ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-foreground">Clause Details</h2>
                <button 
                  onClick={() => setSelectedClause(null)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="p-4 bg-surface/50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    {React.createElement(standardIcons[selectedClause.standard], { 
                      className: `w-5 h-5 text-${standardColors[selectedClause.standard]}-400` 
                    })}
                    <span className="font-bold text-foreground">{selectedClause.clauseNumber}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full bg-${standardColors[selectedClause.standard]}-500/20 text-${standardColors[selectedClause.standard]}-400`}>
                      {ISO_STANDARDS.find(s => s.id === selectedClause.standard)?.code}
                    </span>
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-2">{selectedClause.title}</h3>
                  <p className="text-sm text-muted-foreground">{selectedClause.description}</p>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Keywords</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedClause.keywords.map((keyword, i) => (
                      <span key={i} className="text-xs bg-surface text-muted-foreground px-2 py-1 rounded-full border border-border">
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Coverage Status</h4>
                  {(() => {
                    const status = getCoverageStatus(selectedClause.id);
                    const evidence = getEvidenceForClause(selectedClause.id);
                    return (
                      <div className={`p-3 rounded-lg flex items-center gap-3 ${
                        status === 'full' ? 'bg-emerald-500/20 border border-emerald-500/30' :
                        status === 'partial' ? 'bg-yellow-500/20 border border-yellow-500/30' :
                        'bg-red-500/20 border border-red-500/30'
                      }`}>
                        {status === 'full' ? <CheckCircle2 className="w-5 h-5 text-success" /> :
                         status === 'partial' ? <Clock className="w-5 h-5 text-warning" /> :
                         <XCircle className="w-5 h-5 text-destructive" />}
                        <div>
                          <p className={`font-medium ${
                            status === 'full' ? 'text-success' :
                            status === 'partial' ? 'text-warning' :
                            'text-destructive'
                          }`}>
                            {status === 'full' ? 'Fully Covered' :
                             status === 'partial' ? 'Partially Covered' :
                             'No Evidence'}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {evidence.length} evidence item(s) linked
                          </p>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-muted-foreground">Linked Evidence</h4>
                    <button className="text-xs text-primary hover:text-primary-hover flex items-center gap-1">
                      <Plus className="w-3 h-3" /> Add Link
                    </button>
                  </div>
                  {getEvidenceForClause(selectedClause.id).length > 0 ? (
                    <div className="space-y-2">
                      {getEvidenceForClause(selectedClause.id).map(evidence => {
                        const config = evidenceTypeConfig[evidence.type];
                        const Icon = config.icon;
                        return (
                          <div key={evidence.id} className="p-3 bg-surface/50 rounded-lg flex items-center gap-3">
                            <div className={`p-1.5 rounded ${config.color}`}>
                              <Icon className="w-3 h-3 text-white" />
                            </div>
                            <div className="flex-grow">
                              <p className="text-sm text-foreground">{evidence.title}</p>
                              <p className="text-xs text-muted-foreground">{evidence.date}</p>
                            </div>
                            <a href={evidence.link} className="text-primary hover:text-primary-hover">
                              <ArrowUpRight className="w-4 h-4" />
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="p-4 bg-surface/30 rounded-lg text-center">
                      <p className="text-sm text-muted-foreground">No evidence linked yet</p>
                      <button className="mt-2 text-xs bg-primary hover:bg-primary-hover text-primary-foreground px-3 py-1.5 rounded-lg flex items-center gap-1 mx-auto">
                        <Plus className="w-3 h-3" /> Link Evidence
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <Target className="w-16 h-16 text-muted-foreground/40 mb-4" />
              <h3 className="text-lg font-medium text-muted-foreground mb-2">Select a Clause</h3>
              <p className="text-sm text-muted-foreground/70">
                Click on any clause in the tree view to see details and linked evidence
              </p>
            </div>
          )}
        </div>
      </div>

      {/* AI Auto-Tagger Modal */}
      {showAutoTagger && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="auto-tagger-title"
          aria-describedby="auto-tagger-desc"
          onClick={(e) => { if (e.target === e.currentTarget) { setShowAutoTagger(false); setAutoTagText(''); setAutoTagResults([]); } }}
          onKeyDown={(e) => { if (e.key === 'Escape') { setShowAutoTagger(false); setAutoTagText(''); setAutoTagResults([]); } }}
        >
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 id="auto-tagger-title" className="text-xl font-bold text-foreground flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-400" />
                AI Auto-Tagger
              </h2>
              <button 
                onClick={() => { setShowAutoTagger(false); setAutoTagText(''); setAutoTagResults([]); }}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Close auto-tagger"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            <p id="auto-tagger-desc" className="text-muted-foreground mb-4">
              Paste any text content (policy, procedure, audit finding, etc.) and AI will automatically identify relevant ISO clauses.
            </p>

            <textarea
              value={autoTagText}
              onChange={(e) => setAutoTagText(e.target.value)}
              placeholder="Paste your content here... e.g., 'This procedure describes the process for evaluating and approving new suppliers to ensure quality materials are procured.'"
              rows={6}
              className="w-full p-4 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4"
              aria-label="Content to auto-tag"
            />

            <button
              onClick={handleAutoTag}
              disabled={!autoTagText.trim() || autoTagging}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg text-white font-bold flex items-center justify-center gap-2 hover:from-purple-700 hover:to-pink-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed mb-4"
            >
              <Sparkles className="w-5 h-5" />
              {autoTagging ? 'Analyzing...' : 'Analyze & Auto-Tag'}
            </button>

            {autoTagResults.length > 0 && (
              <div>
                <h3 className="text-lg font-bold text-foreground mb-3 flex items-center gap-2">
                  <Tag className="w-5 h-5 text-success" />
                  Detected ISO Clauses ({autoTagResults.length})
                </h3>
                <div className="space-y-2">
                  {autoTagResults.map(clause => {
                    const Icon = standardIcons[clause.standard];
                    const color = standardColors[clause.standard];
                    const apiResult = apiTagResults.find(r => r.clause_id === clause.id);
                    return (
                      <div key={clause.id} className="p-3 bg-surface/50 rounded-lg flex items-center gap-3">
                        <Icon className={`w-5 h-5 text-${color}-400`} />
                        <span className="font-medium text-foreground">{clause.clauseNumber}</span>
                        <span className="text-muted-foreground flex-grow">{clause.title}</span>
                        {apiResult && (
                          <span className="text-xs text-purple-400">{Math.round(apiResult.confidence)}%</span>
                        )}
                        <button className="text-xs bg-primary hover:bg-primary-hover text-primary-foreground px-3 py-1 rounded-full">
                          Apply Tag
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
