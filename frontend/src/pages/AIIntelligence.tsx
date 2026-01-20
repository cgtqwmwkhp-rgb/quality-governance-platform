import { useState } from 'react'
import {
  Brain,
  Zap,
  TrendingUp,
  AlertTriangle,
  Lightbulb,
  Target,
  BarChart3,
  GitBranch,
  Shield,
  FileText,
  Sparkles,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  Layers,
  MessageSquare,
  Eye,
} from 'lucide-react'

interface Prediction {
  factor_type: string
  factor_value: string
  incident_count?: number
  percentage?: number
  risk_level: string
  high_risk_hours?: number[]
}

interface Anomaly {
  type: string
  category?: string
  day?: string
  percentage: number
  count: number
  message: string
}

interface Cluster {
  category: string
  incident_count: number
  departments_affected: string[]
  priority: string
  suggested_action: string
}

export default function AIIntelligence() {
  const [activeTab, setActiveTab] = useState<'predictions' | 'anomalies' | 'audit' | 'recommendations'>('predictions')
  const [analyzing, setAnalyzing] = useState(false)

  const predictions: Prediction[] = [
    { factor_type: 'department', factor_value: 'Operations', incident_count: 45, percentage: 32.1, risk_level: 'high' },
    { factor_type: 'department', factor_value: 'Field Services', incident_count: 28, percentage: 20.0, risk_level: 'medium' },
    { factor_type: 'department', factor_value: 'Warehouse', incident_count: 22, percentage: 15.7, risk_level: 'medium' },
    { factor_type: 'time_of_day', factor_value: '06:00 - 10:00', high_risk_hours: [6, 7, 8, 9], risk_level: 'medium' },
    { factor_type: 'seasonal', factor_value: 'January', incident_count: 18, risk_level: 'low' },
  ]

  const anomalies: Anomaly[] = [
    { type: 'category_clustering', category: 'Manual Handling', percentage: 42.5, count: 17, message: '42.5% of incidents are Manual Handling - investigate root cause' },
    { type: 'day_clustering', day: 'Monday', percentage: 31.2, count: 12, message: '31.2% of incidents occur on Mondays' },
    { type: 'frequency_spike', category: 'Operations', percentage: 180, count: 9, message: 'Operations department showing 180% above average incident rate' },
  ]

  const clusters: Cluster[] = [
    { category: 'manual_handling', incident_count: 17, departments_affected: ['Operations', 'Warehouse'], priority: 'high', suggested_action: 'Investigate systemic causes of manual handling incidents' },
    { category: 'slips_trips_falls', incident_count: 12, departments_affected: ['Field Services', 'Warehouse'], priority: 'high', suggested_action: 'Review floor conditions and housekeeping procedures' },
    { category: 'vehicle_incident', incident_count: 8, departments_affected: ['Field Services', 'Logistics'], priority: 'medium', suggested_action: 'Review driving standards and telematics data' },
    { category: 'working_at_height', incident_count: 5, departments_affected: ['Operations'], priority: 'medium', suggested_action: 'Review work at height procedures and equipment' },
  ]

  const auditQuestions = [
    { clause: '6.1', question: 'How are OH&S hazards identified?', type: 'compliance', evidence: ['Risk Assessment', 'Hazard Register'] },
    { clause: '7.2', question: 'How is competence determined for workers affecting OH&S performance?', type: 'compliance', evidence: ['Training Records', 'Competency Matrix'] },
    { clause: '8.1.2', question: 'What is the hierarchy of controls used for risk reduction?', type: 'effectiveness', evidence: ['Control Register', 'Risk Assessments'] },
    { clause: '9.1', question: 'What OH&S performance indicators are monitored?', type: 'compliance', evidence: ['KPI Dashboard', 'Performance Reports'] },
    { clause: '10.2', question: 'What is the process for incident investigation?', type: 'compliance', evidence: ['Investigation Procedure', 'Incident Reports'] },
  ]

  const recommendations = [
    {
      title: 'Implement Ergonomic Assessment Program',
      description: 'Based on high manual handling incidents, implement a formal ergonomic assessment for all high-risk tasks',
      priority: 'high',
      timeframe: '2 weeks',
      responsible: 'H&S Manager',
      confidence: 92,
    },
    {
      title: 'Enhanced Monday Toolbox Talks',
      description: 'Incident clustering on Mondays suggests need for enhanced safety briefings at week start',
      priority: 'medium',
      timeframe: '1 week',
      responsible: 'Team Leaders',
      confidence: 85,
    },
    {
      title: 'Operations Department Safety Blitz',
      description: 'Focused safety intervention for Operations due to elevated incident rate',
      priority: 'high',
      timeframe: 'Immediate',
      responsible: 'Operations Manager',
      confidence: 88,
    },
    {
      title: 'Slip Hazard Audit',
      description: 'Conduct comprehensive slip hazard assessment in Field Services and Warehouse',
      priority: 'medium',
      timeframe: '1 month',
      responsible: 'Facilities Team',
      confidence: 78,
    },
  ]

  const handleAnalyze = () => {
    setAnalyzing(true)
    setTimeout(() => setAnalyzing(false), 2000)
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
            <Brain className="w-8 h-8 text-purple-400" />
            AI Intelligence Hub
          </h1>
          <p className="text-gray-400">Predictive Analytics & Smart Recommendations</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {analyzing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Run Analysis
              </>
            )}
          </button>
        </div>
      </div>

      {/* AI Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-gradient-to-br from-purple-600 to-purple-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-5 h-5 text-purple-200" />
            <span className="text-2xl font-bold text-white">5</span>
          </div>
          <p className="text-sm text-purple-200">Risk Predictions</p>
        </div>

        <div className="bg-gradient-to-br from-red-600 to-red-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-200" />
            <span className="text-2xl font-bold text-white">3</span>
          </div>
          <p className="text-sm text-red-200">Anomalies Detected</p>
        </div>

        <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <Layers className="w-5 h-5 text-blue-200" />
            <span className="text-2xl font-bold text-white">4</span>
          </div>
          <p className="text-sm text-blue-200">Incident Clusters</p>
        </div>

        <div className="bg-gradient-to-br from-emerald-600 to-emerald-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <Lightbulb className="w-5 h-5 text-emerald-200" />
            <span className="text-2xl font-bold text-white">4</span>
          </div>
          <p className="text-sm text-emerald-200">Recommendations</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-slate-700 pb-2 overflow-x-auto">
        {[
          { id: 'predictions', label: 'Risk Predictions', icon: TrendingUp },
          { id: 'anomalies', label: 'Anomaly Detection', icon: AlertTriangle },
          { id: 'audit', label: 'AI Audit Assistant', icon: FileText },
          { id: 'recommendations', label: 'Smart Recommendations', icon: Lightbulb },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white'
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
      {activeTab === 'predictions' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Risk Factor Analysis */}
          <div className="bg-slate-800 rounded-xl border border-slate-700">
            <div className="p-4 border-b border-slate-700">
              <h3 className="font-bold text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-purple-400" />
                Predictive Risk Factors
              </h3>
              <p className="text-sm text-gray-400">Based on 365 days of incident data</p>
            </div>
            <div className="p-4 space-y-4">
              {predictions.map((pred, i) => (
                <div key={i} className="p-4 bg-slate-700/50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 uppercase">{pred.factor_type}</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          pred.risk_level === 'high'
                            ? 'bg-red-500/20 text-red-400'
                            : pred.risk_level === 'medium'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-green-500/20 text-green-400'
                        }`}
                      >
                        {pred.risk_level}
                      </span>
                    </div>
                    <span className="text-white font-bold">{pred.percentage}%</span>
                  </div>
                  <div className="text-lg font-semibold text-white">{pred.factor_value}</div>
                  {pred.incident_count && (
                    <div className="text-sm text-gray-400 mt-1">{pred.incident_count} incidents</div>
                  )}
                  <div className="w-full bg-slate-600 rounded-full h-2 mt-2">
                    <div
                      className={`h-2 rounded-full ${
                        pred.risk_level === 'high'
                          ? 'bg-red-500'
                          : pred.risk_level === 'medium'
                          ? 'bg-yellow-500'
                          : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(pred.percentage ?? 0, 100)}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Incident Clusters */}
          <div className="bg-slate-800 rounded-xl border border-slate-700">
            <div className="p-4 border-b border-slate-700">
              <h3 className="font-bold text-white flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-blue-400" />
                Root Cause Clusters
              </h3>
              <p className="text-sm text-gray-400">Similar incidents grouped for systemic analysis</p>
            </div>
            <div className="p-4 space-y-4">
              {clusters.map((cluster, i) => (
                <div
                  key={i}
                  className="p-4 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        cluster.priority === 'high'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}
                    >
                      {cluster.priority} priority
                    </span>
                    <span className="text-2xl font-bold text-white">{cluster.incident_count}</span>
                  </div>
                  <div className="text-lg font-semibold text-white mb-1">
                    {cluster.category.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                  </div>
                  <div className="text-sm text-gray-400 mb-2">
                    Departments: {cluster.departments_affected.join(', ')}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-purple-400">
                    <Lightbulb className="w-4 h-4" />
                    {cluster.suggested_action}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'anomalies' && (
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          <div className="p-4 border-b border-slate-700">
            <h3 className="font-bold text-white flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              Detected Anomalies
            </h3>
            <p className="text-sm text-gray-400">Unusual patterns requiring attention</p>
          </div>
          <div className="p-4 space-y-4">
            {anomalies.map((anomaly, i) => (
              <div
                key={i}
                className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-red-500/20 rounded-lg">
                    <AlertTriangle className="w-6 h-6 text-red-400" />
                  </div>
                  <div className="flex-grow">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-gray-400 uppercase">
                        {anomaly.type.replace(/_/g, ' ')}
                      </span>
                      <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs font-medium">
                        {anomaly.count} occurrences
                      </span>
                    </div>
                    <p className="text-white font-medium mb-2">{anomaly.message}</p>
                    <div className="flex gap-3">
                      <button className="text-sm text-purple-400 hover:text-purple-300 flex items-center gap-1">
                        <Eye className="w-4 h-4" />
                        View Details
                      </button>
                      <button className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
                        <Target className="w-4 h-4" />
                        Create Action
                      </button>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-red-400">{anomaly.percentage}%</div>
                    <div className="text-xs text-gray-400">above normal</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* AI Generated Questions */}
          <div className="bg-slate-800 rounded-xl border border-slate-700">
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-white flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-blue-400" />
                  AI-Generated Audit Questions
                </h3>
                <p className="text-sm text-gray-400">ISO 45001 Clause Coverage</p>
              </div>
              <button className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm">
                Generate More
              </button>
            </div>
            <div className="p-4 space-y-3">
              {auditQuestions.map((q, i) => (
                <div key={i} className="p-3 bg-slate-700/50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs font-mono">
                      {q.clause}
                    </span>
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                      {q.type}
                    </span>
                  </div>
                  <p className="text-white text-sm mb-2">{q.question}</p>
                  <div className="flex flex-wrap gap-1">
                    {q.evidence.map((e, j) => (
                      <span key={j} className="px-2 py-0.5 bg-slate-600 text-gray-300 rounded text-xs">
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Audit Insights */}
          <div className="space-y-6">
            <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
              <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-emerald-400" />
                Finding Trends
              </h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Major NCs (Last 12 months)</span>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-bold text-white">0</span>
                    <span className="text-emerald-400 text-sm">↓ -2</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Minor NCs (Last 12 months)</span>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-bold text-white">6</span>
                    <span className="text-emerald-400 text-sm">↓ -4</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Recurring Findings</span>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-bold text-yellow-400">2</span>
                    <span className="text-gray-400 text-sm">—</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Trend Direction</span>
                  <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm font-medium">
                    Improving
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
              <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                <Shield className="w-5 h-5 text-purple-400" />
                Evidence Gap Analysis
              </h3>
              <div className="space-y-3">
                {[
                  { clause: '7.2', gap: 'Training records incomplete for 3 new starters', severity: 'minor' },
                  { clause: '8.1.2', gap: 'Control effectiveness review overdue', severity: 'minor' },
                ].map((gap, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-yellow-400">{gap.clause}</span>
                        <span className="text-xs text-gray-400">{gap.severity}</span>
                      </div>
                      <p className="text-white text-sm">{gap.gap}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'recommendations' && (
        <div className="space-y-4">
          {recommendations.map((rec, i) => (
            <div
              key={i}
              className="bg-slate-800 rounded-xl border border-slate-700 p-6 hover:border-purple-500/50 transition-colors"
            >
              <div className="flex items-start gap-4">
                <div
                  className={`p-3 rounded-lg ${
                    rec.priority === 'high' ? 'bg-red-500/20' : 'bg-yellow-500/20'
                  }`}
                >
                  <Lightbulb
                    className={`w-6 h-6 ${
                      rec.priority === 'high' ? 'text-red-400' : 'text-yellow-400'
                    }`}
                  />
                </div>
                <div className="flex-grow">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        rec.priority === 'high'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}
                    >
                      {rec.priority} priority
                    </span>
                    <span className="text-xs text-gray-400">
                      <Clock className="w-3 h-3 inline-block mr-1" />
                      {rec.timeframe}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white mb-1">{rec.title}</h3>
                  <p className="text-gray-400 text-sm mb-3">{rec.description}</p>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-400">
                      Assigned to: <span className="text-white">{rec.responsible}</span>
                    </span>
                    <span className="text-sm text-gray-400">
                      AI Confidence:{' '}
                      <span className="text-purple-400 font-medium">{rec.confidence}%</span>
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    Accept
                  </button>
                  <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                    <XCircle className="w-4 h-4" />
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
