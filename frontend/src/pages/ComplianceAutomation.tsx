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

import { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { cn } from '../helpers/utils';
import { Button } from '../components/ui/Button';

interface RegulatoryUpdate {
  id: number;
  source: string;
  source_reference: string;
  title: string;
  summary: string;
  category: string;
  impact: string;
  affected_standards: string[];
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
  entity_name: string;
  issuing_body: string;
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
}

const impactColors: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
  informational: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

const statusColors: Record<string, string> = {
  valid: 'bg-emerald-500/20 text-emerald-400',
  expiring_soon: 'bg-yellow-500/20 text-yellow-400',
  expired: 'bg-red-500/20 text-red-400',
  scheduled: 'bg-blue-500/20 text-blue-400',
  overdue: 'bg-red-500/20 text-red-400',
};

export default function ComplianceAutomation() {
  const [activeTab, setActiveTab] = useState<'regulatory' | 'certificates' | 'audits' | 'scoring' | 'riddor'>('regulatory');
  const [updates, setUpdates] = useState<RegulatoryUpdate[]>([]);
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [audits, setAudits] = useState<ScheduledAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [complianceScore] = useState({
    overall: 87.5,
    previous: 85.2,
    change: 2.3,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    await new Promise(resolve => setTimeout(resolve, 500));

    setUpdates([
      {
        id: 1,
        source: 'hse_uk',
        source_reference: 'HSE/2026/001',
        title: 'Updated guidance on workplace first aid requirements',
        summary: 'New requirements for first aid training and equipment in workplaces with 50+ employees.',
        category: 'health_safety',
        impact: 'high',
        affected_standards: ['ISO 45001'],
        published_date: '2026-01-15',
        effective_date: '2026-04-01',
        is_reviewed: false,
        requires_action: true,
      },
      {
        id: 2,
        source: 'iso',
        source_reference: 'ISO/TC 176/2026',
        title: 'Amendment to ISO 9001:2015 - Clause 4.4.1',
        summary: 'Clarification on process interaction requirements.',
        category: 'quality',
        impact: 'medium',
        affected_standards: ['ISO 9001'],
        published_date: '2026-01-10',
        effective_date: '2026-07-01',
        is_reviewed: true,
        requires_action: false,
      },
      {
        id: 3,
        source: 'hse_uk',
        source_reference: 'HSE/2026/002',
        title: 'RIDDOR amendment - digital submission requirements',
        summary: 'All RIDDOR submissions must be made digitally from March 2026.',
        category: 'regulatory',
        impact: 'critical',
        affected_standards: ['ISO 45001'],
        published_date: '2026-01-18',
        effective_date: '2026-03-01',
        is_reviewed: false,
        requires_action: true,
      },
    ]);

    setCertificates([
      {
        id: 1,
        name: 'First Aid at Work Certificate',
        certificate_type: 'training',
        entity_type: 'user',
        entity_name: 'John Smith',
        issuing_body: 'St John Ambulance',
        expiry_date: '2026-03-05',
        status: 'expiring_soon',
        is_critical: true,
      },
      {
        id: 2,
        name: 'IPAF Licence',
        certificate_type: 'license',
        entity_type: 'user',
        entity_name: 'Mike Johnson',
        issuing_body: 'IPAF',
        expiry_date: '2026-07-18',
        status: 'valid',
        is_critical: false,
      },
      {
        id: 3,
        name: 'Crane Calibration Certificate',
        certificate_type: 'calibration',
        entity_type: 'equipment',
        entity_name: 'Mobile Crane MC-01',
        issuing_body: 'UKAS Accredited',
        expiry_date: '2026-01-29',
        status: 'expiring_soon',
        is_critical: true,
      },
    ]);

    setAudits([
      {
        id: 1,
        name: 'Monthly H&S Inspection - Site A',
        audit_type: 'safety_inspection',
        frequency: 'monthly',
        next_due_date: '2026-01-24',
        status: 'scheduled',
        standards: ['ISO 45001'],
      },
      {
        id: 2,
        name: 'Quarterly ISO 9001 Internal Audit',
        audit_type: 'internal_audit',
        frequency: 'quarterly',
        next_due_date: '2026-01-16',
        status: 'overdue',
        standards: ['ISO 9001'],
      },
    ]);

    setLoading(false);
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
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-500 border-t-transparent" />
      </div>
    );
  }

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
        <div className="lg:col-span-1 bg-gradient-to-br from-emerald-600 to-teal-700 rounded-xl p-6 text-white">
          <div className="flex items-center justify-between mb-4">
            <Shield className="w-8 h-8 opacity-80" />
            <span className={`flex items-center gap-1 text-sm ${complianceScore.change >= 0 ? 'text-emerald-200' : 'text-red-200'}`}>
              {complianceScore.change >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              {complianceScore.change >= 0 ? '+' : ''}{complianceScore.change}%
            </span>
          </div>
          <div className="text-4xl font-bold mb-1">{complianceScore.overall}%</div>
          <div className="text-emerald-200 text-sm">Overall Compliance Score</div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-red-500/20">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <span className="text-gray-400 text-sm">Regulatory Updates</span>
          </div>
          <div className="text-2xl font-bold text-white">{updates.filter(u => !u.is_reviewed).length}</div>
          <div className="text-sm text-gray-500">Pending review</div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-yellow-500/20">
              <Clock className="w-5 h-5 text-yellow-400" />
            </div>
            <span className="text-gray-400 text-sm">Expiring Certificates</span>
          </div>
          <div className="text-2xl font-bold text-white">{certificates.filter(c => c.status === 'expiring_soon').length}</div>
          <div className="text-sm text-gray-500">Within 60 days</div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-orange-500/20">
              <Calendar className="w-5 h-5 text-orange-400" />
            </div>
            <span className="text-gray-400 text-sm">Overdue Audits</span>
          </div>
          <div className="text-2xl font-bold text-white">{audits.filter(a => a.status === 'overdue').length}</div>
          <div className="text-sm text-gray-500">Require attention</div>
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
                  <span className="text-gray-500">
                    Effective: {new Date(update.effective_date).toLocaleDateString()}
                  </span>
                  <span className="text-gray-400">
                    Affects: {update.affected_standards.join(', ')}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button className="flex items-center gap-2 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white rounded-lg text-sm transition-colors">
                    <Zap className="w-4 h-4" />
                    Run Gap Analysis
                  </button>
                  {!update.is_reviewed && (
                    <button className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors">
                      <CheckCircle className="w-4 h-4" />
                      Mark Reviewed
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
            <button className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors">
              <Award className="w-4 h-4" />
              Add Certificate
            </button>
          </div>
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
                        {cert.entity_name} • {cert.issuing_body}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[cert.status]}`}>
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
        </div>
      )}

      {/* Scheduled Audits Tab */}
      {activeTab === 'audits' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h3 className="font-medium text-white">Scheduled Audits & Inspections</h3>
            <button className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors">
              <Calendar className="w-4 h-4" />
              Schedule Audit
            </button>
          </div>
          <div className="divide-y divide-slate-700">
            {audits.map(audit => (
              <div key={audit.id} className="p-4 hover:bg-slate-700/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-white">{audit.name}</h4>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[audit.status]}`}>
                        {audit.status.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400">
                      {audit.frequency} • {audit.standards.join(', ')}
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
        </div>
      )}

      {/* Compliance Scoring Tab */}
      {activeTab === 'scoring' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 className="font-medium text-white mb-4">Score Breakdown by Standard</h3>
            <div className="space-y-4">
              {[
                { name: 'ISO 9001', score: 92, color: 'emerald' },
                { name: 'ISO 14001', score: 88.5, color: 'blue' },
                { name: 'ISO 45001', score: 82, color: 'purple' },
              ].map(standard => (
                <div key={standard.name}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-medium">{standard.name}</span>
                    <span className="text-white">{standard.score}%</span>
                  </div>
                  <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full bg-${standard.color}-500`}
                      style={{ width: `${standard.score}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 className="font-medium text-white mb-4">Key Gaps</h3>
            <div className="space-y-3">
              {[
                { standard: 'ISO 45001', clause: '8.2', description: 'First aid training gaps' },
                { standard: 'ISO 14001', clause: '6.1', description: 'Environmental risk register outdated' },
                { standard: 'ISO 9001', clause: '10.2', description: 'NCR closure rate below target' },
              ].map((gap, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-slate-700/30 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-yellow-400" />
                  <div className="flex-1">
                    <p className="text-white text-sm">{gap.description}</p>
                    <p className="text-gray-500 text-xs">{gap.standard} Clause {gap.clause}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-500" />
                </div>
              ))}
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
                  <button className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors">
                    <ExternalLink className="w-4 h-4" />
                    HSE RIDDOR Portal
                  </button>
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
    </div>
  );
}
