import { useState, useEffect } from 'react'
import {
  Leaf,
  BarChart3,
  Target,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Fuel,
  Zap,
  Trash2,
  Car,
  Plane,
  Users,
  Building2,
  RefreshCw,
  Plus,
  Download,
  Award,
  Gauge,
  Factory,
  Truck,
  ShoppingCart,
  Briefcase,
  Home,
  Globe,
} from 'lucide-react'

interface ReportingYear {
  id: number
  year_label: string
  year_number: number
  total_emissions: number
  emissions_per_fte: number
  fte: number
  scope_1: number
  scope_2: number
  scope_3: number
  data_quality: number
  certification_status: string
  is_baseline: boolean
}

interface ImprovementAction {
  id: number
  action_id: string
  action_title: string
  owner: string
  deadline: string
  scheduled_month: string
  status: string
  progress_percent: number
  is_overdue: boolean
}

interface Scope3Category {
  number: number
  name: string
  is_measured: boolean
  total_co2e: number
  percentage: number
}

export default function PlanetMark() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'emissions' | 'actions' | 'quality' | 'scope3' | 'certification'>('dashboard')
  const [years, setYears] = useState<ReportingYear[]>([])
  const [currentYear, setCurrentYear] = useState<ReportingYear | null>(null)
  const [actions, setActions] = useState<ImprovementAction[]>([])
  const [scope3Categories, setScope3Categories] = useState<Scope3Category[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Simulated data based on Plantexpand documents
    setTimeout(() => {
      const yearsData: ReportingYear[] = [
        {
          id: 2,
          year_label: 'YE2025',
          year_number: 2,
          total_emissions: 278.5,
          emissions_per_fte: 4.06,
          fte: 68.6,
          scope_1: 256.2,
          scope_2: 18.4,
          scope_3: 3.9,
          data_quality: 11,
          certification_status: 'in_progress',
          is_baseline: false,
        },
        {
          id: 1,
          year_label: 'YE2024',
          year_number: 1,
          total_emissions: 293.2,
          emissions_per_fte: 4.27,
          fte: 68.6,
          scope_1: 260.0,
          scope_2: 20.0,
          scope_3: 13.2,
          data_quality: 9,
          certification_status: 'certified',
          is_baseline: true,
        },
      ]
      setYears(yearsData)
      setCurrentYear(yearsData[0])

      setActions([
        { id: 1, action_id: 'ACT-001', action_title: 'Launch Net-Zero Taskforce & publish baseline dashboard', owner: 'CEO', deadline: '2025-07-31', scheduled_month: 'Jul 25', status: 'completed', progress_percent: 100, is_overdue: false },
        { id: 2, action_id: 'ACT-002', action_title: 'Complete fuel-card audit (100% fleet coverage)', owner: 'Finance', deadline: '2025-08-31', scheduled_month: 'Aug 25', status: 'completed', progress_percent: 100, is_overdue: false },
        { id: 3, action_id: 'ACT-003', action_title: 'Fit GPS trackers to 100% of fleet', owner: 'Technical Director', deadline: '2025-09-30', scheduled_month: 'Sep 25', status: 'completed', progress_percent: 100, is_overdue: false },
        { id: 4, action_id: 'ACT-004', action_title: 'Optimize building heating: smart thermostats & night setback', owner: 'Facilities', deadline: '2025-10-31', scheduled_month: 'Oct 25', status: 'in_progress', progress_percent: 65, is_overdue: false },
        { id: 5, action_id: 'ACT-005', action_title: 'Issue eco-driving literature & driver league table', owner: 'H&S Lead', deadline: '2025-11-30', scheduled_month: 'Nov 25', status: 'in_progress', progress_percent: 30, is_overdue: false },
        { id: 6, action_id: 'ACT-006', action_title: 'Install smart electricity meters', owner: 'Facilities', deadline: '2025-12-31', scheduled_month: 'Dec 25', status: 'planned', progress_percent: 0, is_overdue: false },
        { id: 7, action_id: 'ACT-007', action_title: 'Analyze tracker data & refine routes', owner: 'Technical Director', deadline: '2026-01-31', scheduled_month: 'Jan 26', status: 'planned', progress_percent: 0, is_overdue: false },
        { id: 8, action_id: 'ACT-008', action_title: 'Draft low-carbon purchasing policy', owner: 'Finance', deadline: '2026-02-28', scheduled_month: 'Feb 26', status: 'planned', progress_percent: 0, is_overdue: false },
        { id: 9, action_id: 'ACT-009', action_title: 'Engage top 10 suppliers for Scope 3 data', owner: 'Finance', deadline: '2026-03-31', scheduled_month: 'Mar 26', status: 'planned', progress_percent: 0, is_overdue: false },
        { id: 10, action_id: 'ACT-010', action_title: 'Run company-wide sustainability workshop', owner: 'HR', deadline: '2026-04-30', scheduled_month: 'Apr 26', status: 'planned', progress_percent: 0, is_overdue: false },
        { id: 11, action_id: 'ACT-011', action_title: 'Verify YTD emissions & agree FY26 target', owner: 'Finance', deadline: '2026-05-31', scheduled_month: 'May 26', status: 'planned', progress_percent: 0, is_overdue: false },
        { id: 12, action_id: 'ACT-012', action_title: 'Submit evidence pack to Planet Mark', owner: 'Data Lead', deadline: '2026-06-30', scheduled_month: 'Jun 26', status: 'planned', progress_percent: 0, is_overdue: false },
      ])

      setScope3Categories([
        { number: 1, name: 'Purchased goods and services', is_measured: true, total_co2e: 1.2, percentage: 30.8 },
        { number: 2, name: 'Capital goods', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 3, name: 'Fuel and energy-related activities', is_measured: true, total_co2e: 0.8, percentage: 20.5 },
        { number: 4, name: 'Upstream transportation', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 5, name: 'Waste generated', is_measured: true, total_co2e: 0.5, percentage: 12.8 },
        { number: 6, name: 'Business travel', is_measured: true, total_co2e: 0.3, percentage: 7.7 },
        { number: 7, name: 'Employee commuting', is_measured: true, total_co2e: 1.1, percentage: 28.2 },
        { number: 8, name: 'Upstream leased assets', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 9, name: 'Downstream transportation', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 10, name: 'Processing of sold products', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 11, name: 'Use of sold products', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 12, name: 'End-of-life treatment', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 13, name: 'Downstream leased assets', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 14, name: 'Franchises', is_measured: false, total_co2e: 0, percentage: 0 },
        { number: 15, name: 'Investments', is_measured: false, total_co2e: 0, percentage: 0 },
      ])

      setLoading(false)
    }, 500)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500/20 text-emerald-400'
      case 'in_progress': return 'bg-blue-500/20 text-blue-400'
      case 'planned': return 'bg-gray-500/20 text-gray-400'
      case 'delayed': return 'bg-red-500/20 text-red-400'
      case 'certified': return 'bg-emerald-500/20 text-emerald-400'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  const completedActions = actions.filter(a => a.status === 'completed').length
  const yoyChange = currentYear && years.length >= 2 
    ? ((currentYear.emissions_per_fte - years[1].emissions_per_fte) / years[1].emissions_per_fte * 100) 
    : null

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-gradient-to-br from-green-500 to-teal-600 rounded-xl">
            <Leaf className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Planet Mark Carbon</h1>
            <p className="text-gray-400">Net-Zero Journey • GHG Protocol Aligned</p>
          </div>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">
            <Download className="w-4 h-4" />
            Export Report
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors">
            <Plus className="w-4 h-4" />
            Add Emission
          </button>
        </div>
      </div>

      {/* Year Selector & Summary Banner */}
      {currentYear && (
        <div className="bg-gradient-to-r from-green-600 to-teal-600 rounded-xl p-6 mb-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <select
                  value={currentYear.id}
                  onChange={(e) => setCurrentYear(years.find(y => y.id === parseInt(e.target.value)) || years[0])}
                  className="bg-white/20 border border-white/30 rounded-lg px-3 py-1 text-white font-bold text-lg"
                >
                  {years.map(y => (
                    <option key={y.id} value={y.id} className="bg-slate-800 text-white">
                      {y.year_label} {y.is_baseline ? '(Baseline)' : ''}
                    </option>
                  ))}
                </select>
                {currentYear.certification_status === 'certified' && (
                  <span className="px-3 py-1 bg-white/20 rounded-full text-sm font-medium flex items-center gap-1">
                    <Award className="w-4 h-4" /> Certified
                  </span>
                )}
              </div>
              <p className="text-green-100">
                Reporting: 1 Jul {2024 + currentYear.year_number - 1} → 30 Jun {2024 + currentYear.year_number}
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{currentYear.total_emissions.toFixed(1)}</div>
                <div className="text-green-100 text-sm">tCO₂e Total</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{currentYear.emissions_per_fte.toFixed(2)}</div>
                <div className="text-green-100 text-sm">tCO₂e/FTE</div>
              </div>
              <div className="text-center">
                <div className={`text-3xl font-bold ${yoyChange && yoyChange < 0 ? 'text-white' : 'text-yellow-300'}`}>
                  {yoyChange ? `${yoyChange > 0 ? '+' : ''}${yoyChange.toFixed(1)}%` : '—'}
                </div>
                <div className="text-green-100 text-sm">vs Baseline</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{currentYear.data_quality}/16</div>
                <div className="text-green-100 text-sm">Data Quality</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-slate-700 pb-2 overflow-x-auto">
        {[
          { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
          { id: 'emissions', label: 'Emissions', icon: Factory },
          { id: 'scope3', label: 'Scope 3 Categories', icon: Globe },
          { id: 'actions', label: 'Improvement Plan', icon: Target },
          { id: 'quality', label: 'Data Quality', icon: Gauge },
          { id: 'certification', label: 'Certification', icon: Award },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-green-600 text-white'
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
          <RefreshCw className="w-8 h-8 text-green-400 animate-spin" />
        </div>
      ) : (
        <>
          {/* Dashboard Tab */}
          {activeTab === 'dashboard' && currentYear && (
            <div className="space-y-6">
              {/* Scope Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  { scope: 'Scope 1', value: currentYear.scope_1, color: 'bg-orange-500', icon: Fuel, label: 'Direct Emissions', detail: 'Fleet diesel, Natural gas' },
                  { scope: 'Scope 2', value: currentYear.scope_2, color: 'bg-blue-500', icon: Zap, label: 'Indirect (Energy)', detail: 'Purchased electricity' },
                  { scope: 'Scope 3', value: currentYear.scope_3, color: 'bg-purple-500', icon: Globe, label: 'Value Chain', detail: 'Travel, Waste, Suppliers' },
                ].map((scope) => {
                  const Icon = scope.icon
                  const pct = ((scope.value / currentYear.total_emissions) * 100).toFixed(1)
                  return (
                    <div key={scope.scope} className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-3 ${scope.color} rounded-xl`}>
                            <Icon className="w-6 h-6 text-white" />
                          </div>
                          <div>
                            <div className="font-bold text-white">{scope.scope}</div>
                            <div className="text-xs text-gray-400">{scope.label}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-white">{scope.value.toFixed(1)}</div>
                          <div className="text-xs text-gray-400">tCO₂e</div>
                        </div>
                      </div>
                      <div className="w-full bg-slate-700 rounded-full h-3 mb-2">
                        <div
                          className={`h-3 rounded-full ${scope.color}`}
                          style={{ width: `${pct}%` }}
                        ></div>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">{scope.detail}</span>
                        <span className="text-white font-medium">{pct}%</span>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Key Sources & Action Progress */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Key Emission Sources */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600">
                    <h3 className="font-bold text-white">Key Emission Sources</h3>
                    <p className="text-sm text-gray-400">Top contributors to carbon footprint</p>
                  </div>
                  <div className="p-4 space-y-4">
                    {[
                      { source: 'Fleet Diesel', value: 256.2, pct: 89, icon: Truck, color: 'text-orange-400' },
                      { source: 'Natural Gas (Heating)', value: 18.4, pct: 6, icon: Building2, color: 'text-blue-400' },
                      { source: 'Electricity', value: 1.9, pct: 1, icon: Zap, color: 'text-yellow-400' },
                      { source: 'Employee Commuting', value: 1.1, pct: 0.4, icon: Car, color: 'text-purple-400' },
                      { source: 'Business Travel', value: 0.3, pct: 0.1, icon: Plane, color: 'text-sky-400' },
                    ].map((source, i) => {
                      const Icon = source.icon
                      return (
                        <div key={i} className="flex items-center gap-4">
                          <Icon className={`w-5 h-5 ${source.color}`} />
                          <div className="flex-grow">
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-white">{source.source}</span>
                              <span className="text-gray-400">{source.value} tCO₂e ({source.pct}%)</span>
                            </div>
                            <div className="w-full bg-slate-700 rounded-full h-2">
                              <div
                                className="h-2 rounded-full bg-green-500"
                                style={{ width: `${Math.min(source.pct, 100)}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Improvement Plan Progress */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600 flex justify-between items-center">
                    <div>
                      <h3 className="font-bold text-white">Year 2 Improvement Plan</h3>
                      <p className="text-sm text-gray-400">{completedActions}/{actions.length} actions completed</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-green-400">{Math.round((completedActions / actions.length) * 100)}%</div>
                      <div className="text-xs text-gray-400">Complete</div>
                    </div>
                  </div>
                  <div className="p-4 space-y-3 max-h-80 overflow-y-auto">
                    {actions.slice(0, 6).map((action) => (
                      <div key={action.id} className="flex items-center gap-3 p-2 bg-slate-700/50 rounded-lg">
                        {action.status === 'completed' ? (
                          <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                        ) : action.status === 'in_progress' ? (
                          <Clock className="w-5 h-5 text-blue-400 flex-shrink-0" />
                        ) : (
                          <div className="w-5 h-5 border-2 border-gray-500 rounded-full flex-shrink-0" />
                        )}
                        <div className="flex-grow min-w-0">
                          <div className="text-sm text-white truncate">{action.action_title}</div>
                          <div className="text-xs text-gray-400">{action.scheduled_month} • {action.owner}</div>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs ${getStatusColor(action.status)}`}>
                          {action.progress_percent}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Quarterly Milestones */}
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">Quarterly Milestones (FY 2025-26)</h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4">
                  {[
                    { q: 'Q1', period: 'Jul-Sep 25', milestones: ['Taskforce & dashboard live', 'Fuel-card 100% complete', 'Fleet 100% tracked'], status: 'completed' },
                    { q: 'Q2', period: 'Oct-Dec 25', milestones: ['Heating optimised, gas ↓5%', 'Eco-driving roll-out', 'Smart electricity meters'], status: 'in_progress' },
                    { q: 'Q3', period: 'Jan-Mar 26', milestones: ['Fleet CO₂ ↓≥5% vs July', 'Supplier data ≥90% spend'], status: 'planned' },
                    { q: 'Q4', period: 'Apr-Jun 26', milestones: ['Staff engagement ≥75%', 'Data quality S1&2 ≥12/16', 'Planet Mark submission'], status: 'planned' },
                  ].map((quarter) => (
                    <div key={quarter.q} className={`p-4 rounded-lg border ${
                      quarter.status === 'completed' ? 'bg-green-500/10 border-green-500/30' :
                      quarter.status === 'in_progress' ? 'bg-blue-500/10 border-blue-500/30' :
                      'bg-slate-700/50 border-slate-600'
                    }`}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-bold text-white">{quarter.q}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${getStatusColor(quarter.status)}`}>
                          {quarter.status === 'completed' ? '✓ Done' : quarter.status === 'in_progress' ? 'In Progress' : 'Upcoming'}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 mb-2">{quarter.period}</div>
                      <ul className="space-y-1">
                        {quarter.milestones.map((m, i) => (
                          <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                            <span className={`mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                              quarter.status === 'completed' ? 'bg-green-400' :
                              quarter.status === 'in_progress' && i === 0 ? 'bg-blue-400' : 'bg-gray-500'
                            }`}></span>
                            {m}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Emissions Tab */}
          {activeTab === 'emissions' && currentYear && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600 flex justify-between items-center">
                  <h3 className="font-bold text-white">Emission Sources by Scope</h3>
                  <button className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                    <Plus className="w-4 h-4" /> Add Source
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Source</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Scope</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-gray-300 uppercase">Activity</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-gray-300 uppercase">tCO₂e</th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">% of Total</th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Data Quality</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                      {[
                        { source: 'Fleet Diesel', scope: 'Scope 1', activity: '103,500 litres', co2e: 260.0, pct: 88.7, quality: 'Actual' },
                        { source: 'Natural Gas', scope: 'Scope 1', activity: '110,000 kWh', co2e: 20.0, pct: 6.8, quality: 'Estimated' },
                        { source: 'Electricity (Grid)', scope: 'Scope 2', activity: '9,200 kWh', co2e: 1.9, pct: 0.6, quality: 'Estimated' },
                        { source: 'Employee Commuting', scope: 'Scope 3', activity: '68.6 FTE', co2e: 1.1, pct: 0.4, quality: 'Calculated' },
                        { source: 'Waste Generated', scope: 'Scope 3', activity: '12 tonnes', co2e: 0.5, pct: 0.2, quality: 'Calculated' },
                      ].map((row, i) => (
                        <tr key={i} className="hover:bg-slate-700/50">
                          <td className="px-4 py-3 font-medium text-white">{row.source}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs ${
                              row.scope === 'Scope 1' ? 'bg-orange-500/20 text-orange-400' :
                              row.scope === 'Scope 2' ? 'bg-blue-500/20 text-blue-400' :
                              'bg-purple-500/20 text-purple-400'
                            }`}>{row.scope}</span>
                          </td>
                          <td className="px-4 py-3 text-right text-gray-300">{row.activity}</td>
                          <td className="px-4 py-3 text-right font-bold text-white">{row.co2e.toFixed(1)}</td>
                          <td className="px-4 py-3 text-center text-gray-400">{row.pct}%</td>
                          <td className="px-4 py-3 text-center">
                            <span className={`px-2 py-1 rounded text-xs ${
                              row.quality === 'Actual' ? 'bg-green-500/20 text-green-400' :
                              row.quality === 'Calculated' ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-gray-500/20 text-gray-400'
                            }`}>{row.quality}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-700/30">
                      <tr>
                        <td colSpan={3} className="px-4 py-3 font-bold text-white">Total</td>
                        <td className="px-4 py-3 text-right font-bold text-green-400">{currentYear.total_emissions.toFixed(1)}</td>
                        <td className="px-4 py-3 text-center font-bold text-white">100%</td>
                        <td></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Scope 3 Categories Tab */}
          {activeTab === 'scope3' && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">GHG Protocol Scope 3 Categories</h3>
                  <p className="text-sm text-gray-400">All 15 categories - {scope3Categories.filter(c => c.is_measured).length} currently measured</p>
                </div>
                <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {scope3Categories.map((cat) => {
                    const icons: Record<number, React.ElementType> = {
                      1: ShoppingCart, 2: Building2, 3: Fuel, 4: Truck, 5: Trash2,
                      6: Briefcase, 7: Home, 8: Building2, 9: Truck, 10: Factory,
                      11: Users, 12: Trash2, 13: Building2, 14: Users, 15: BarChart3
                    }
                    const Icon = icons[cat.number] || Globe
                    return (
                      <div
                        key={cat.number}
                        className={`p-4 rounded-lg border ${
                          cat.is_measured
                            ? 'bg-green-500/10 border-green-500/30'
                            : 'bg-slate-700/50 border-slate-600'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <div className={`p-2 rounded-lg ${cat.is_measured ? 'bg-green-500/20' : 'bg-slate-600'}`}>
                              <Icon className={`w-4 h-4 ${cat.is_measured ? 'text-green-400' : 'text-gray-400'}`} />
                            </div>
                            <span className="text-xs text-gray-400">Cat {cat.number}</span>
                          </div>
                          {cat.is_measured ? (
                            <CheckCircle2 className="w-5 h-5 text-green-400" />
                          ) : (
                            <div className="w-5 h-5 border border-gray-500 rounded-full" />
                          )}
                        </div>
                        <div className="text-sm font-medium text-white mb-1">{cat.name}</div>
                        {cat.is_measured && (
                          <div className="text-lg font-bold text-green-400">{cat.total_co2e.toFixed(1)} tCO₂e</div>
                        )}
                        {!cat.is_measured && (
                          <div className="text-sm text-gray-400">Not yet measured</div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Actions Tab */}
          {activeTab === 'actions' && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600 flex justify-between items-center">
                  <div>
                    <h3 className="font-bold text-white">SMART Improvement Actions</h3>
                    <p className="text-sm text-gray-400">Monthly action schedule for Year 2</p>
                  </div>
                  <button className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                    <Plus className="w-4 h-4" /> Add Action
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Month</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Action</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">Owner</th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Progress</th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                      {actions.map((action) => (
                        <tr key={action.id} className="hover:bg-slate-700/50">
                          <td className="px-4 py-3 font-medium text-white">{action.scheduled_month}</td>
                          <td className="px-4 py-3 text-gray-300">{action.action_title}</td>
                          <td className="px-4 py-3 text-gray-400">{action.owner}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-20 bg-slate-700 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full ${
                                    action.status === 'completed' ? 'bg-green-500' :
                                    action.status === 'in_progress' ? 'bg-blue-500' : 'bg-gray-500'
                                  }`}
                                  style={{ width: `${action.progress_percent}%` }}
                                ></div>
                              </div>
                              <span className="text-sm text-gray-400">{action.progress_percent}%</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(action.status)}`}>
                              {action.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Data Quality Tab */}
          {activeTab === 'quality' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  { scope: 'Scope 1 & 2', score: 9, target: 12, status: 'needs_improvement' },
                  { scope: 'Scope 3', score: 8, target: 11, status: 'needs_improvement' },
                  { scope: 'Overall', score: 11, target: 12, status: 'close' },
                ].map((dq) => (
                  <div key={dq.scope} className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                    <h3 className="font-bold text-white mb-4">{dq.scope}</h3>
                    <div className="relative w-32 h-32 mx-auto mb-4">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-700" />
                        <circle
                          cx="64"
                          cy="64"
                          r="56"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="transparent"
                          strokeDasharray={`${(dq.score / 16) * 352} 352`}
                          className={dq.score >= dq.target ? 'text-green-500' : dq.score >= dq.target - 2 ? 'text-yellow-500' : 'text-red-500'}
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-3xl font-bold text-white">{dq.score}</span>
                        <span className="text-sm text-gray-400">/ 16</span>
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-400">Target: ≥{dq.target}/16</div>
                      <div className={`text-sm font-medium mt-1 ${
                        dq.score >= dq.target ? 'text-green-400' : 'text-yellow-400'
                      }`}>
                        {dq.score >= dq.target ? '✓ Met' : `${dq.target - dq.score} points needed`}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">Data Quality Improvement Recommendations</h3>
                </div>
                <div className="p-4 space-y-4">
                  {[
                    { action: 'Complete fuel-card audit for 100% fleet transactions', impact: '+2 points', scope: 'Scope 1', priority: 'high' },
                    { action: 'Install smart electricity meters with auto-upload', impact: '+3 points', scope: 'Scope 2', priority: 'high' },
                    { action: 'Replace estimated gas readings with actual meter reads', impact: '+2 points', scope: 'Scope 1', priority: 'medium' },
                    { action: 'Engage top 10 suppliers for specific emission data', impact: '+2 points', scope: 'Scope 3', priority: 'medium' },
                    { action: 'Implement employee commute survey (annual)', impact: '+1 point', scope: 'Scope 3', priority: 'low' },
                  ].map((rec, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${
                          rec.priority === 'high' ? 'bg-red-500' :
                          rec.priority === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                        }`}></div>
                        <span className="text-white">{rec.action}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-1 bg-slate-600 rounded text-xs text-gray-300">{rec.scope}</span>
                        <span className="text-green-400 font-medium">{rec.impact}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Certification Tab */}
          {activeTab === 'certification' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="p-4 bg-gradient-to-br from-green-500 to-teal-600 rounded-xl">
                      <Award className="w-8 h-8 text-white" />
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-white">Planet Mark Business Certification</h3>
                      <p className="text-gray-400">Year 2 Progress</p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-between items-center p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-gray-300">Certification Status</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor('in_progress')}`}>
                        In Progress
                      </span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-gray-300">Reporting Period</span>
                      <span className="text-white font-medium">1 Jul 2025 - 30 Jun 2026</span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-gray-300">Submission Deadline</span>
                      <span className="text-white font-medium">30 Jun 2026</span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-slate-700/50 rounded-lg">
                      <span className="text-gray-300">Reduction Target</span>
                      <span className="text-green-400 font-medium">≥5% per FTE</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600">
                    <h3 className="font-bold text-white">Evidence Checklist</h3>
                    <p className="text-sm text-gray-400">Required documentation for certification</p>
                  </div>
                  <div className="p-4 space-y-3">
                    {[
                      { item: 'Electricity bills (12 months)', uploaded: true, verified: true },
                      { item: 'Gas bills (12 months)', uploaded: true, verified: false },
                      { item: 'Fleet fuel card statements', uploaded: true, verified: true },
                      { item: 'Waste transfer notes', uploaded: false, verified: false },
                      { item: 'Business travel records', uploaded: true, verified: false },
                      { item: 'Improvement plan evidence', uploaded: true, verified: true },
                    ].map((doc, i) => (
                      <div key={i} className="flex items-center justify-between p-2 bg-slate-700/50 rounded-lg">
                        <div className="flex items-center gap-3">
                          {doc.uploaded ? (
                            <CheckCircle2 className={`w-5 h-5 ${doc.verified ? 'text-green-400' : 'text-yellow-400'}`} />
                          ) : (
                            <AlertTriangle className="w-5 h-5 text-red-400" />
                          )}
                          <span className="text-white text-sm">{doc.item}</span>
                        </div>
                        <span className={`text-xs ${
                          doc.verified ? 'text-green-400' :
                          doc.uploaded ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {doc.verified ? 'Verified' : doc.uploaded ? 'Pending Review' : 'Missing'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
