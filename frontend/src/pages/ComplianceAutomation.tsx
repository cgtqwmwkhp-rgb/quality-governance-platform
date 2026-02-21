import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  Clock,
  Calendar,
  TrendingUp,
  TrendingDown,
  FileText,
  Shield,
  Award,
  Users,
  Truck,
  Building,
  ExternalLink,
  Eye,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  BarChart3,
  Zap,
  X,
  Plus,
  Loader2,
  Search,
  ArrowUpRight,
  Minus,
} from 'lucide-react';
import { cn } from '../helpers/utils';
import { TableSkeleton } from '../components/ui/SkeletonLoader';
import { Button } from '../components/ui/Button';
import { complianceAutomationApi } from '../api/client';
import { ToastContainer, useToast } from '../components/ui/Toast';

interface RegulatoryUpdate {
  id: number;
  source: string;
  source_reference: string;
  title: string;
  summary: string;
  category: string;
  impact: string;
  affected_standards: string[];
  affected_clauses: string[];
  published_date: string;
  effective_date: string;
  is_reviewed: boolean;
  requires_action: boolean;
}

interface Certificate {
  id: number;
  name: string;
  certificate_type: string;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  issuing_body: string;
  issue_date: string;
  expiry_date: string;
  status: string;
  is_critical: boolean;
}

interface ScheduledAudit {
  id: number;
  name: string;
  audit_type: string;
  frequency: string;
  next_due_date: string;
  status: string;
  standards: string[];
  department: string;
}

interface ComplianceScoreData {
  overall_score: number;
  previous_score: number | null;
  change: number;
  breakdown: Record<string, { score: number; clauses_compliant: number; clauses_total: number; gaps: number }>;
}

interface GapAnalysis {
  id: number;
  title: string;
  total_gaps: number;
  critical_gaps: number;
  high_gaps: number;
  estimated_effort_hours: number;
  status: string;
  gaps: Array<{
    clause: string;
    requirement: string;
    gap_description: string;
    severity: string;
    effort_hours: number;
    recommendation: string;
  }>;
  created_at: string;
}

interface RiddorSubmission {
  id: number;
  incident_id: number;
  riddor_type: string;
  submission_status: string;
  hse_reference: string | null;
  deadline: string;
  submitted_at: string | null;
  created_at: string;
}

interface ExpiringSummary {
  expired: number;
  expiring_7_days: number;
  expiring_30_days: number;
  expiring_90_days: number;
  total_critical: number;
}

type TabId = 'regulatory' | 'certificates' | 'audits' | 'scoring' | 'riddor';

const impactColors: Record<string, string> = {
  critical: 'bg-destructive/15 text-destructive border-destructive/25',
  high: 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/25',
  medium: 'bg-warning/15 text-warning-foreground border-warning/25',
  low: 'bg-success/15 text-success border-success/25',
  informational: 'bg-info/15 text-info border-info/25',
};

const statusColors: Record<string, string> = {
  valid: 'bg-success/10 text-success',
  expiring_soon: 'bg-warning/10 text-warning',
  expired: 'bg-destructive/10 text-destructive',
  scheduled: 'bg-info/10 text-info',
  overdue: 'bg-destructive/10 text-destructive',
};

const EMPTY_CERT_FORM = {
  name: '',
  certificate_type: 'training',
  entity_type: 'user',
  entity_id: '',
  entity_name: '',
  issuing_body: '',
  issue_date: '',
  expiry_date: '',
  is_critical: false,
};

