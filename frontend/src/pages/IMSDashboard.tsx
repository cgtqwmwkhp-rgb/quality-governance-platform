import { useState } from 'react'
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

export default function IMSDashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'mapping' | 'audit' | 'review'>('overview')
  const [selectedStandard, setSelectedStandard] = useState<string | null>(null)

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
  ]

  const crossMappings: CrossMapping[] = [
    {
      clause: '4.1 Context',
      standards: [
        { standard: 'ISO 9001', clause: '4.1', title: 'Understanding the organization' },
        { standard: 'ISO 14001', clause: '4.1', title: 'Understanding the organization' },
        { standard: 'ISO 45001', clause: '4.1', title: 'Understanding the organization' },
      ],
      control: 'CTRL-001: Context Analysis Procedure',
      evidence: 3,
    },
    {
      clause: '5.1 Leadership',
      standards: [
        { standard: 'ISO 9001', clause: '5.1', title: 'Leadership and commitment' },
        { standard: 'ISO 14001', clause: '5.1', title: 'Leadership and commitment' },
        { standard: 'ISO 45001', clause: '5.1', title: 'Leadership and commitment' },
      ],
      control: 'CTRL-005: Management Commitment Statement',
      evidence: 5,
    },
    {
      clause: '6.1 Risks & Opportunities',
      standards: [
        { standard: 'ISO 9001', clause: '6.1', title: 'Actions to address risks' },
        { standard: 'ISO 14001', clause: '6.1', title: 'Actions to address risks' },
        { standard: 'ISO 45001', clause: '6.1', title: 'Actions to address risks' },
      ],
      control: 'CTRL-010: Risk Assessment Procedure',
      evidence: 8,
    },
    {
      clause: '9.2 Internal Audit',
      standards: [
        { standard: 'ISO 9001', clause: '9.2', title: 'Internal audit' },
        { standard: 'ISO 14001', clause: '9.2', title: 'Internal audit' },
        { standard: 'ISO 45001', clause: '9.2', title: 'Internal audit' },
      ],
      control: 'CTRL-020: Internal Audit Procedure',
      evidence: 12,
    },
    {
      clause: '10.2 Nonconformity',
      standards: [
        { standard: 'ISO 9001', clause: '10.2', title: 'Nonconformity and corrective action' },
        { standard: 'ISO 14001', clause: '10.2', title: 'Nonconformity and corrective action' },
        { standard: 'ISO 45001', clause: '10.2', title: 'Incident investigation' },
      ],
      control: 'CTRL-025: CAPA Procedure',
      evidence: 15,
    },
  ]

  const auditSchedule = [
    { id: 1, type: 'Internal', scope: 'Full IMS', date: '2026-02-15', lead: 'John Smith', status: 'Planned' },
    { id: 2, type: 'Surveillance', scope: '9001, 14001, 45001', date: '2026-03-15', lead: 'External CB', status: 'Confirmed' },
    { id: 3, type: 'Internal', scope: 'Environmental Aspects', date: '2026-04-20', lead: 'Sarah Johnson', status: 'Draft' },
    { id: 4, type: 'Internal', scope: 'OH&S Hazards', date: '2026-05-10', lead: 'Mike Davis', status: 'Draft' },
  ]

  const managementReviewInputs = [
    { category: 'Audit Results', status: 'Complete', source: 'All Standards', trend: 'improving' },
    { category: 'Customer Feedback', status: 'Complete', source: 'ISO 9001', trend: 'stable' },
    { category: 'Process Performance', status: 'In Progress', source: 'All Standards', trend: 'improving' },
    { category: 'Environmental Performance', status: 'Complete', source: 'ISO 14001', trend: 'improving' },
    { category: 'OH&S Performance', status: 'Complete', source: 'ISO 45001', trend: 'stable' },
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
          <p className="text-gray-400">Unified ISO 9001, 14001 & 45001 Dashboard</p>
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
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
            <p className="text-sm text-gray-400">Common requirements across ISO 9001, 14001 & 45001</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-700/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Common Clause</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 9001</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 14001</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 45001</th>
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
    </div>
  )
}
