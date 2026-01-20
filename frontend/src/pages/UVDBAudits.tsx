import { useState, useEffect } from 'react'
import {
  Shield,
  Leaf,
  HardHat,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronRight,
  FileText,
  Users,
  Building2,
  Truck,
  Wrench,
  BarChart3,
  Target,
  RefreshCw,
  Plus,
  Search,
  Filter,
  Download,
  Calendar,
  TrendingUp,
  Award,
  ClipboardList,
  ExternalLink,
  Link2,
  Zap,
} from 'lucide-react'

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

export default function UVDBAudits() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'protocol' | 'audits' | 'mapping'>('dashboard')
  const [sections, setSections] = useState<UVDBSection[]>([])
  const [audits, setAudits] = useState<UVDBAudit[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Simulated data load
    setTimeout(() => {
      setSections([
        { number: '1', title: 'System Assurance and Compliance', max_score: 21, question_count: 5, iso_mapping: { '9001': '4-5', '14001': '4-5', '45001': '4-5' } },
        { number: '2', title: 'Quality Control and Assurance', max_score: 21, question_count: 5, iso_mapping: { '9001': '7-8', '27001': '7.5' } },
        { number: '3', title: 'Health and Safety Leadership', max_score: 18, question_count: 5, iso_mapping: { '45001': '5' } },
        { number: '4', title: 'Health and Safety Management', max_score: 21, question_count: 7, iso_mapping: { '45001': '6-8' } },
        { number: '5', title: 'Health and Safety Arrangements', max_score: 21, question_count: 7, iso_mapping: { '45001': '8' } },
        { number: '6', title: 'Occupational Health', max_score: 15, question_count: 5, iso_mapping: { '45001': '8.1.2' } },
        { number: '7', title: 'Safety Critical Personnel', max_score: 15, question_count: 5, iso_mapping: { '45001': '7.2' } },
        { number: '8', title: 'Environmental Leadership', max_score: 15, question_count: 4, iso_mapping: { '14001': '5' } },
        { number: '9', title: 'Environmental Management', max_score: 21, question_count: 7, iso_mapping: { '14001': '6-8' } },
        { number: '10', title: 'Environmental Arrangements', max_score: 15, question_count: 5, iso_mapping: { '14001': '8' } },
        { number: '11', title: 'Waste Management', max_score: 12, question_count: 4, iso_mapping: { '14001': '8.1' } },
        { number: '12', title: 'Selection and Management of Sub-contractors', max_score: 12, question_count: 2, iso_mapping: { '9001': '8.4', '45001': '8.1.4' } },
        { number: '13', title: 'Sourcing of Goods and Products', max_score: 12, question_count: 4, iso_mapping: { '9001': '8.4' } },
        { number: '14', title: 'Use of Work Equipment, Vehicles and Machines', max_score: 6, question_count: 1, iso_mapping: { '45001': '8.1' } },
        { number: '15', title: 'Key Performance Indicators', max_score: 0, question_count: 14, iso_mapping: { '45001': '9.1', '14001': '9.1' } },
      ])
      setAudits([
        { id: 1, audit_reference: 'UVDB-2025-0001', company_name: 'Plantexpand Limited', audit_type: 'B2', audit_date: '2025-09-15', status: 'completed', percentage_score: 94, lead_auditor: 'John Smith' },
        { id: 2, audit_reference: 'UVDB-2026-0001', company_name: 'Plantexpand Limited', audit_type: 'B2', audit_date: '2026-03-15', status: 'scheduled', percentage_score: null, lead_auditor: 'External Auditor' },
      ])
      setLoading(false)
    }, 500)
  }, [])

  const totalMaxScore = sections.reduce((sum, s) => sum + s.max_score, 0)

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500/20 text-emerald-400'
      case 'in_progress': return 'bg-blue-500/20 text-blue-400'
      case 'scheduled': return 'bg-yellow-500/20 text-yellow-400'
      case 'expired': return 'bg-red-500/20 text-red-400'
      default: return 'bg-gray-500/20 text-gray-400'
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

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
            <Award className="w-8 h-8 text-yellow-400" />
            UVDB Achilles Verify B2
          </h1>
          <p className="text-gray-400">Utilities Vendor Database - Supply Chain Qualification Audit</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">
            <Download className="w-4 h-4" />
            Export Protocol
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors">
            <Plus className="w-4 h-4" />
            New Audit
          </button>
        </div>
      </div>

      {/* Protocol Info Banner */}
      <div className="bg-gradient-to-r from-yellow-600 to-orange-600 rounded-xl p-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">UVDB-QS-003 - Verify B2 Audit Protocol</h2>
            <p className="text-yellow-100">Version 11.2 - UK Utilities Sector Qualification Standard</p>
          </div>
          <div className="mt-4 md:mt-0 flex items-center gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-white">{sections.length}</div>
              <div className="text-yellow-100 text-sm">Sections</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-white">{totalMaxScore}</div>
              <div className="text-yellow-100 text-sm">Max Score</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-white">4</div>
              <div className="text-yellow-100 text-sm">ISO Aligned</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-slate-700 pb-2 overflow-x-auto">
        {[
          { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
          { id: 'protocol', label: 'Protocol Sections', icon: ClipboardList },
          { id: 'audits', label: 'Audit History', icon: Calendar },
          { id: 'mapping', label: 'ISO Cross-Mapping', icon: Link2 },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-yellow-600 text-white'
                  : 'text-gray-400 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-yellow-400 animate-spin" />
        </div>
      ) : (
        <>
          {/* Dashboard Tab */}
          {activeTab === 'dashboard' && (
            <div className="space-y-6">
              {/* ISO Alignment Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { standard: 'ISO 9001:2015', title: 'Quality', icon: Shield, color: 'bg-blue-500', sections: '1.1, 2.1-2.5, 12-13' },
                  { standard: 'ISO 14001:2015', title: 'Environmental', icon: Leaf, color: 'bg-emerald-500', sections: '1.3, 8-11, 15' },
                  { standard: 'ISO 45001:2018', title: 'OH&S', icon: HardHat, color: 'bg-orange-500', sections: '1.2, 3-7, 14, 15' },
                  { standard: 'ISO 27001:2022', title: 'Information Security', icon: Lock, color: 'bg-purple-500', sections: '2.3' },
                ].map((iso) => {
                  const Icon = iso.icon
                  return (
                    <div key={iso.standard} className="bg-slate-800 rounded-xl p-5 border border-slate-700">
                      <div className="flex items-center gap-3 mb-3">
                        <div className={`p-2 ${iso.color} rounded-lg`}>
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <div className="font-bold text-white">{iso.standard}</div>
                          <div className="text-xs text-gray-400">{iso.title}</div>
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
                    <h3 className="font-bold text-white">Audit Status</h3>
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
                            {audit.audit_type} Audit • {audit.audit_date || 'TBD'} • {audit.lead_auditor}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {audit.percentage_score && (
                          <div className="text-right">
                            <div className="text-2xl font-bold text-emerald-400">{audit.percentage_score}%</div>
                            <div className="text-xs text-gray-400">Score</div>
                          </div>
                        )}
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(audit.status)}`}>
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
                  <h3 className="font-bold text-white">Section 15: Key Performance Indicators (5 Year Trend)</h3>
                </div>
                <div className="p-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
                  {[
                    { label: 'Man Hours', value: '1.2M', trend: 'up' },
                    { label: 'Fatalities', value: '0', trend: 'stable' },
                    { label: 'RIDDOR', value: '2', trend: 'down' },
                    { label: 'LTI', value: '3', trend: 'down' },
                    { label: 'Near Misses', value: '45', trend: 'up' },
                    { label: 'Env Incidents', value: '1', trend: 'stable' },
                    { label: 'LTIFR', value: '2.5', trend: 'down' },
                  ].map((kpi, i) => (
                    <div key={i} className="bg-slate-700/50 rounded-lg p-4 text-center">
                      <div className="text-2xl font-bold text-white">{kpi.value}</div>
                      <div className="text-xs text-gray-400">{kpi.label}</div>
                      <div className={`flex items-center justify-center gap-1 mt-1 text-xs ${
                        kpi.trend === 'up' ? 'text-emerald-400' :
                        kpi.trend === 'down' ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        {kpi.trend === 'up' && <TrendingUp className="w-3 h-3" />}
                        {kpi.trend === 'down' && <TrendingUp className="w-3 h-3 transform rotate-180" />}
                        {kpi.trend === 'stable' && <span>—</span>}
                      </div>
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
                        <div className="text-xs text-gray-400">Max Score</div>
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
                              iso === '9001' ? 'bg-blue-500/20 text-blue-400' :
                              iso === '14001' ? 'bg-emerald-500/20 text-emerald-400' :
                              iso === '45001' ? 'bg-orange-500/20 text-orange-400' :
                              'bg-purple-500/20 text-purple-400'
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
                      placeholder="Search audits..."
                      className="pl-10 pr-4 py-2 bg-slate-600 border border-slate-500 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
                    />
                  </div>
                  <button className="flex items-center gap-2 px-3 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors">
                    <Filter className="w-4 h-4" />
                    Filter
                  </button>
                </div>
                <button className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors">
                  <Plus className="w-4 h-4" />
                  New Audit
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-700/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Reference</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Company</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Date</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Lead Auditor</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Score</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Status</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {audits.map((audit) => (
                      <tr key={audit.id} className="hover:bg-slate-700/50">
                        <td className="px-4 py-3 font-medium text-white">{audit.audit_reference}</td>
                        <td className="px-4 py-3 text-gray-300">{audit.company_name}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs font-medium">
                            {audit.audit_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{audit.audit_date || 'TBD'}</td>
                        <td className="px-4 py-3 text-gray-300">{audit.lead_auditor}</td>
                        <td className="px-4 py-3 text-center">
                          {audit.percentage_score ? (
                            <span className="text-emerald-400 font-bold">{audit.percentage_score}%</span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(audit.status)}`}>
                            {audit.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button className="p-2 hover:bg-slate-600 rounded-lg transition-colors">
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
                <h3 className="font-bold text-white">UVDB B2 to ISO Standards Cross-Mapping</h3>
                <p className="text-sm text-gray-400">Demonstrates alignment between UVDB requirements and ISO certification standards</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-700/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">UVDB Section</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Topic</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 9001</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 14001</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 45001</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">ISO 27001</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {[
                      { section: '1.1', topic: 'Quality Management Systems', iso9001: '4.4, 5.1, 9.2', iso14001: '', iso45001: '', iso27001: '' },
                      { section: '1.2', topic: 'Health and Safety Management Systems', iso9001: '', iso14001: '', iso45001: '4.4, 5.1, 9.2', iso27001: '' },
                      { section: '1.3', topic: 'Environmental Management Systems', iso9001: '', iso14001: '4.4, 5.1, 9.2', iso45001: '', iso27001: '' },
                      { section: '1.4', topic: 'CDM Regulations 2015', iso9001: '', iso14001: '', iso45001: '6.1, 8.1', iso27001: '' },
                      { section: '1.5', topic: 'Permits and Licensing', iso9001: '', iso14001: '6.1.3', iso45001: '6.1.3', iso27001: '' },
                      { section: '2.1', topic: 'Top Management Quality Assurance', iso9001: '5.1, 5.2, 5.3', iso14001: '', iso45001: '', iso27001: '' },
                      { section: '2.2', topic: 'Document Control', iso9001: '7.5', iso14001: '', iso45001: '', iso27001: '7.5' },
                      { section: '2.3', topic: 'Information Security', iso9001: '', iso14001: '', iso45001: '', iso27001: '5.1, 8.1, A.8' },
                      { section: '2.4', topic: 'Service Provision & Handover', iso9001: '8.5, 8.6', iso14001: '', iso45001: '', iso27001: '' },
                      { section: '2.5', topic: 'Internal Auditing', iso9001: '9.2', iso14001: '9.2', iso45001: '9.2', iso27001: '' },
                      { section: '12', topic: 'Sub-contractor Management', iso9001: '8.4', iso14001: '', iso45001: '8.1.4', iso27001: '' },
                      { section: '13', topic: 'Sourcing (CFSI, Sustainability)', iso9001: '8.4.2', iso14001: '8.1', iso45001: '', iso27001: '' },
                      { section: '14', topic: 'Work Equipment & Vehicles', iso9001: '', iso14001: '', iso45001: '7.1.3, 8.1', iso27001: '' },
                      { section: '15', topic: 'Key Performance Indicators', iso9001: '', iso14001: '9.1', iso45001: '9.1', iso27001: '' },
                    ].map((row, i) => (
                      <tr key={i} className="hover:bg-slate-700/50">
                        <td className="px-4 py-3 font-medium text-white">{row.section}</td>
                        <td className="px-4 py-3 text-gray-300">{row.topic}</td>
                        <td className="px-4 py-3 text-center">
                          {row.iso9001 && (
                            <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">{row.iso9001}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.iso14001 && (
                            <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">{row.iso14001}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.iso45001 && (
                            <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-xs">{row.iso45001}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.iso27001 && (
                            <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">{row.iso27001}</span>
                          )}
                        </td>
                      </tr>
                    ))}
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