const EMPTY_AUDIT_FORM = {
  name: '',
  audit_type: 'internal_audit',
  frequency: 'monthly',
  next_due_date: '',
  description: '',
  department: '',
  standard_ids: '' as string,
};

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function ComplianceAutomation() {
  const [activeTab, setActiveTab] = useState<TabId>('regulatory');
  const [updates, setUpdates] = useState<RegulatoryUpdate[]>([]);
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [audits, setAudits] = useState<ScheduledAudit[]>([]);
  const [gapAnalyses, setGapAnalyses] = useState<GapAnalysis[]>([]);
  const [riddorSubmissions, setRiddorSubmissions] = useState<RiddorSubmission[]>([]);
  const [expiringSummary, setExpiringSummary] = useState<ExpiringSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [complianceScore, setComplianceScore] = useState<ComplianceScoreData>({
    overall_score: 0,
    previous_score: null,
    change: 0,
    breakdown: {},
  });

  const [showCertModal, setShowCertModal] = useState(false);
  const [certForm, setCertForm] = useState(EMPTY_CERT_FORM);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [auditForm, setAuditForm] = useState(EMPTY_AUDIT_FORM);
  const [expandedGapId, setExpandedGapId] = useState<number | null>(null);
  const [certDetailId, setCertDetailId] = useState<number | null>(null);

  const { toasts, show: showToast, dismiss: dismissToast } = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [updatesRes, certsRes, auditsRes, scoreRes, gapRes, riddorRes, expiringRes] = await Promise.allSettled([
        complianceAutomationApi.listRegulatoryUpdates(),
        complianceAutomationApi.listCertificates(),
        complianceAutomationApi.listScheduledAudits(),
        complianceAutomationApi.getComplianceScore(),
        complianceAutomationApi.listGapAnalyses(),
        complianceAutomationApi.listRiddorSubmissions(),
        complianceAutomationApi.getExpiringCertificates(),
      ]);

      if (updatesRes.status === 'fulfilled') {
        setUpdates((updatesRes.value.data as Record<string, unknown>)['updates'] as typeof updates ?? []);
      }
      if (certsRes.status === 'fulfilled') {
        setCertificates((certsRes.value.data as Record<string, unknown>)['certificates'] as typeof certificates ?? []);
      }
      if (auditsRes.status === 'fulfilled') {
        setAudits((auditsRes.value.data as Record<string, unknown>)['audits'] as typeof audits ?? []);
      }
      if (scoreRes.status === 'fulfilled') {
        const s = scoreRes.value.data as unknown as ComplianceScoreData;
        setComplianceScore({
          overall_score: s.overall_score ?? 0,
          previous_score: s.previous_score ?? null,
          change: s.change ?? 0,
          breakdown: s.breakdown ?? {},
        });
      }
      if (gapRes.status === 'fulfilled') {
        setGapAnalyses((gapRes.value.data as Record<string, unknown>)['analyses'] as typeof gapAnalyses ?? []);
      }
      if (riddorRes.status === 'fulfilled') {
        setRiddorSubmissions((riddorRes.value.data as Record<string, unknown>)['submissions'] as typeof riddorSubmissions ?? []);
      }
      if (expiringRes.status === 'fulfilled') {
        setExpiringSummary(expiringRes.value.data as ExpiringSummary);
      }
    } catch (err) {
      console.error('Failed to load compliance data', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleMarkReviewed = async (updateId: number) => {
    setActionLoading(`review-${updateId}`);
    try {
      await complianceAutomationApi.reviewUpdate(updateId);
      setUpdates(prev => prev.map(u => u.id === updateId ? { ...u, is_reviewed: true } : u));
      showToast('Regulatory update marked as reviewed', 'success');
    } catch (err) {
      showToast('Failed to mark update as reviewed', 'error');
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRunGapAnalysis = async (regulatoryUpdateId?: number) => {
    setActionLoading(`gap-${regulatoryUpdateId ?? 'new'}`);
    try {
      await complianceAutomationApi.runGapAnalysis(
        regulatoryUpdateId ? { regulatory_update_id: regulatoryUpdateId } : undefined
      );
      showToast('Gap analysis completed successfully', 'success');
      const gapRes = await complianceAutomationApi.listGapAnalyses();
      setGapAnalyses((gapRes.data as Record<string, unknown>)['analyses'] as typeof gapAnalyses ?? []);
    } catch (err) {
      showToast('Failed to run gap analysis', 'error');
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddCertificate = async () => {
    if (!certForm.name || !certForm.issue_date || !certForm.expiry_date || !certForm.entity_id) return;
    setActionLoading('add-cert');
    try {
      await complianceAutomationApi.addCertificate({ ...certForm });
      setShowCertModal(false);
      setCertForm(EMPTY_CERT_FORM);
      showToast('Certificate added successfully', 'success');
      const [certsRes, expiringRes] = await Promise.allSettled([
        complianceAutomationApi.listCertificates(),
        complianceAutomationApi.getExpiringCertificates(),
      ]);
      if (certsRes.status === 'fulfilled') setCertificates((certsRes.value.data as Record<string, unknown>)['certificates'] as typeof certificates ?? []);
      if (expiringRes.status === 'fulfilled') setExpiringSummary(expiringRes.value.data as ExpiringSummary);
    } catch (err) {
      showToast('Failed to add certificate', 'error');
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleScheduleAudit = async () => {
    if (!auditForm.name || !auditForm.next_due_date) return;
    setActionLoading('schedule-audit');
    try {
      await complianceAutomationApi.scheduleAudit({
        name: auditForm.name,
        audit_type: auditForm.audit_type,
        frequency: auditForm.frequency,
        next_due_date: auditForm.next_due_date,
        description: auditForm.description || undefined,
        department: auditForm.department || undefined,
        standard_ids: auditForm.standard_ids ? auditForm.standard_ids.split(',').map(s => s.trim()) : undefined,
      });
      setShowAuditModal(false);
      setAuditForm(EMPTY_AUDIT_FORM);
      showToast('Audit scheduled successfully', 'success');
      const res = await complianceAutomationApi.listScheduledAudits();
      setAudits((res.data as Record<string, unknown>)['audits'] as typeof audits ?? []);
    } catch (err) {
      showToast('Failed to schedule audit', 'error');
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  const pendingRiddor = useMemo(() =>
    riddorSubmissions.filter(s => s.submission_status !== 'submitted'),
    [riddorSubmissions]
  );

  const tabs = useMemo(() => [
    { id: 'regulatory' as TabId, label: 'Regulatory Updates', icon: Bell, count: updates.filter(u => !u.is_reviewed).length },
    { id: 'certificates' as TabId, label: 'Certificates', icon: Award, count: certificates.filter(c => c.status === 'expiring_soon' || c.status === 'expired').length },
    { id: 'audits' as TabId, label: 'Scheduled Audits', icon: Calendar, count: audits.filter(a => a.status === 'overdue').length },
    { id: 'scoring' as TabId, label: 'Compliance Score', icon: BarChart3 },
    { id: 'riddor' as TabId, label: 'RIDDOR', icon: FileText, count: pendingRiddor.length },
  ], [updates, certificates, audits, pendingRiddor]);

  const scoreChange = complianceScore.change ?? 0;

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="h-8 w-64 rounded bg-muted animate-pulse" />
        <TableSkeleton rows={6} columns={4} />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Compliance Automation</h1>
          <p className="text-muted-foreground mt-1">Monitor regulations, track certificates, and automate compliance</p>
        </div>
        <Button onClick={loadData} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Score Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Overall Score */}
        <div className="bg-gradient-to-br from-primary to-primary-hover rounded-xl p-5 text-primary-foreground relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-8 translate-x-8" />
          <div className="relative">
            <div className="flex items-center justify-between mb-3">
              <Shield className="w-7 h-7 opacity-80" />
              <span className={cn(
                'flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full',
                scoreChange > 0 ? 'bg-white/20' : scoreChange < 0 ? 'bg-destructive/40' : 'bg-white/10'
              )}>
                {scoreChange > 0 ? <TrendingUp className="w-3.5 h-3.5" /> :
                 scoreChange < 0 ? <TrendingDown className="w-3.5 h-3.5" /> :
                 <Minus className="w-3.5 h-3.5" />}
                {scoreChange > 0 ? '+' : ''}{scoreChange.toFixed(1)}%
              </span>
            </div>
            <div className="text-4xl font-bold mb-0.5">{complianceScore.overall_score.toFixed(1)}%</div>
            <div className="text-primary-foreground/70 text-sm">Overall Compliance Score</div>
          </div>
        </div>

        {/* Regulatory Updates */}
        <button
          onClick={() => setActiveTab('regulatory')}
          className={cn(
            'bg-card border rounded-xl p-4 text-left transition-all hover:shadow-md',
            activeTab === 'regulatory' ? 'border-primary/50 ring-1 ring-primary/20' : 'border-border'
          )}
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-destructive/10">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <span className="text-muted-foreground text-sm">Regulatory Updates</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{updates.filter(u => !u.is_reviewed).length}</div>
          <div className="text-sm text-muted-foreground">Pending review</div>
        </button>

        {/* Expiring Certificates */}
        <button
          onClick={() => setActiveTab('certificates')}
          className={cn(
            'bg-card border rounded-xl p-4 text-left transition-all hover:shadow-md',
            activeTab === 'certificates' ? 'border-primary/50 ring-1 ring-primary/20' : 'border-border'
          )}
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-warning/10">
              <Clock className="w-5 h-5 text-warning" />
            </div>
            <span className="text-muted-foreground text-sm">Expiring Certificates</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {expiringSummary ? expiringSummary.expiring_90_days : certificates.filter(c => c.status === 'expiring_soon').length}
          </div>
          <div className="text-sm text-muted-foreground">
            {expiringSummary ? `${expiringSummary.expired} expired · ${expiringSummary.total_critical} critical` : 'Within 90 days'}
          </div>
        </button>

        {/* Overdue Audits */}
        <button
          onClick={() => setActiveTab('audits')}
          className={cn(
            'bg-card border rounded-xl p-4 text-left transition-all hover:shadow-md',
            activeTab === 'audits' ? 'border-primary/50 ring-1 ring-primary/20' : 'border-border'
          )}
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-orange-500/10">
              <Calendar className="w-5 h-5 text-orange-500" />
            </div>
            <span className="text-muted-foreground text-sm">Overdue Audits</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{audits.filter(a => a.status === 'overdue').length}</div>
          <div className="text-sm text-muted-foreground">Require attention</div>
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-card p-1.5 rounded-xl overflow-x-auto border border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className={cn(
                'px-1.5 py-0.5 rounded-full text-xs font-semibold min-w-[20px] text-center',
                activeTab === tab.id ? 'bg-white/20' : 'bg-destructive/15 text-destructive'
              )}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ============================================================ */}
      {/* REGULATORY UPDATES TAB */}
      {/* ============================================================ */}
      {activeTab === 'regulatory' && (
        <div className="space-y-4">
          {updates.length === 0 && (
            <div className="bg-card border border-border rounded-xl p-12 text-center">
              <CheckCircle className="w-12 h-12 text-success mx-auto mb-4" />
              <p className="text-foreground font-medium">All caught up</p>
              <p className="text-muted-foreground text-sm mt-1">No regulatory updates require your attention.</p>
            </div>
          )}
          {updates.map(update => (
            <div
              key={update.id}
              className={cn(
                'bg-card border rounded-xl p-5 transition-all',
                update.is_reviewed ? 'border-border opacity-75' : 'border-warning/30 shadow-sm'
              )}
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span className={cn('px-2.5 py-1 rounded-md text-xs font-semibold border', impactColors[update.impact])}>
                      {update.impact.toUpperCase()}
                    </span>
                    <span className="px-2.5 py-1 bg-muted rounded-md text-xs font-medium text-muted-foreground">
                      {update.source.replace('_', ' ').toUpperCase()}
                    </span>
                    <span className="text-muted-foreground text-xs">{update.source_reference}</span>
                    {!update.is_reviewed && (
                      <span className="px-2 py-0.5 bg-warning/15 text-warning rounded-md text-xs font-semibold">
                        NEW
                      </span>
                    )}
                    {update.is_reviewed && (
                      <span className="px-2 py-0.5 bg-success/10 text-success rounded-md text-xs font-medium flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" /> Reviewed
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold text-foreground mb-1">{update.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{update.summary}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Published: {formatDate(update.published_date)}</span>
                  {update.effective_date && (
                    <span>Effective: {formatDate(update.effective_date)}</span>
                  )}
                  {update.affected_standards?.length > 0 && (
                    <span className="text-foreground/70">
                      Affects: {update.affected_standards.join(', ')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRunGapAnalysis(update.id)}
                    disabled={!!actionLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-info/10 hover:bg-info/20 text-info rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {actionLoading === `gap-${update.id}` ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Zap className="w-3.5 h-3.5" />
                    )}
                    {actionLoading === `gap-${update.id}` ? 'Analysing...' : 'Run Gap Analysis'}
                  </button>
                  {!update.is_reviewed && (
                    <button
                      onClick={() => handleMarkReviewed(update.id)}
                      disabled={!!actionLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      {actionLoading === `review-${update.id}` ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <CheckCircle className="w-3.5 h-3.5" />
                      )}
                      Mark Reviewed
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Gap Analysis Results */}
          {gapAnalyses.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <Search className="w-5 h-5 text-info" />
                Gap Analysis History
              </h3>
              <div className="space-y-3">
                {gapAnalyses.map(ga => (
                  <div key={ga.id} className="bg-card border border-border rounded-xl overflow-hidden">
                    <button
                      onClick={() => setExpandedGapId(expandedGapId === ga.id ? null : ga.id)}
                      className="w-full p-4 flex items-center justify-between text-left hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-lg bg-info/10">
                          <Zap className="w-4 h-4 text-info" />
                        </div>
                        <div className="min-w-0">
                          <h4 className="font-medium text-foreground truncate">{ga.title}</h4>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {formatDate(ga.created_at)} · {ga.total_gaps} gap{ga.total_gaps !== 1 ? 's' : ''}
                            {ga.critical_gaps > 0 && ` · ${ga.critical_gaps} critical`}
                            {ga.high_gaps > 0 && ` · ${ga.high_gaps} high`}
                            {` · ~${ga.estimated_effort_hours}h effort`}
                          </p>
                        </div>
                      </div>
                      <ChevronRight className={cn(
                        'w-4 h-4 text-muted-foreground transition-transform shrink-0 ml-2',
                        expandedGapId === ga.id && 'rotate-90'
                      )} />
                    </button>
                    {expandedGapId === ga.id && ga.gaps && (
                      <div className="border-t border-border p-4 space-y-3 bg-muted/20">
                        {(Array.isArray(ga.gaps) ? ga.gaps : []).map((gap, idx) => (
                          <div key={idx} className="p-3 bg-card rounded-lg border border-border">
                            <div className="flex items-center gap-2 mb-1.5">
                              <span className={cn(
                                'px-2 py-0.5 rounded text-xs font-semibold',
                                gap.severity === 'critical' ? 'bg-destructive/15 text-destructive' :
                                gap.severity === 'high' ? 'bg-orange-500/15 text-orange-500' :
                                'bg-warning/15 text-warning'
                              )}>
                                {gap.severity.toUpperCase()}
                              </span>
                              <span className="text-xs font-medium text-foreground">Clause {gap.clause}</span>
                            </div>
                            <p className="text-sm text-foreground mb-1">{gap.gap_description}</p>
                            <p className="text-xs text-muted-foreground">
                              <span className="font-medium">Recommendation:</span> {gap.recommendation}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* CERTIFICATES TAB */}
      {/* ============================================================ */}
      {activeTab === 'certificates' && (
        <div className="space-y-4">
          {/* Expiring Summary Bar */}
          {expiringSummary && (expiringSummary.expired > 0 || expiringSummary.expiring_7_days > 0 || expiringSummary.total_critical > 0) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-destructive">{expiringSummary.expired}</div>
                <div className="text-xs text-destructive/80">Expired</div>
              </div>
              <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-orange-500">{expiringSummary.expiring_7_days}</div>
                <div className="text-xs text-orange-500/80">Within 7 days</div>
              </div>
              <div className="bg-warning/10 border border-warning/20 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-warning">{expiringSummary.expiring_30_days}</div>
                <div className="text-xs text-warning/80">Within 30 days</div>
              </div>
              <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-destructive">{expiringSummary.total_critical}</div>
                <div className="text-xs text-destructive/80">Critical expiring</div>
              </div>
            </div>
          )}

          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h3 className="font-semibold text-foreground">Certificate Expiry Tracking</h3>
              <button
                onClick={() => setShowCertModal(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg text-sm font-medium transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Certificate
              </button>
            </div>
            {certificates.length === 0 ? (
              <div className="p-12 text-center">
                <Award className="w-12 h-12 text-muted-foreground/40 mx-auto mb-4" />
                <p className="text-foreground font-medium">No certificates tracked</p>
                <p className="text-muted-foreground text-sm mt-1">Add certificates to track their expiry dates.</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {certificates.map(cert => {
                  const daysLeft = daysUntil(cert.expiry_date);
                  const isExpanded = certDetailId === cert.id;
                  return (
                    <div key={cert.id} className={cn(
                      'transition-colors',
                      daysLeft < 0 ? 'bg-destructive/5' : daysLeft < 30 ? 'bg-warning/5' : ''
                    )}>
                      <div className="p-4 flex items-center justify-between">
                        <div className="flex items-center gap-4 min-w-0">
                          <div className={cn(
                            'p-2 rounded-lg shrink-0',
                            cert.entity_type === 'user' ? 'bg-info/10' :
                            cert.entity_type === 'equipment' ? 'bg-purple-500/10' : 'bg-success/10'
                          )}>
                            {cert.entity_type === 'user' ? <Users className="w-5 h-5 text-info" /> :
                             cert.entity_type === 'equipment' ? <Truck className="w-5 h-5 text-purple-500" /> :
                             <Building className="w-5 h-5 text-success" />}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="font-medium text-foreground truncate">{cert.name}</h4>
                              {cert.is_critical && (
                                <span className="px-1.5 py-0.5 bg-destructive/15 text-destructive rounded text-xs font-semibold shrink-0">
                                  Critical
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground truncate">
                              {cert.entity_name}{cert.issuing_body ? ` · ${cert.issuing_body}` : ''}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0 ml-4">
                          <div className="text-right">
                            <span className={cn('px-2.5 py-1 rounded-md text-xs font-semibold', statusColors[cert.status] || 'bg-muted text-muted-foreground')}>
                              {cert.status.replace('_', ' ').toUpperCase()}
                            </span>
                            <p className="text-xs text-muted-foreground mt-1.5">
                              {daysLeft < 0
                                ? `Expired ${Math.abs(daysLeft)} days ago`
                                : daysLeft === 0
                                  ? 'Expires today'
                                  : `${daysLeft} day${daysLeft !== 1 ? 's' : ''} remaining`
                              }
                            </p>
                          </div>
                          <button
                            onClick={() => setCertDetailId(isExpanded ? null : cert.id)}
                            className={cn(
                              'p-2 rounded-lg transition-colors',
                              isExpanded ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                            )}
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                      {isExpanded && (
                        <div className="px-4 pb-4">
                          <div className="bg-muted/30 rounded-lg p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                            <div>
                              <div className="text-muted-foreground text-xs mb-1">Type</div>
                              <div className="text-foreground font-medium capitalize">{cert.certificate_type}</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground text-xs mb-1">Entity ID</div>
                              <div className="text-foreground font-medium">{cert.entity_id}</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground text-xs mb-1">Issued</div>
                              <div className="text-foreground font-medium">{formatDate(cert.issue_date)}</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground text-xs mb-1">Expires</div>
                              <div className={cn('font-medium', daysLeft < 0 ? 'text-destructive' : daysLeft < 30 ? 'text-warning' : 'text-foreground')}>
                                {formatDate(cert.expiry_date)}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* SCHEDULED AUDITS TAB */}
      {/* ============================================================ */}
      {activeTab === 'audits' && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-semibold text-foreground">Scheduled Audits & Inspections</h3>
            <button
              onClick={() => setShowAuditModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              Schedule Audit
            </button>
          </div>
          {audits.length === 0 ? (
            <div className="p-12 text-center">
              <Calendar className="w-12 h-12 text-muted-foreground/40 mx-auto mb-4" />
              <p className="text-foreground font-medium">No scheduled audits</p>
              <p className="text-muted-foreground text-sm mt-1">Schedule your first audit to get started.</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {audits.map(audit => {
                const daysLeft = daysUntil(audit.next_due_date);
                return (
                  <div key={audit.id} className={cn(
                    'p-4 transition-colors',
                    audit.status === 'overdue' ? 'bg-destructive/5' : 'hover:bg-muted/30'
                  )}>
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <h4 className="font-medium text-foreground">{audit.name}</h4>
                          <span className={cn('px-2 py-0.5 rounded-md text-xs font-semibold', statusColors[audit.status] || 'bg-muted text-muted-foreground')}>
                            {audit.status.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          <span className="capitalize">{audit.frequency}</span>
                          {audit.department && ` · ${audit.department}`}
                          {audit.standards?.length > 0 && ` · ${audit.standards.join(', ')}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-right">
                          <p className={cn(
                            'text-sm font-medium',
                            daysLeft < 0 ? 'text-destructive' : daysLeft < 7 ? 'text-warning' : 'text-foreground'
                          )}>
                            {daysLeft < 0
                              ? `Overdue by ${Math.abs(daysLeft)} day${Math.abs(daysLeft) !== 1 ? 's' : ''}`
                              : `Due in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}`
                            }
                          </p>
                          <p className="text-xs text-muted-foreground">{formatDate(audit.next_due_date)}</p>
                        </div>
                        <button
                          onClick={() => showToast(`Audit "${audit.name}" would launch in the Audit Builder`, 'info')}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg text-xs font-medium transition-colors"
                        >
                          <ArrowUpRight className="w-3.5 h-3.5" />
                          Start
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* COMPLIANCE SCORING TAB */}
      {/* ============================================================ */}
      {activeTab === 'scoring' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Score Breakdown */}
          <div className="bg-card border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground mb-4">Score Breakdown by Standard</h3>
            <div className="space-y-5">
              {Object.entries(complianceScore.breakdown).length > 0 ? (
                Object.entries(complianceScore.breakdown).map(([name, data]) => {
                  const barColor = data.score >= 90 ? 'bg-success' : data.score >= 75 ? 'bg-warning' : 'bg-destructive';
                  return (
                    <div key={name}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-foreground font-medium text-sm">{name}</span>
                        <span className={cn(
                          'text-sm font-bold',
                          data.score >= 90 ? 'text-success' : data.score >= 75 ? 'text-warning' : 'text-destructive'
                        )}>
                          {data.score}%
                        </span>
                      </div>
                      <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full transition-all duration-500', barColor)}
                          style={{ width: `${data.score}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1.5">
                        {data.clauses_compliant}/{data.clauses_total} clauses compliant · {data.gaps} gap{data.gaps !== 1 ? 's' : ''} identified
                      </p>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-8">
                  <BarChart3 className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-muted-foreground text-sm">No score data available yet.</p>
                </div>
              )}
            </div>
          </div>

          {/* Key Gaps & Actions */}
          <div className="space-y-6">
            <div className="bg-card border border-border rounded-xl p-6">
              <h3 className="font-semibold text-foreground mb-4">Key Gaps</h3>
              <div className="space-y-2.5">
                {Object.entries(complianceScore.breakdown)
                  .filter(([, d]) => d.gaps > 0)
                  .sort(([, a], [, b]) => b.gaps - a.gaps)
                  .map(([standard, data]) => (
                    <div key={standard} className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg border border-border/50">
                      <AlertCircle className={cn(
                        'w-5 h-5 shrink-0',
                        data.gaps >= 5 ? 'text-destructive' : 'text-warning'
                      )} />
                      <div className="flex-1 min-w-0">
                        <p className="text-foreground text-sm font-medium">{data.gaps} gap{data.gaps !== 1 ? 's' : ''} identified</p>
                        <p className="text-muted-foreground text-xs">{standard} · {data.clauses_total - data.clauses_compliant} clauses non-compliant</p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                    </div>
                  ))}
                {Object.entries(complianceScore.breakdown).filter(([, d]) => d.gaps > 0).length === 0 && (
                  <div className="p-6 text-center">
                    <CheckCircle className="w-8 h-8 text-success mx-auto mb-2" />
                    <p className="text-muted-foreground text-sm">No compliance gaps identified</p>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-card border border-border rounded-xl p-6">
              <h3 className="font-semibold text-foreground mb-3">Quick Actions</h3>
              <div className="space-y-2">
                <button
                  onClick={() => handleRunGapAnalysis()}
                  disabled={!!actionLoading}
                  className="w-full flex items-center gap-3 p-3 rounded-lg text-left bg-muted/30 hover:bg-muted/50 border border-border/50 transition-colors disabled:opacity-50"
                >
                  {actionLoading === 'gap-new' ? (
                    <Loader2 className="w-5 h-5 text-info animate-spin shrink-0" />
                  ) : (
                    <Zap className="w-5 h-5 text-info shrink-0" />
                  )}
                  <div>
                    <p className="text-foreground text-sm font-medium">Run Full Gap Analysis</p>
                    <p className="text-muted-foreground text-xs">Assess compliance across all overdue audits</p>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* RIDDOR TAB */}
      {/* ============================================================ */}
      {activeTab === 'riddor' && (
        <div className="space-y-6">
          {/* Info Banner */}
          <div className="bg-gradient-to-r from-destructive/10 to-orange-500/10 border border-destructive/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-destructive/15 rounded-lg shrink-0">
                <FileText className="w-6 h-6 text-destructive" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-foreground mb-1">RIDDOR Automation</h3>
                <p className="text-muted-foreground text-sm mb-4">
                  Automatically detect reportable incidents and prepare RIDDOR submissions to the Health & Safety Executive.
                </p>
                <a
                  href="https://www.hse.gov.uk/riddor/report.htm"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-destructive hover:bg-destructive/90 text-destructive-foreground rounded-lg text-sm font-medium transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                  HSE RIDDOR Portal
                </a>
              </div>
            </div>
          </div>

          {/* Pending Submissions */}
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border">
              <h3 className="font-semibold text-foreground">RIDDOR Submissions</h3>
            </div>
            {riddorSubmissions.length === 0 ? (
              <div className="p-12 text-center">
                <CheckCircle className="w-12 h-12 text-success mx-auto mb-4" />
                <p className="text-foreground font-medium">No RIDDOR submissions</p>
                <p className="text-muted-foreground text-sm mt-1">
                  Reportable incidents will appear here automatically when detected.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {riddorSubmissions.map(sub => {
                  const deadlineDays = daysUntil(sub.deadline);
                  return (
                    <div key={sub.id} className={cn(
                      'p-4',
                      sub.submission_status !== 'submitted' && deadlineDays < 3 ? 'bg-destructive/5' : ''
                    )}>
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-foreground capitalize">{sub.riddor_type.replace(/_/g, ' ')}</span>
                            <span className={cn(
                              'px-2 py-0.5 rounded-md text-xs font-semibold',
                              sub.submission_status === 'submitted' ? 'bg-success/10 text-success' :
                              sub.submission_status === 'ready_to_submit' ? 'bg-warning/10 text-warning' :
                              'bg-muted text-muted-foreground'
                            )}>
                              {sub.submission_status.replace(/_/g, ' ').toUpperCase()}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Incident #{sub.incident_id}
                            {sub.hse_reference && ` · HSE Ref: ${sub.hse_reference}`}
                            {sub.submitted_at && ` · Submitted: ${formatDate(sub.submitted_at)}`}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          {sub.submission_status !== 'submitted' ? (
                            <p className={cn(
                              'text-sm font-medium',
                              deadlineDays < 3 ? 'text-destructive' : 'text-warning'
                            )}>
                              Deadline: {deadlineDays < 0
                                ? `${Math.abs(deadlineDays)} days overdue`
                                : `${deadlineDays} day${deadlineDays !== 1 ? 's' : ''} left`
                              }
                            </p>
                          ) : (
                            <span className="text-sm text-success font-medium">Submitted</span>
                          )}
                          <p className="text-xs text-muted-foreground">{formatDate(sub.deadline)}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* ADD CERTIFICATE MODAL */}
      {/* ============================================================ */}
      {showCertModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setShowCertModal(false)}>
          <div className="bg-card border border-border rounded-xl w-full max-w-lg shadow-lg animate-scale-in" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h3 className="font-semibold text-foreground text-lg">Add Certificate</h3>
              <button onClick={() => setShowCertModal(false)} className="text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-muted transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Certificate Name *</label>
                <input
                  value={certForm.name}
                  onChange={e => setCertForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  placeholder="e.g. First Aid at Work"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Type</label>
                  <select
                    value={certForm.certificate_type}
                    onChange={e => setCertForm(f => ({ ...f, certificate_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  >
                    <option value="training">Training</option>
                    <option value="equipment">Equipment</option>
                    <option value="competency">Competency</option>
                    <option value="license">License</option>
                    <option value="accreditation">Accreditation</option>
                    <option value="calibration">Calibration</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Entity Type</label>
                  <select
                    value={certForm.entity_type}
                    onChange={e => setCertForm(f => ({ ...f, entity_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  >
                    <option value="user">Person</option>
                    <option value="equipment">Equipment</option>
                    <option value="organization">Organisation</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Entity ID *</label>
                  <input
                    value={certForm.entity_id}
                    onChange={e => setCertForm(f => ({ ...f, entity_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                    placeholder="e.g. user-001"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Entity Name</label>
                  <input
                    value={certForm.entity_name}
                    onChange={e => setCertForm(f => ({ ...f, entity_name: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                    placeholder="e.g. John Smith"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Issuing Body</label>
                <input
                  value={certForm.issuing_body}
                  onChange={e => setCertForm(f => ({ ...f, issuing_body: e.target.value }))}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  placeholder="e.g. St John Ambulance"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Issue Date *</label>
                  <input
                    type="date"
                    value={certForm.issue_date}
                    onChange={e => setCertForm(f => ({ ...f, issue_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Expiry Date *</label>
                  <input
                    type="date"
                    value={certForm.expiry_date}
                    onChange={e => setCertForm(f => ({ ...f, expiry_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_critical"
                  checked={certForm.is_critical}
                  onChange={e => setCertForm(f => ({ ...f, is_critical: e.target.checked }))}
                  className="rounded border-border"
                />
                <label htmlFor="is_critical" className="text-sm text-foreground">Critical certificate</label>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-5 border-t border-border">
              <button
                onClick={() => setShowCertModal(false)}
                className="px-4 py-2 text-muted-foreground hover:text-foreground text-sm font-medium rounded-lg hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddCertificate}
                disabled={actionLoading === 'add-cert' || !certForm.name || !certForm.issue_date || !certForm.expiry_date || !certForm.entity_id}
                className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {actionLoading === 'add-cert' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                {actionLoading === 'add-cert' ? 'Adding...' : 'Add Certificate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* SCHEDULE AUDIT MODAL */}
      {/* ============================================================ */}
      {showAuditModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setShowAuditModal(false)}>
          <div className="bg-card border border-border rounded-xl w-full max-w-lg shadow-lg animate-scale-in" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h3 className="font-semibold text-foreground text-lg">Schedule Audit</h3>
              <button onClick={() => setShowAuditModal(false)} className="text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-muted transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Audit Name *</label>
                <input
                  value={auditForm.name}
                  onChange={e => setAuditForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  placeholder="e.g. Monthly H&S Inspection"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Description</label>
                <input
                  value={auditForm.description}
                  onChange={e => setAuditForm(f => ({ ...f, description: e.target.value }))}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  placeholder="Optional description"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Audit Type</label>
                  <select
                    value={auditForm.audit_type}
                    onChange={e => setAuditForm(f => ({ ...f, audit_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  >
                    <option value="internal_audit">Internal Audit</option>
                    <option value="safety_inspection">Safety Inspection</option>
                    <option value="environmental_audit">Environmental Audit</option>
                    <option value="supplier_audit">Supplier Audit</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Frequency</label>
                  <select
                    value={auditForm.frequency}
                    onChange={e => setAuditForm(f => ({ ...f, frequency: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  >
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="annual">Annual</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Next Due Date *</label>
                  <input
                    type="date"
                    value={auditForm.next_due_date}
                    onChange={e => setAuditForm(f => ({ ...f, next_due_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Department</label>
                  <input
                    value={auditForm.department}
                    onChange={e => setAuditForm(f => ({ ...f, department: e.target.value }))}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                    placeholder="e.g. Safety Team"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Standards (comma-separated)</label>
                <input
                  value={auditForm.standard_ids}
                  onChange={e => setAuditForm(f => ({ ...f, standard_ids: e.target.value }))}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all"
                  placeholder="e.g. ISO 9001, ISO 45001"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 p-5 border-t border-border">
              <button
                onClick={() => setShowAuditModal(false)}
                className="px-4 py-2 text-muted-foreground hover:text-foreground text-sm font-medium rounded-lg hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleScheduleAudit}
                disabled={actionLoading === 'schedule-audit' || !auditForm.name || !auditForm.next_due_date}
                className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {actionLoading === 'schedule-audit' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Calendar className="w-4 h-4" />
                )}
                {actionLoading === 'schedule-audit' ? 'Scheduling...' : 'Schedule Audit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
