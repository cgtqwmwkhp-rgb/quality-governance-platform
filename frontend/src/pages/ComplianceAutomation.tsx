/**
 * Compliance Automation Center
 * 
 * Features:
 * - Regulatory change monitoring
 * - Gap analysis
 * - Certificate expiry tracking
 * - Scheduled audits
 * - Compliance scoring
 * - RIDDOR automation
 */

import { useState, useEffect, useCallback } from 'react';
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
  Play,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  BarChart3,
  Zap,
  BookOpen,
  X,
  Plus,
} from 'lucide-react';
import { cn } from '../helpers/utils';
import { Button } from '../components/ui/Button';
import { complianceAutomationApi } from '../api/client';

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

const impactColors: Record<string, string> = {
  critical: 'bg-destructive/20 text-destructive border-destructive/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
  informational: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
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

export default function ComplianceAutomation() {
  const [activeTab, setActiveTab] = useState<'regulatory' | 'certificates' | 'audits' | 'scoring' | 'riddor'>('regulatory');
  const [updates, setUpdates] = useState<RegulatoryUpdate[]>([]);
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [audits, setAudits] = useState<ScheduledAudit[]>([]);
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

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [updatesRes, certsRes, auditsRes, scoreRes] = await Promise.allSettled([
        complianceAutomationApi.listRegulatoryUpdates(),
        complianceAutomationApi.listCertificates(),
        complianceAutomationApi.listScheduledAudits(),
        complianceAutomationApi.getComplianceScore(),
      ]);

      if (updatesRes.status === 'fulfilled') {
        setUpdates((updatesRes.value.data as any).updates ?? []);
      }
      if (certsRes.status === 'fulfilled') {
        setCertificates((certsRes.value.data as any).certificates ?? []);
      }
      if (auditsRes.status === 'fulfilled') {
        setAudits((auditsRes.value.data as any).audits ?? []);
      }
      if (scoreRes.status === 'fulfilled') {
        const s = scoreRes.value.data as any;
        setComplianceScore({
          overall_score: s.overall_score ?? 0,
          previous_score: s.previous_score ?? null,
          change: s.change ?? 0,
          breakdown: s.breakdown ?? {},
        });
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
    } catch (err) {
      console.error('Failed to mark update as reviewed', err);
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
    } catch (err) {
      console.error('Failed to run gap analysis', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddCertificate = async () => {
    if (!certForm.name || !certForm.issue_date || !certForm.expiry_date || !certForm.entity_id) return;
    setActionLoading('add-cert');
    try {
      await complianceAutomationApi.addCertificate({
        ...certForm,
      });
      setShowCertModal(false);
      setCertForm(EMPTY_CERT_FORM);
      const res = await complianceAutomationApi.listCertificates();
      setCertificates((res.data as any).certificates ?? []);
    } catch (err) {
      console.error('Failed to add certificate', err);
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
      const res = await complianceAutomationApi.listScheduledAudits();
      setAudits((res.data as any).audits ?? []);
    } catch (err) {
      console.error('Failed to schedule audit', err);
    } finally {
      setActionLoading(null);
    }
  };

  const tabs = [
    { id: 'regulatory', label: 'Regulatory Updates', icon: Bell, count: updates.filter(u => !u.is_reviewed).length },
    { id: 'certificates', label: 'Certificates', icon: Award, count: certificates.filter(c => c.status === 'expiring_soon').length },
    { id: 'audits', label: 'Scheduled Audits', icon: Calendar, count: audits.filter(a => a.status === 'overdue').length },
    { id: 'scoring', label: 'Compliance Score', icon: BarChart3 },
    { id: 'riddor', label: 'RIDDOR', icon: FileText },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const scoreChange = complianceScore.change ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Compliance Automation</h1>
          <p className="text-muted-foreground mt-1">Monitor regulations, track certificates, and automate compliance</p>
        </div>
        <Button
          onClick={loadData}
          variant="outline"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Score Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1 bg-gradient-to-br from-primary to-primary-hover rounded-xl p-6 text-primary-foreground">
          <div className="flex items-center justify-between mb-4">
            <Shield className="w-8 h-8 opacity-80" />
            <span className={`flex items-center gap-1 text-sm ${scoreChange >= 0 ? 'text-primary-foreground/80' : 'text-destructive'}`}>
              {scoreChange >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              {scoreChange >= 0 ? '+' : ''}{scoreChange}%
            </span>
          </div>
          <div className="text-4xl font-bold mb-1">{complianceScore.overall_score}%</div>
          <div className="text-primary-foreground/80 text-sm">Overall Compliance Score</div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-destructive/20">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <span className="text-muted-foreground text-sm">Regulatory Updates</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{updates.filter(u => !u.is_reviewed).length}</div>
          <div className="text-sm text-muted-foreground">Pending review</div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-warning/20">
              <Clock className="w-5 h-5 text-warning" />
            </div>
            <span className="text-muted-foreground text-sm">Expiring Certificates</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{certificates.filter(c => c.status === 'expiring_soon').length}</div>
          <div className="text-sm text-muted-foreground">Within 60 days</div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-orange-500/20">
              <Calendar className="w-5 h-5 text-orange-400" />
            </div>
            <span className="text-muted-foreground text-sm">Overdue Audits</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{audits.filter(a => a.status === 'overdue').length}</div>
          <div className="text-sm text-muted-foreground">Require attention</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-card/50 p-1 rounded-xl overflow-x-auto border border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className={cn(
                "px-2 py-0.5 rounded-full text-xs",
                activeTab === tab.id ? 'bg-white/20' : 'bg-red-500/20 text-red-400'
              )}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Regulatory Updates Tab */}
      {activeTab === 'regulatory' && (
        <div className="space-y-4">
          {updates.length === 0 && (
            <div className="bg-card/50 border border-border rounded-xl p-8 text-center">
              <CheckCircle className="w-12 h-12 text-success mx-auto mb-4" />
              <p className="text-foreground font-medium">No regulatory updates</p>
              <p className="text-muted-foreground text-sm mt-1">All caught up!</p>
            </div>
          )}
          {updates.map(update => (
            <div
              key={update.id}
              className={`bg-slate-800/50 border rounded-xl p-5 transition-colors ${
                update.is_reviewed ? 'border-slate-700' : 'border-yellow-500/30'
              }`}
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`px-2 py-1 rounded text-xs font-medium border ${impactColors[update.impact]}`}>
                      {update.impact.toUpperCase()}
                    </span>
                    <span className="px-2 py-1 bg-slate-700 rounded text-xs text-gray-300">
                      {update.source.toUpperCase()}
                    </span>
                    <span className="text-gray-500 text-xs">{update.source_reference}</span>
                    {!update.is_reviewed && (
                      <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                        NEW
                      </span>
                    )}
                  </div>
                  <h3 className="font-medium text-white mb-1">{update.title}</h3>
                  <p className="text-sm text-gray-400">{update.summary}</p>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-500">
                    Published: {new Date(update.published_date).toLocaleDateString()}
                  </span>
                  {update.effective_date && (
                    <span className="text-gray-500">
                      Effective: {new Date(update.effective_date).toLocaleDateString()}
                    </span>
                  )}
                  {update.affected_standards?.length > 0 && (
                    <span className="text-gray-400">
                      Affects: {update.affected_standards.join(', ')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRunGapAnalysis(update.id)}
                    disabled={actionLoading === `gap-${update.id}`}
                    className="flex items-center gap-2 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white rounded-lg text-sm transition-colors disabled:opacity-50"
                  >
                    <Zap className="w-4 h-4" />
                    {actionLoading === `gap-${update.id}` ? 'Running...' : 'Run Gap Analysis'}
                  </button>
                  {!update.is_reviewed && (
                    <button
                      onClick={() => handleMarkReviewed(update.id)}
                      disabled={actionLoading === `review-${update.id}`}
                      className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
                    >
                      <CheckCircle className="w-4 h-4" />
                      {actionLoading === `review-${update.id}` ? 'Saving...' : 'Mark Reviewed'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Certificates Tab */}
      {activeTab === 'certificates' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h3 className="font-medium text-white">Certificate Expiry Tracking</h3>
            <button
              onClick={() => setShowCertModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors"
            >
              <Award className="w-4 h-4" />
              Add Certificate
            </button>
          </div>
          {certificates.length === 0 ? (
            <div className="p-8 text-center">
              <Award className="w-12 h-12 text-gray-500 mx-auto mb-4" />
              <p className="text-white font-medium">No certificates tracked</p>
              <p className="text-gray-400 text-sm mt-1">Add certificates to track their expiry</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {certificates.map(cert => (
                <div key={cert.id} className="p-4 hover:bg-slate-700/30 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${
                        cert.entity_type === 'user' ? 'bg-blue-500/20' :
                        cert.entity_type === 'equipment' ? 'bg-purple-500/20' : 'bg-emerald-500/20'
                      }`}>
                        {cert.entity_type === 'user' ? <Users className="w-5 h-5 text-blue-400" /> :
                         cert.entity_type === 'equipment' ? <Truck className="w-5 h-5 text-purple-400" /> :
                         <Building className="w-5 h-5 text-emerald-400" />}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-white">{cert.name}</h4>
                          {cert.is_critical && (
                            <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">
                              Critical
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-400">
                          {cert.entity_name} {cert.issuing_body ? `\u2022 ${cert.issuing_body}` : ''}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[cert.status] || ''}`}>
                          {cert.status.replace('_', ' ').toUpperCase()}
                        </span>
                        <p className="text-sm text-gray-400 mt-1">
                          Expires: {new Date(cert.expiry_date).toLocaleDateString()}
                        </p>
                      </div>
                      <button className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-slate-700">
                        <Eye className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Scheduled Audits Tab */}
      {activeTab === 'audits' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h3 className="font-medium text-white">Scheduled Audits & Inspections</h3>
            <button
              onClick={() => setShowAuditModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors"
            >
              <Calendar className="w-4 h-4" />
              Schedule Audit
            </button>
          </div>
          {audits.length === 0 ? (
            <div className="p-8 text-center">
              <Calendar className="w-12 h-12 text-gray-500 mx-auto mb-4" />
              <p className="text-white font-medium">No scheduled audits</p>
              <p className="text-gray-400 text-sm mt-1">Schedule your first audit</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {audits.map(audit => (
                <div key={audit.id} className="p-4 hover:bg-slate-700/30 transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium text-white">{audit.name}</h4>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[audit.status] || ''}`}>
                          {audit.status.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400">
                        {audit.frequency} {audit.standards?.length ? `\u2022 ${audit.standards.join(', ')}` : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-sm text-white">Due: {new Date(audit.next_due_date).toLocaleDateString()}</p>
                      </div>
                      <button className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors">
                        <Play className="w-4 h-4" />
                        Start
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Compliance Scoring Tab */}
      {activeTab === 'scoring' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 className="font-medium text-white mb-4">Score Breakdown by Standard</h3>
            <div className="space-y-4">
              {Object.entries(complianceScore.breakdown).length > 0 ? (
                Object.entries(complianceScore.breakdown).map(([name, data]) => (
                  <div key={name}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">{name}</span>
                      <span className="text-white">{data.score}%</span>
                    </div>
                    <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-emerald-500"
                        style={{ width: `${data.score}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {data.clauses_compliant}/{data.clauses_total} clauses compliant &middot; {data.gaps} gaps
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-gray-400 text-sm">No score data available yet.</p>
              )}
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 className="font-medium text-white mb-4">Key Gaps</h3>
            <div className="space-y-3">
              {Object.entries(complianceScore.breakdown)
                .filter(([, d]) => d.gaps > 0)
                .map(([standard, data]) => (
                  <div key={standard} className="flex items-center gap-3 p-3 bg-slate-700/30 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-yellow-400" />
                    <div className="flex-1">
                      <p className="text-white text-sm">{data.gaps} gap{data.gaps !== 1 ? 's' : ''} identified</p>
                      <p className="text-gray-500 text-xs">{standard}</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-500" />
                  </div>
                ))}
              {Object.entries(complianceScore.breakdown).filter(([, d]) => d.gaps > 0).length === 0 && (
                <div className="p-4 text-center">
                  <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                  <p className="text-gray-400 text-sm">No gaps identified</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* RIDDOR Tab */}
      {activeTab === 'riddor' && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-red-600/20 to-orange-600/20 border border-red-500/30 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-red-500/20 rounded-lg">
                <FileText className="w-6 h-6 text-red-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white mb-2">RIDDOR Automation</h3>
                <p className="text-gray-300 mb-4">
                  Automatically detect reportable incidents and prepare RIDDOR submissions to the Health & Safety Executive.
                </p>
                <div className="flex items-center gap-4">
                  <a
                    href="https://www.hse.gov.uk/riddor/report.htm"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    HSE RIDDOR Portal
                  </a>
                  <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors">
                    <BookOpen className="w-4 h-4" />
                    View Guide
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-700">
              <h3 className="font-medium text-white">Pending RIDDOR Submissions</h3>
            </div>
            <div className="p-8 text-center">
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
              <p className="text-white font-medium">No pending RIDDOR submissions</p>
              <p className="text-gray-400 text-sm mt-1">All reportable incidents have been submitted</p>
            </div>
          </div>
        </div>
      )}

      {/* Add Certificate Modal */}
      {showCertModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-lg">
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
              <h3 className="font-medium text-white">Add Certificate</h3>
              <button onClick={() => setShowCertModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Certificate Name *</label>
                <input
                  value={certForm.name}
                  onChange={e => setCertForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  placeholder="e.g. First Aid at Work"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Type</label>
                  <select
                    value={certForm.certificate_type}
                    onChange={e => setCertForm(f => ({ ...f, certificate_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
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
                  <label className="block text-sm text-gray-400 mb-1">Entity Type</label>
                  <select
                    value={certForm.entity_type}
                    onChange={e => setCertForm(f => ({ ...f, entity_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  >
                    <option value="user">Person</option>
                    <option value="equipment">Equipment</option>
                    <option value="organization">Organisation</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Entity ID *</label>
                  <input
                    value={certForm.entity_id}
                    onChange={e => setCertForm(f => ({ ...f, entity_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                    placeholder="e.g. user-001"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Entity Name</label>
                  <input
                    value={certForm.entity_name}
                    onChange={e => setCertForm(f => ({ ...f, entity_name: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                    placeholder="e.g. John Smith"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Issuing Body</label>
                <input
                  value={certForm.issuing_body}
                  onChange={e => setCertForm(f => ({ ...f, issuing_body: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  placeholder="e.g. St John Ambulance"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Issue Date *</label>
                  <input
                    type="date"
                    value={certForm.issue_date}
                    onChange={e => setCertForm(f => ({ ...f, issue_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Expiry Date *</label>
                  <input
                    type="date"
                    value={certForm.expiry_date}
                    onChange={e => setCertForm(f => ({ ...f, expiry_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_critical"
                  checked={certForm.is_critical}
                  onChange={e => setCertForm(f => ({ ...f, is_critical: e.target.checked }))}
                  className="rounded border-slate-600"
                />
                <label htmlFor="is_critical" className="text-sm text-gray-400">Critical certificate</label>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-slate-700">
              <button
                onClick={() => setShowCertModal(false)}
                className="px-4 py-2 text-gray-400 hover:text-white text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleAddCertificate}
                disabled={actionLoading === 'add-cert' || !certForm.name || !certForm.issue_date || !certForm.expiry_date || !certForm.entity_id}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                {actionLoading === 'add-cert' ? 'Adding...' : 'Add Certificate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Audit Modal */}
      {showAuditModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-lg">
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
              <h3 className="font-medium text-white">Schedule Audit</h3>
              <button onClick={() => setShowAuditModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Audit Name *</label>
                <input
                  value={auditForm.name}
                  onChange={e => setAuditForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  placeholder="e.g. Monthly H&S Inspection"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Description</label>
                <input
                  value={auditForm.description}
                  onChange={e => setAuditForm(f => ({ ...f, description: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  placeholder="Optional description"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Audit Type</label>
                  <select
                    value={auditForm.audit_type}
                    onChange={e => setAuditForm(f => ({ ...f, audit_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  >
                    <option value="internal_audit">Internal Audit</option>
                    <option value="safety_inspection">Safety Inspection</option>
                    <option value="environmental_audit">Environmental Audit</option>
                    <option value="supplier_audit">Supplier Audit</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Frequency</label>
                  <select
                    value={auditForm.frequency}
                    onChange={e => setAuditForm(f => ({ ...f, frequency: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
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
                  <label className="block text-sm text-gray-400 mb-1">Next Due Date *</label>
                  <input
                    type="date"
                    value={auditForm.next_due_date}
                    onChange={e => setAuditForm(f => ({ ...f, next_due_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Department</label>
                  <input
                    value={auditForm.department}
                    onChange={e => setAuditForm(f => ({ ...f, department: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                    placeholder="e.g. Safety Team"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Standards (comma-separated)</label>
                <input
                  value={auditForm.standard_ids}
                  onChange={e => setAuditForm(f => ({ ...f, standard_ids: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                  placeholder="e.g. ISO 9001, ISO 45001"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-slate-700">
              <button
                onClick={() => setShowAuditModal(false)}
                className="px-4 py-2 text-gray-400 hover:text-white text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleScheduleAudit}
                disabled={actionLoading === 'schedule-audit' || !auditForm.name || !auditForm.next_due_date}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                <Calendar className="w-4 h-4" />
                {actionLoading === 'schedule-audit' ? 'Scheduling...' : 'Schedule Audit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
