import { useState, useEffect } from 'react'
import {
  Shield,
  Leaf,
  HardHat,
  CheckCircle2,
  AlertTriangle,
  Clock,
  TrendingUp,
  Calendar,
  Users,
  Target,
  BarChart3,
  Link2,
  ChevronRight,
  RefreshCw,
  GitMerge,
  FileText,
  ClipboardList,
  Lock,
  Server,
  ShieldCheck,
  Bug,
  Building2,
  Laptop,
  Database,
  Globe,
  UserCheck,
  Key,
  AlertOctagon,
  Award,
} from 'lucide-react'

interface Standard {
  id: string
  name: string
  version: string
  icon: React.ElementType
  color: string
  compliance: number
  findings: { major: number; minor: number; observations: number }
  lastAudit: string
  nextAudit: string
  certificateExpiry: string
}

interface CrossMapping {
  clause: string
  standards: { standard: string; clause: string; title: string }[]
  control: string
  evidence: number
}

interface ISMSDashboardData {
  assets: { total: number; critical: number }
  controls: { total: number; applicable: number; implemented: number; implementation_percentage: number }
  risks: { open: number; high_critical: number }
  incidents: { open: number; last_30_days: number }
  suppliers: { high_risk: number }
  compliance_score: number
}

export default function IMSDashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'mapping' | 'audit' | 'review' | 'isms'>('overview')
  const [selectedStandard, setSelectedStandard] = useState<string | null>(null)
  const [ismsData, setIsmsData] = useState<ISMSDashboardData | null>(null)
  const [ismsLoading, setIsmsLoading] = useState(false)

  useEffect(() => {
    if (activeTab === 'isms') {
      setIsmsLoading(true)
      // Simulated data - replace with actual API call
      setTimeout(() => {
        setIsmsData({
          assets: { total: 156, critical: 23 },
          controls: { total: 93, applicable: 87, implemented: 72, implementation_percentage: 82.8 },
          risks: { open: 18, high_critical: 4 },
          incidents: { open: 3, last_30_days: 7 },
          suppliers: { high_risk: 2 },
          compliance_score: 82.8,
        })
        setIsmsLoading(false)
      }, 500)
    }
  }, [activeTab])

  const standards: Standard[] = [
    {
      id: 'iso9001',
      name: 'ISO 9001:2015',
      version: 'Quality Management',
      icon: Shield,
      color: 'bg-blue-500',
      compliance: 94,
      findings: { major: 0, minor: 2, observations: 3 },
      lastAudit: '2025-09-15',
      nextAudit: '2026-03-15',
      certificateExpiry: '2027-09-14',
    },
    {
      id: 'iso14001',
      name: 'ISO 14001:2015',
      version: 'Environmental Management',
      icon: Leaf,
      color: 'bg-emerald-500',
      compliance: 91,
      findings: { major: 0, minor: 3, observations: 2 },
      lastAudit: '2025-09-15',
      nextAudit: '2026-03-15',
      certificateExpiry: '2027-09-14',
    },
    {
      id: 'iso45001',
      name: 'ISO 45001:2018',
      version: 'OH&S Management',
      icon: HardHat,
      color: 'bg-orange-500',
      compliance: 96,
      findings: { major: 0, minor: 1, observations: 4 },
      lastAudit: '2025-09-15',
      nextAudit: '2026-03-15',
      certificateExpiry: '2027-09-14',
    },
    {
      id: 'iso27001',
      name: 'ISO 27001:2022',
      version: 'Information Security',
      icon: Lock,
      color: 'bg-purple-500',
      compliance: 89,
      findings: { major: 0, minor: 4, observations: 5 },
      lastAudit: '2025-10-20',
      nextAudit: '2026-04-20',
      certificateExpiry: '2027-10-19',
    },
    {
      id: 'planetmark',
      name: 'Planet Mark',
      version: 'Carbon Certification',
      icon: Leaf,
      color: 'bg-teal-500',
      compliance: 87,
      findings: { major: 0, minor: 2, observations: 1 },
      lastAudit: '2024-09-30',
      nextAudit: '2026-06-30',
      certificateExpiry: '2026-09-30',
    },
    {
      id: 'uvdb',
      name: 'UVDB Achilles',
      version: 'Verify B2 Audit',
      icon: Award,
      color: 'bg-yellow-500',
      compliance: 94,
      findings: { major: 0, minor: 1, observations: 2 },
      lastAudit: '2025-09-15',
      nextAudit: '2026-03-15',
      certificateExpiry: '2026-09-14',
    },
  ]

  const crossMappings: CrossMapping[] = [
    {
      clause: '4.1 Context',
      standards: [
        { standard: 'ISO 9001', clause: '4.1', title: 'Understanding the organization' },
        { standard: 'ISO 14001', clause: '4.1', title: 'Understanding the organization' },
        { standard: 'ISO 45001', clause: '4.1', title: 'Understanding the organization' },
        { standard: 'ISO 27001', clause: '4.1', title: 'Understanding the organization' },
      ],
      control: 'CTRL-001: Context Analysis Procedure',
      evidence: 4,
    },
    {
      clause: '5.1 Leadership',
      standards: [
        { standard: 'ISO 9001', clause: '5.1', title: 'Leadership and commitment' },
        { standard: 'ISO 14001', clause: '5.1', title: 'Leadership and commitment' },
        { standard: 'ISO 45001', clause: '5.1', title: 'Leadership and commitment' },
        { standard: 'ISO 27001', clause: '5.1', title: 'Leadership and commitment' },
      ],
      control: 'CTRL-005: Management Commitment Statement',
      evidence: 6,
    },
    {
      clause: '6.1 Risks & Opportunities',
      standards: [
        { standard: 'ISO 9001', clause: '6.1', title: 'Actions to address risks' },
        { standard: 'ISO 14001', clause: '6.1', title: 'Actions to address risks' },
        { standard: 'ISO 45001', clause: '6.1', title: 'Actions to address risks' },
        { standard: 'ISO 27001', clause: '6.1', title: 'Information security risk assessment' },
      ],
      control: 'CTRL-010: Risk Assessment Procedure',
      evidence: 10,
    },
    {
      clause: '7.2 Competence',
      standards: [
        { standard: 'ISO 9001', clause: '7.2', title: 'Competence' },
        { standard: 'ISO 14001', clause: '7.2', title: 'Competence' },
        { standard: 'ISO 45001', clause: '7.2', title: 'Competence' },
        { standard: 'ISO 27001', clause: '7.2', title: 'Competence' },
      ],
      control: 'CTRL-015: Training & Competency Procedure',
      evidence: 8,
    },
    {
      clause: '9.2 Internal Audit',
      standards: [
        { standard: 'ISO 9001', clause: '9.2', title: 'Internal audit' },
        { standard: 'ISO 14001', clause: '9.2', title: 'Internal audit' },
        { standard: 'ISO 45001', clause: '9.2', title: 'Internal audit' },
        { standard: 'ISO 27001', clause: '9.2', title: 'Internal audit' },
      ],
      control: 'CTRL-020: Internal Audit Procedure',
      evidence: 16,
    },
    {
      clause: '10.2 Nonconformity & Corrective Action',
      standards: [
        { standard: 'ISO 9001', clause: '10.2', title: 'Nonconformity and corrective action' },
        { standard: 'ISO 14001', clause: '10.2', title: 'Nonconformity and corrective action' },
        { standard: 'ISO 45001', clause: '10.2', title: 'Incident investigation' },
        { standard: 'ISO 27001', clause: '10.2', title: 'Nonconformity and corrective action' },
      ],
      control: 'CTRL-025: CAPA Procedure',
      evidence: 18,
    },
  ]

  const auditSchedule = [
    { id: 1, type: 'Internal', scope: 'Full IMS', date: '2026-02-15', lead: 'John Smith', status: 'Planned' },
    { id: 2, type: 'Surveillance', scope: '9001, 14001, 45001', date: '2026-03-15', lead: 'External CB', status: 'Confirmed' },
    { id: 3, type: 'Internal', scope: 'Environmental Aspects', date: '2026-04-20', lead: 'Sarah Johnson', status: 'Draft' },
    { id: 4, type: 'Internal', scope: 'OH&S Hazards', date: '2026-05-10', lead: 'Mike Davis', status: 'Draft' },
    { id: 5, type: 'External', scope: 'UVDB B2 Verify', date: '2026-03-15', lead: 'Achilles', status: 'Confirmed' },
    { id: 6, type: 'Surveillance', scope: 'ISO 27001 ISMS', date: '2026-04-20', lead: 'External CB', status: 'Planned' },
    { id: 7, type: 'Certification', scope: 'Planet Mark Year 2', date: '2026-06-30', lead: 'Planet Mark', status: 'Planned' },
  ]

  const managementReviewInputs = [
    { category: 'Audit Results', status: 'Complete', source: 'All Standards', trend: 'improving' },
    { category: 'Customer Feedback', status: 'Complete', source: 'ISO 9001', trend: 'stable' },
    { category: 'Process Performance', status: 'In Progress', source: 'All Standards', trend: 'improving' },
    { category: 'Environmental Performance', status: 'Complete', source: 'ISO 14001', trend: 'improving' },
    { category: 'OH&S Performance', status: 'Complete', source: 'ISO 45001', trend: 'stable' },
    { category: 'Information Security', status: 'Complete', source: 'ISO 27001', trend: 'improving' },
    { category: 'Carbon Footprint', status: 'Complete', source: 'Planet Mark', trend: 'improving' },
    { category: 'UVDB Qualification', status: 'Complete', source: 'UVDB Achilles', trend: 'stable' },
    { category: 'Objectives Achievement', status: 'Pending', source: 'All Standards', trend: 'stable' },
    { category: 'Risks & Opportunities', status: 'In Progress', source: 'All Standards', trend: 'stable' },
    { category: 'Resource Adequacy', status: 'Pending', source: 'All Standards', trend: 'stable' },
  ]

  const overallCompliance = Math.round(
    standards.reduce((sum, s) => sum + s.compliance, 0) / standards.length
  )

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
            <GitMerge className="w-8 h-8 text-emerald-400" />
            Integrated Management System
          </h1>
          <p className="text-gray-400">Unified ISO 9001, 14001, 45001 & 27001 Dashboard</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">
            <RefreshCw className="w-4 h-4" />
            Sync
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors">
            <FileText className="w-4 h-4" />
            Generate Report
          </button>
        </div>
      </div>

      {/* Overall Compliance Indicator */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">Overall IMS Compliance</h2>
            <p className="text-emerald-100">Across all management system standards</p>
          </div>
          <div className="text-right">
            <div className="text-5xl font-bold text-white">{overallCompliance}%</div>
            <div className="flex items-center gap-1 text-emerald-100 mt-1">
              <TrendingUp className="w-4 h-4" />
              <span>+2% from last quarter</span>
            </div>
          </div>
        </div>
      </div>

      {/* Standards Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {standards.map((standard) => {
          const Icon = standard.icon
          return (
            <div
              key={standard.id}
              className={`bg-slate-800 rounded-xl p-6 border border-slate-700 hover:border-slate-500 transition-colors cursor-pointer ${
                selectedStandard === standard.id ? 'ring-2 ring-emerald-500' : ''
              }`}
              onClick={() => setSelectedStandard(standard.id)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl ${standard.color}`}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold text-white">{standard.compliance}%</div>
                  <div className="text-xs text-gray-400">Compliance</div>
                </div>
              </div>

              <h3 className="text-lg font-bold text-white mb-1">{standard.name}</h3>
              <p className="text-sm text-gray-400 mb-4">{standard.version}</p>

              {/* Progress Bar */}
              <div className="w-full bg-slate-700 rounded-full h-2 mb-4">
                <div
                  className={`h-2 rounded-full ${standard.color}`}
                  style={{ width: `${standard.compliance}%` }}
                ></div>
              </div>

              {/* Findings Summary */}
              <div className="flex justify-between text-sm">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                  <span className="text-gray-400">Major: {standard.findings.major}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-yellow-500 rounded-full"></span>
                  <span className="text-gray-400">Minor: {standard.findings.minor}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                  <span className="text-gray-400">Obs: {standard.findings.observations}</span>
                </div>
              </div>

              {/* Dates */}
              <div className="mt-4 pt-4 border-t border-slate-700 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-gray-500">Next Audit</span>
                  <div className="text-gray-300">{standard.nextAudit}</div>
                </div>
                <div>
                  <span className="text-gray-500">Cert Expiry</span>
                  <div className="text-gray-300">{standard.certificateExpiry}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-slate-700 pb-2">
        {[
          { id: 'overview', label: 'Overview', icon: BarChart3 },
          { id: 'mapping', label: 'Cross-Standard Mapping', icon: Link2 },
          { id: 'audit', label: 'Unified Audit Plan', icon: ClipboardList },
          { id: 'review', label: 'Management Review', icon: Users },
          { id: 'isms', label: 'ISO 27001 ISMS', icon: Lock },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-emerald-600 text-white'
                  : 'text-gray-400 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Key Metrics */}
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <h3 className="text-lg font-bold text-white mb-4">Key Performance Metrics</h3>
            <div className="space-y-4">
              {[
                { label: 'Open Actions', value: 12, target: 0, unit: '', status: 'warning' },
                { label: 'Overdue Actions', value: 2, target: 0, unit: '', status: 'critical' },
                { label: 'Document Review Compliance', value: 94, target: 100, unit: '%', status: 'good' },
                { label: 'Training Completion', value: 98, target: 100, unit: '%', status: 'good' },
                { label: 'Audit Completion', value: 75, target: 100, unit: '%', status: 'warning' },
              ].map((metric, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-gray-300">{metric.label}</span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-bold ${
                        metric.status === 'good'
                          ? 'text-emerald-400'
                          : metric.status === 'warning'
                          ? 'text-yellow-400'
                          : 'text-red-400'
                      }`}
                    >
                      {metric.value}
                      {metric.unit}
                    </span>
                    <span className="text-gray-500 text-sm">/ {metric.target}{metric.unit}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <h3 className="text-lg font-bold text-white mb-4">Recent Activity</h3>
            <div className="space-y-3">
              {[
                { action: 'Audit Finding Closed', detail: 'Minor NC #2024-015', time: '2 hours ago', icon: CheckCircle2, color: 'text-emerald-400' },
                { action: 'Document Updated', detail: 'Environmental Aspects Register', time: '4 hours ago', icon: FileText, color: 'text-blue-400' },
                { action: 'Risk Assessment Completed', detail: 'New Contractor Activity', time: '1 day ago', icon: Shield, color: 'text-purple-400' },
                { action: 'Training Completed', detail: 'ISO 45001 Awareness - 15 staff', time: '2 days ago', icon: Users, color: 'text-orange-400' },
                { action: 'Objective Updated', detail: 'Q4 Recycling Target Achieved', time: '3 days ago', icon: Target, color: 'text-emerald-400' },
              ].map((activity, i) => {
                const Icon = activity.icon
                return (
                  <div key={i} className="flex items-start gap-3 p-2 hover:bg-slate-700 rounded-lg transition-colors">
                    <Icon className={`w-5 h-5 mt-0.5 ${activity.color}`} />
                    <div className="flex-grow">
                      <div className="text-white text-sm">{activity.action}</div>
                      <div className="text-gray-400 text-xs">{activity.detail}</div>
                    </div>
                    <span className="text-gray-500 text-xs">{activity.time}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'mapping' && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="p-4 bg-slate-700 border-b border-slate-600">
            <h3 className="font-bold text-white">Annex SL Cross-Standard Mapping</h3>
            <p className="text-sm text-gray-400">Common requirements across ISO 9001, 14001, 45001 & 27001</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-700/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Common Clause</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 9001</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 14001</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 45001</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 27001</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Unified Control</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {crossMappings.map((mapping, i) => (
                  <tr key={i} className="hover:bg-slate-700/50">
                    <td className="px-4 py-3 font-medium text-white">{mapping.clause}</td>
                    {mapping.standards.map((s, j) => (
                      <td key={j} className="px-4 py-3 text-center">
                        <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                          {s.clause}
                        </span>
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      <span className="text-emerald-400 text-sm">{mapping.control}</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm font-medium">
                        {mapping.evidence}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
            <div>
              <h3 className="font-bold text-white">Unified Audit Schedule</h3>
              <p className="text-sm text-gray-400">Integrated audit program covering all standards</p>
            </div>
            <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors">
              Plan New Audit
            </button>
          </div>
          <div className="p-4 space-y-4">
            {auditSchedule.map((audit) => (
              <div
                key={audit.id}
                className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-slate-600 rounded-lg">
                    <Calendar className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <div className="font-medium text-white">
                      {audit.type} Audit - {audit.scope}
                    </div>
                    <div className="text-sm text-gray-400">
                      Lead: {audit.lead} | Date: {audit.date}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      audit.status === 'Confirmed'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : audit.status === 'Planned'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {audit.status}
                  </span>
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'review' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Inputs Progress */}
          <div className="lg:col-span-2 bg-slate-800 rounded-xl border border-slate-700">
            <div className="p-4 bg-slate-700 border-b border-slate-600">
              <h3 className="font-bold text-white">Management Review Inputs</h3>
              <p className="text-sm text-gray-400">Next Review: March 2026</p>
            </div>
            <div className="p-4 space-y-3">
              {managementReviewInputs.map((input, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {input.status === 'Complete' ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : input.status === 'In Progress' ? (
                      <Clock className="w-5 h-5 text-yellow-400" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-gray-400" />
                    )}
                    <div>
                      <div className="font-medium text-white">{input.category}</div>
                      <div className="text-xs text-gray-400">{input.source}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`flex items-center gap-1 text-sm ${
                      input.trend === 'improving' ? 'text-emerald-400' : 'text-gray-400'
                    }`}>
                      {input.trend === 'improving' ? (
                        <TrendingUp className="w-4 h-4" />
                      ) : (
                        <span className="text-lg">—</span>
                      )}
                    </div>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        input.status === 'Complete'
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : input.status === 'In Progress'
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-gray-500/20 text-gray-400'
                      }`}
                    >
                      {input.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Review Summary */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
            <h3 className="font-bold text-white mb-4">Review Readiness</h3>
            
            <div className="relative w-40 h-40 mx-auto mb-6">
              <svg className="w-full h-full transform -rotate-90">
                <circle
                  cx="80"
                  cy="80"
                  r="70"
                  stroke="currentColor"
                  strokeWidth="10"
                  fill="transparent"
                  className="text-slate-700"
                />
                <circle
                  cx="80"
                  cy="80"
                  r="70"
                  stroke="currentColor"
                  strokeWidth="10"
                  fill="transparent"
                  strokeDasharray={`${(5 / 8) * 440} 440`}
                  className="text-emerald-500"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold text-white">62%</span>
                <span className="text-sm text-gray-400">Complete</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Inputs Complete</span>
                <span className="text-white font-medium">5 / 8</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Days to Review</span>
                <span className="text-white font-medium">54</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Attendees Confirmed</span>
                <span className="text-white font-medium">6 / 8</span>
              </div>
            </div>

            <button className="w-full mt-6 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors">
              Schedule Review Meeting
            </button>
          </div>
        </div>
      )}

      {/* ISO 27001 ISMS Tab */}
      {activeTab === 'isms' && (
        <div className="space-y-6">
          {ismsLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            </div>
          ) : ismsData ? (
            <>
              {/* ISMS Compliance Score */}
              <div className="bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-white mb-1">ISO 27001:2022 ISMS Compliance</h2>
                    <p className="text-purple-100">Information Security Management System</p>
                  </div>
                  <div className="text-right">
                    <div className="text-5xl font-bold text-white">{ismsData.compliance_score}%</div>
                    <div className="flex items-center gap-1 text-purple-100 mt-1">
                      <ShieldCheck className="w-4 h-4" />
                      <span>Annex A Controls Implemented</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* ISMS Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-blue-500/20 rounded-lg">
                      <Server className="w-5 h-5 text-blue-400" />
                    </div>
                    <span className="text-gray-400 text-sm">Information Assets</span>
                  </div>
                  <div className="text-3xl font-bold text-white">{ismsData.assets.total}</div>
                  <div className="text-sm text-yellow-400 mt-1">{ismsData.assets.critical} Critical</div>
                </div>

                <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-emerald-500/20 rounded-lg">
                      <ShieldCheck className="w-5 h-5 text-emerald-400" />
                    </div>
                    <span className="text-gray-400 text-sm">Annex A Controls</span>
                  </div>
                  <div className="text-3xl font-bold text-white">{ismsData.controls.implemented}/{ismsData.controls.applicable}</div>
                  <div className="text-sm text-emerald-400 mt-1">{ismsData.controls.implementation_percentage}% Implemented</div>
                </div>

                <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-orange-500/20 rounded-lg">
                      <AlertOctagon className="w-5 h-5 text-orange-400" />
                    </div>
                    <span className="text-gray-400 text-sm">Security Risks</span>
                  </div>
                  <div className="text-3xl font-bold text-white">{ismsData.risks.open}</div>
                  <div className="text-sm text-red-400 mt-1">{ismsData.risks.high_critical} High/Critical</div>
                </div>

                <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-red-500/20 rounded-lg">
                      <Bug className="w-5 h-5 text-red-400" />
                    </div>
                    <span className="text-gray-400 text-sm">Security Incidents</span>
                  </div>
                  <div className="text-3xl font-bold text-white">{ismsData.incidents.open}</div>
                  <div className="text-sm text-gray-400 mt-1">{ismsData.incidents.last_30_days} in last 30 days</div>
                </div>

                <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-500/20 rounded-lg">
                      <Building2 className="w-5 h-5 text-purple-400" />
                    </div>
                    <span className="text-gray-400 text-sm">Supplier Risk</span>
                  </div>
                  <div className="text-3xl font-bold text-white">{ismsData.suppliers.high_risk}</div>
                  <div className="text-sm text-yellow-400 mt-1">High Risk Suppliers</div>
                </div>
              </div>

              {/* Annex A Control Domains */}
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">Annex A Control Domains (ISO 27001:2022)</h3>
                  <p className="text-sm text-gray-400">93 controls across 4 themes</p>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { domain: 'Organizational', count: 37, implemented: 31, icon: Building2, color: 'bg-blue-500' },
                    { domain: 'People', count: 8, implemented: 7, icon: UserCheck, color: 'bg-green-500' },
                    { domain: 'Physical', count: 14, implemented: 11, icon: Key, color: 'bg-orange-500' },
                    { domain: 'Technological', count: 34, implemented: 23, icon: Laptop, color: 'bg-purple-500' },
                  ].map((domain, i) => {
                    const Icon = domain.icon
                    const percentage = Math.round((domain.implemented / domain.count) * 100)
                    return (
                      <div key={i} className="bg-slate-700/50 rounded-lg p-4">
                        <div className="flex items-center gap-3 mb-3">
                          <div className={`p-2 rounded-lg ${domain.color}`}>
                            <Icon className="w-5 h-5 text-white" />
                          </div>
                          <div>
                            <div className="font-medium text-white">{domain.domain}</div>
                            <div className="text-xs text-gray-400">{domain.count} controls</div>
                          </div>
                        </div>
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-gray-400">Implemented</span>
                          <span className="text-white font-medium">{domain.implemented}/{domain.count}</span>
                        </div>
                        <div className="w-full bg-slate-600 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${domain.color}`}
                            style={{ width: `${percentage}%` }}
                          ></div>
                        </div>
                        <div className="text-right text-xs text-gray-400 mt-1">{percentage}%</div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Information Asset Categories & Security Incidents */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Asset Categories */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600">
                    <h3 className="font-bold text-white">Information Asset Categories</h3>
                  </div>
                  <div className="p-4 space-y-3">
                    {[
                      { category: 'Hardware', count: 45, icon: Server, critical: 8 },
                      { category: 'Software', count: 32, icon: Laptop, critical: 5 },
                      { category: 'Data', count: 38, icon: Database, critical: 7 },
                      { category: 'Services', count: 21, icon: Globe, critical: 2 },
                      { category: 'People', count: 15, icon: Users, critical: 1 },
                      { category: 'Physical', count: 5, icon: Key, critical: 0 },
                    ].map((cat, i) => {
                      const Icon = cat.icon
                      return (
                        <div key={i} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer">
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-slate-600 rounded-lg">
                              <Icon className="w-4 h-4 text-gray-300" />
                            </div>
                            <span className="text-white font-medium">{cat.category}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-gray-400">{cat.count} assets</span>
                            {cat.critical > 0 && (
                              <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">
                                {cat.critical} critical
                              </span>
                            )}
                            <ChevronRight className="w-4 h-4 text-gray-500" />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Recent Security Incidents */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-white">Recent Security Incidents</h3>
                      <p className="text-sm text-gray-400">Last 30 days</p>
                    </div>
                    <button className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded-lg text-sm font-medium transition-colors">
                      Report Incident
                    </button>
                  </div>
                  <div className="p-4 space-y-3">
                    {[
                      { id: 'SEC-00042', title: 'Phishing Attempt Detected', type: 'phishing', severity: 'medium', status: 'investigating', date: '2026-01-18' },
                      { id: 'SEC-00041', title: 'Unauthorized Access Attempt', type: 'unauthorized_access', severity: 'high', status: 'contained', date: '2026-01-15' },
                      { id: 'SEC-00040', title: 'Data Loss Prevention Alert', type: 'data_leak', severity: 'low', status: 'closed', date: '2026-01-12' },
                      { id: 'SEC-00039', title: 'Malware Detection on Endpoint', type: 'malware', severity: 'medium', status: 'closed', date: '2026-01-10' },
                    ].map((incident, i) => (
                      <div key={i} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <Bug className={`w-5 h-5 ${
                            incident.severity === 'high' ? 'text-red-400' :
                            incident.severity === 'medium' ? 'text-yellow-400' : 'text-blue-400'
                          }`} />
                          <div>
                            <div className="font-medium text-white text-sm">{incident.title}</div>
                            <div className="text-xs text-gray-400">{incident.id} • {incident.date}</div>
                          </div>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          incident.status === 'investigating' ? 'bg-yellow-500/20 text-yellow-400' :
                          incident.status === 'contained' ? 'bg-blue-500/20 text-blue-400' :
                          'bg-emerald-500/20 text-emerald-400'
                        }`}>
                          {incident.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Statement of Applicability Summary */}
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-white">Statement of Applicability (SoA)</h3>
                    <p className="text-sm text-gray-400">Version 2.1 - Last Updated: January 2026</p>
                  </div>
                  <button className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    Export SoA
                  </button>
                </div>
                <div className="p-6">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="text-center p-4 bg-slate-700/50 rounded-lg">
                      <div className="text-3xl font-bold text-white">{ismsData.controls.total}</div>
                      <div className="text-sm text-gray-400">Total Controls</div>
                    </div>
                    <div className="text-center p-4 bg-emerald-500/10 rounded-lg border border-emerald-500/30">
                      <div className="text-3xl font-bold text-emerald-400">{ismsData.controls.applicable}</div>
                      <div className="text-sm text-gray-400">Applicable</div>
                    </div>
                    <div className="text-center p-4 bg-blue-500/10 rounded-lg border border-blue-500/30">
                      <div className="text-3xl font-bold text-blue-400">{ismsData.controls.implemented}</div>
                      <div className="text-sm text-gray-400">Implemented</div>
                    </div>
                    <div className="text-center p-4 bg-gray-500/10 rounded-lg border border-gray-500/30">
                      <div className="text-3xl font-bold text-gray-400">{ismsData.controls.total - ismsData.controls.applicable}</div>
                      <div className="text-sm text-gray-400">Excluded</div>
                    </div>
                  </div>
                  <div className="text-center">
                    <p className="text-gray-400 text-sm">
                      The Statement of Applicability documents all 93 Annex A controls from ISO 27001:2022,
                      their applicability status, implementation status, and justification for exclusions.
                    </p>
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}
