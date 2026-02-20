import { useState, useEffect, useCallback } from 'react'
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
import { cn } from '../helpers/utils'
import { Button } from '../components/ui/Button'
import { aiApi } from '../api/client'
import { useToast, ToastContainer } from '../components/ui/Toast'

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
  const { toasts, show: _showToast, dismiss: dismissToast } = useToast();
  const [activeTab, setActiveTab] = useState<'predictions' | 'anomalies' | 'audit' | 'recommendations'>('predictions')
  const [analyzing, setAnalyzing] = useState(false)
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [recommendations, setRecommendations] = useState<{ title: string; description: string; priority: string; timeframe: string; responsible: string; confidence: number }[]>([])

  const loadAIData = useCallback(async () => {
    setAnalyzing(true)
    try {
      const [predRes, anomRes, recRes] = await Promise.all([
        aiApi.getPredictions(),
        aiApi.getAnomalies(),
        aiApi.getRecommendations(),
      ])

      const predData = predRes.data as Record<string, unknown>
      if (predData?.predictions) setPredictions(predData.predictions as Prediction[])
      else if (Array.isArray(predData)) setPredictions(predData as Prediction[])

      const anomData = anomRes.data as Record<string, unknown>
      if (anomData?.anomalies) setAnomalies(anomData.anomalies as Anomaly[])
      else if (Array.isArray(anomData)) setAnomalies(anomData as Anomaly[])
      if (anomData?.clusters) setClusters(anomData.clusters as Cluster[])

      const recData = recRes.data as Record<string, unknown>
      if (recData?.recommendations) setRecommendations(recData.recommendations as typeof recommendations)
      else if (Array.isArray(recData)) setRecommendations(recData as typeof recommendations)
    } catch {
      console.error('Failed to load AI data')
    } finally {
      setAnalyzing(false)
    }
  }, [])

  useEffect(() => { loadAIData() }, [loadAIData])

  const auditQuestions = [
    { clause: '6.1', question: 'How are OH&S hazards identified?', type: 'compliance', evidence: ['Risk Assessment', 'Hazard Register'] },
    { clause: '7.2', question: 'How is competence determined for workers affecting OH&S performance?', type: 'compliance', evidence: ['Training Records', 'Competency Matrix'] },
    { clause: '8.1.2', question: 'What is the hierarchy of controls used for risk reduction?', type: 'effectiveness', evidence: ['Control Register', 'Risk Assessments'] },
    { clause: '9.1', question: 'What OH&S performance indicators are monitored?', type: 'compliance', evidence: ['KPI Dashboard', 'Performance Reports'] },
    { clause: '10.2', question: 'What is the process for incident investigation?', type: 'compliance', evidence: ['Investigation Procedure', 'Incident Reports'] },
  ]

  const handleAnalyze = () => {
    loadAIData()
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center gap-3">
            <Brain className="w-8 h-8 text-primary" />
            AI Intelligence Hub
          </h1>
          <p className="text-muted-foreground">Predictive Analytics & Smart Recommendations</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <Button
            onClick={handleAnalyze}
            disabled={analyzing}
          >
            {analyzing ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Run Analysis
              </>
            )}
          </Button>
        </div>
      </div>

      {/* AI Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-card border border-border rounded-xl p-4 hover:border-border-strong transition-colors">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Zap className="w-5 h-5 text-purple-500" />
            </div>
            <span className="text-2xl font-bold text-foreground">5</span>
          </div>
          <p className="text-sm text-muted-foreground">Risk Predictions</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 hover:border-border-strong transition-colors">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <span className="text-2xl font-bold text-foreground">3</span>
          </div>
          <p className="text-sm text-muted-foreground">Anomalies Detected</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 hover:border-border-strong transition-colors">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
              <Layers className="w-5 h-5 text-info" />
            </div>
            <span className="text-2xl font-bold text-foreground">4</span>
          </div>
          <p className="text-sm text-muted-foreground">Incident Clusters</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 hover:border-border-strong transition-colors">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
              <Lightbulb className="w-5 h-5 text-success" />
            </div>
            <span className="text-2xl font-bold text-foreground">4</span>
          </div>
          <p className="text-sm text-muted-foreground">Recommendations</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border pb-2 overflow-x-auto">
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
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap",
                activeTab === tab.id
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
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
          <div className="bg-card rounded-xl border border-border">
            <div className="p-4 border-b border-border">
              <h3 className="font-bold text-foreground flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                Predictive Risk Factors
              </h3>
              <p className="text-sm text-muted-foreground">Based on 365 days of incident data</p>
            </div>
            <div className="p-4 space-y-4">
              {predictions.map((pred, i) => (
                <div key={i} className="p-4 bg-surface rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground uppercase">{pred.factor_type}</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                          pred.risk_level === 'high'
                            ? 'bg-destructive/10 text-destructive border-destructive/20'
                            : pred.risk_level === 'medium'
                            ? 'bg-warning/10 text-warning border-warning/20'
                            : 'bg-success/10 text-success border-success/20'
                        }`}
                      >
                        {pred.risk_level}
                      </span>
                    </div>
                    <span className="text-foreground font-bold">{pred.percentage}%</span>
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

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
