/**
 * Advanced Analytics Dashboard
 * 
 * Features:
 * - Interactive drill-down charts
 * - Trend forecasting with confidence intervals
 * - Benchmark comparisons
 * - Cost analysis
 * - ROI tracking
 */

import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Target,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
  Download,
  RefreshCw,
  Award,
  AlertTriangle,
  CheckCircle,
  Shield,
  Zap,
  Building,
  Globe,
  Percent,
  Coins,
  PiggyBank,
  Activity,
  Eye,
  X,
} from 'lucide-react';
import { cn } from '../helpers/utils';
import { Button } from '../components/ui/Button';

interface KPIData {
  incidents: { total: number; open: number; closed: number; trend: number; avg_resolution_days: number };
  actions: { total: number; open: number; overdue: number; completed_on_time_rate: number; trend: number };
  audits: { total: number; completed: number; in_progress: number; avg_score: number; trend: number };
  risks: { total: number; high: number; medium: number; low: number; mitigated: number };
  compliance: { overall_score: number; iso_9001: number; iso_14001: number; iso_45001: number };
  training: { completion_rate: number; expiring_soon: number; overdue: number };
}

interface BenchmarkData {
  your_value: number;
  industry_average: number;
  industry_median: number;
  percentile_25: number;
  percentile_75: number;
  percentile_90: number;
  your_percentile: number;
  trend: string;
}

interface CostData {
  total_cost: number;
  breakdown: {
    incident_costs: { amount: number; count: number };
    regulatory_fines: { amount: number; count: number };
    legal_costs: { amount: number; count: number };
    remediation: { amount: number; count: number };
    productivity_loss: { amount: number };
  };
  trend: { vs_previous_period: number; direction: string };
}

interface ROIData {
  investments: Array<{
    id: number;
    name: string;
    category: string;
    investment: number;
    annual_savings: number;
    incidents_prevented: number;
    roi_percentage: number;
    payback_months: number;
  }>;
  summary: {
    total_investment: number;
    total_annual_savings: number;
    total_incidents_prevented: number;
    overall_roi: number;
  };
}

const timeRanges = [
  { value: 'last_7_days', label: 'Last 7 Days' },
  { value: 'last_30_days', label: 'Last 30 Days' },
  { value: 'last_90_days', label: 'Last 90 Days' },
  { value: 'last_12_months', label: 'Last 12 Months' },
  { value: 'year_to_date', label: 'Year to Date' },
];

export default function AdvancedAnalytics() {
  const [timeRange, setTimeRange] = useState('last_30_days');
  const [activeTab, setActiveTab] = useState<'overview' | 'trends' | 'benchmarks' | 'costs' | 'roi'>('overview');
  const [kpis, setKpis] = useState<KPIData | null>(null);
  const [benchmarks, setBenchmarks] = useState<Record<string, BenchmarkData>>({});
  const [costs, setCosts] = useState<CostData | null>(null);
  const [roi, setRoi] = useState<ROIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [drillDownOpen, setDrillDownOpen] = useState(false);
  const [drillDownData, setDrillDownData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [timeRange]);

  const loadData = async () => {
    setLoading(true);
    // Simulate API calls
    await new Promise(resolve => setTimeout(resolve, 500));
    
    setKpis({
      incidents: { total: 47, open: 12, closed: 35, trend: -8.5, avg_resolution_days: 4.2 },
      actions: { total: 156, open: 34, overdue: 8, completed_on_time_rate: 87.5, trend: 12.3 },
      audits: { total: 23, completed: 18, in_progress: 5, avg_score: 89.4, trend: 3.2 },
      risks: { total: 89, high: 12, medium: 34, low: 43, mitigated: 67 },
      compliance: { overall_score: 94.2, iso_9001: 96.1, iso_14001: 92.8, iso_45001: 93.7 },
      training: { completion_rate: 91.2, expiring_soon: 14, overdue: 3 },
    });

    setBenchmarks({
      incident_rate: { your_value: 2.3, industry_average: 3.8, industry_median: 3.5, percentile_25: 4.2, percentile_75: 2.8, percentile_90: 1.9, your_percentile: 72, trend: 'improving' },
      audit_score: { your_value: 89.4, industry_average: 82.1, industry_median: 83.5, percentile_25: 78.0, percentile_75: 88.0, percentile_90: 92.5, your_percentile: 78, trend: 'stable' },
      action_completion_rate: { your_value: 87.5, industry_average: 79.2, industry_median: 81.0, percentile_25: 72.0, percentile_75: 86.0, percentile_90: 93.0, your_percentile: 76, trend: 'improving' },
    });

    setCosts({
      total_cost: 127500,
      breakdown: {
        incident_costs: { amount: 45000, count: 47 },
        regulatory_fines: { amount: 25000, count: 2 },
        legal_costs: { amount: 15000, count: 3 },
        remediation: { amount: 22500, count: 8 },
        productivity_loss: { amount: 20000 },
      },
      trend: { vs_previous_period: -12.5, direction: 'improving' },
    });

    setRoi({
      investments: [
        { id: 1, name: 'Safety Management System', category: 'technology', investment: 50000, annual_savings: 35000, incidents_prevented: 12, roi_percentage: 70, payback_months: 17 },
        { id: 2, name: 'Enhanced PPE Program', category: 'equipment', investment: 25000, annual_savings: 18000, incidents_prevented: 8, roi_percentage: 72, payback_months: 17 },
        { id: 3, name: 'Comprehensive Training', category: 'training', investment: 40000, annual_savings: 28000, incidents_prevented: 15, roi_percentage: 70, payback_months: 17 },
      ],
      summary: { total_investment: 115000, total_annual_savings: 81000, total_incidents_prevented: 35, overall_roi: 70.4 },
    });

    setLoading(false);
  };

  const handleDrillDown = (metric: string, dimension: string, value: string) => {
    setDrillDownData({
      metric,
      dimension,
      value,
      records: [
        { id: 'INC-001', title: 'Slip and fall incident', date: '2026-01-15', status: 'closed', severity: 'medium' },
        { id: 'INC-002', title: 'Near miss - falling object', date: '2026-01-12', status: 'closed', severity: 'low' },
        { id: 'INC-003', title: 'Equipment malfunction', date: '2026-01-10', status: 'open', severity: 'high' },
      ],
    });
    setDrillDownOpen(true);
  };

  const KPICard = ({ 
    title, 
    value, 
    subtitle, 
    trend,
    icon: Icon, 
    color,
    onClick 
  }: { 
    title: string; 
    value: string | number; 
    subtitle?: string;
    trend?: number; 
    trendLabel?: string;
    icon: React.ElementType; 
    color: string;
    onClick?: () => void;
  }) => (
    <div 
      className={`bg-card/50 backdrop-blur-sm border border-border rounded-xl p-5 hover:border-primary/50 transition-all cursor-pointer group`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-lg bg-${color}-500/20`}>
          <Icon className={`w-5 h-5 text-${color}-400`} />
        </div>
        {trend !== undefined && (
          <div className={`flex items-center gap-1 text-sm ${trend >= 0 ? 'text-success' : 'text-destructive'}`}>
            {trend >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
            <span>{Math.abs(trend)}%</span>
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-foreground mb-1">{value}</div>
      <div className="text-sm text-muted-foreground">{title}</div>
      {subtitle && <div className="text-xs text-muted-foreground/70 mt-1">{subtitle}</div>}
      <div className="flex items-center gap-1 mt-3 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
        <Eye className="w-3 h-3" />
        <span>Click to drill down</span>
      </div>
    </div>
  );

  const TrendChart = ({ data, title, color = '#10B981' }: { data: number[]; title: string; color?: string }) => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    
    return (
      <div className="bg-card/50 border border-border rounded-xl p-5">
        <h3 className="text-lg font-semibold text-foreground mb-4">{title}</h3>
        <div className="h-32 flex items-end gap-1">
          {data.map((value, i) => (
            <div
              key={i}
              className="flex-1 rounded-t transition-all hover:opacity-80 cursor-pointer"
              style={{
                height: `${((value - min) / range) * 100}%`,
                backgroundColor: color,
                minHeight: '4px',
              }}
              title={`Value: ${value}`}
            />
          ))}
        </div>
        <div className="flex justify-between mt-2 text-xs text-muted-foreground">
          <span>30 days ago</span>
          <span>Today</span>
        </div>
      </div>
    );
  };

  const BenchmarkGauge = ({ metric, data }: { metric: string; data: BenchmarkData }) => {
    const position = (data.your_percentile / 100) * 100;
    
    return (
      <div className="bg-card/50 border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground capitalize">{metric.replace(/_/g, ' ')}</h3>
          <span className={`px-2 py-1 rounded text-xs font-medium ${
            data.trend === 'improving' ? 'bg-success/10 text-success' :
            data.trend === 'stable' ? 'bg-info/10 text-info' :
            'bg-destructive/10 text-destructive'
          }`}>
            {data.trend}
          </span>
        </div>
        
        {/* Gauge */}
        <div className="relative h-8 bg-surface rounded-full overflow-hidden mb-4">
          <div className="absolute inset-0 flex">
            <div className="w-1/4 bg-destructive/30" />
            <div className="w-1/4 bg-warning/30" />
            <div className="w-1/4 bg-info/30" />
            <div className="w-1/4 bg-success/30" />
          </div>
          <div 
            className="absolute top-0 bottom-0 w-1 bg-foreground shadow-lg transition-all"
            style={{ left: `${position}%` }}
          />
        </div>
        
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Your Value:</span>
            <span className="text-foreground font-semibold ml-2">{data.your_value}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Industry Avg:</span>
            <span className="text-foreground font-semibold ml-2">{data.industry_average}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Percentile:</span>
            <span className="text-success font-semibold ml-2">{data.your_percentile}th</span>
          </div>
          <div>
            <span className="text-muted-foreground">Top 10%:</span>
            <span className="text-foreground font-semibold ml-2">{data.percentile_90}</span>
          </div>
        </div>
      </div>
    );
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'trends', label: 'Trends & Forecast', icon: TrendingUp },
    { id: 'benchmarks', label: 'Benchmarks', icon: Target },
    { id: 'costs', label: 'Cost Analysis', icon: DollarSign },
    { id: 'roi', label: 'ROI Tracking', icon: PiggyBank },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Advanced Analytics</h1>
          <p className="text-muted-foreground mt-1">Interactive insights with forecasting and benchmarks</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-background border border-border rounded-lg px-4 py-2 text-foreground text-sm focus:ring-2 focus:ring-primary/50"
          >
            {timeRanges.map(range => (
              <option key={range.value} value={range.value}>{range.label}</option>
            ))}
          </select>
          <Button 
            onClick={loadData}
            variant="outline"
            size="icon"
          >
            <RefreshCw className="w-5 h-5" />
          </Button>
          <Button>
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-card/50 p-1 rounded-xl border border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && kpis && (
        <div className="space-y-6">
          {/* KPI Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Total Incidents"
              value={kpis.incidents.total}
              subtitle={`${kpis.incidents.open} open, ${kpis.incidents.closed} closed`}
              trend={kpis.incidents.trend}
              icon={AlertTriangle}
              color="red"
              onClick={() => handleDrillDown('incidents', 'status', 'all')}
            />
            <KPICard
              title="Actions"
              value={kpis.actions.total}
              subtitle={`${kpis.actions.overdue} overdue`}
              trend={kpis.actions.trend}
              icon={CheckCircle}
              color="blue"
              onClick={() => handleDrillDown('actions', 'status', 'all')}
            />
            <KPICard
              title="Audit Score"
              value={`${kpis.audits.avg_score}%`}
              subtitle={`${kpis.audits.completed} completed`}
              trend={kpis.audits.trend}
              icon={Shield}
              color="purple"
              onClick={() => handleDrillDown('audits', 'status', 'all')}
            />
            <KPICard
              title="Compliance"
              value={`${kpis.compliance.overall_score}%`}
              subtitle="Overall score"
              icon={Award}
              color="emerald"
              onClick={() => handleDrillDown('compliance', 'standard', 'all')}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TrendChart
              title="Incident Trend (30 days)"
              data={[8, 12, 7, 15, 10, 8, 11, 9, 6, 13, 8, 7, 10, 12, 9, 8, 11, 7, 9, 10, 8, 6, 9, 11, 8, 7, 10, 9, 8, 7]}
              color="#EF4444"
            />
            <TrendChart
              title="Action Completion Rate (%)"
              data={[82, 85, 84, 86, 88, 87, 89, 88, 90, 89, 91, 88, 90, 92, 89, 91, 90, 88, 91, 93, 90, 92, 89, 91, 90, 88, 91, 89, 90, 88]}
              color="#10B981"
            />
          </div>

          {/* Risk Distribution */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-white mb-4">Risk Distribution</h3>
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">High Risk</span>
                  <span className="text-sm font-semibold text-red-400">{kpis.risks.high}</span>
                </div>
                <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-red-500 rounded-full" 
                    style={{ width: `${(kpis.risks.high / kpis.risks.total) * 100}%` }}
                  />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">Medium Risk</span>
                  <span className="text-sm font-semibold text-yellow-400">{kpis.risks.medium}</span>
                </div>
                <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-yellow-500 rounded-full" 
                    style={{ width: `${(kpis.risks.medium / kpis.risks.total) * 100}%` }}
                  />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">Low Risk</span>
                  <span className="text-sm font-semibold text-emerald-400">{kpis.risks.low}</span>
                </div>
                <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-emerald-500 rounded-full" 
                    style={{ width: `${(kpis.risks.low / kpis.risks.total) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* ISO Compliance */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-white mb-4">ISO Compliance Scores</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                { standard: 'ISO 9001', score: kpis.compliance.iso_9001, color: 'blue' },
                { standard: 'ISO 14001', score: kpis.compliance.iso_14001, color: 'green' },
                { standard: 'ISO 45001', score: kpis.compliance.iso_45001, color: 'purple' },
              ].map(item => (
                <div key={item.standard} className="text-center">
                  <div className="relative w-24 h-24 mx-auto mb-3">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle cx="48" cy="48" r="40" stroke="#334155" strokeWidth="8" fill="none" />
                      <circle 
                        cx="48" cy="48" r="40" 
                        stroke={item.color === 'blue' ? '#3B82F6' : item.color === 'green' ? '#10B981' : '#8B5CF6'}
                        strokeWidth="8" 
                        fill="none"
                        strokeDasharray={`${(item.score / 100) * 251.2} 251.2`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xl font-bold text-white">{item.score}%</span>
                    </div>
                  </div>
                  <div className="text-sm font-medium text-gray-300">{item.standard}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Trends Tab */}
      {activeTab === 'trends' && (
        <div className="space-y-6">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Incident Forecast (Next 12 Periods)</h3>
            <div className="h-64 flex items-end gap-1">
              {/* Historical */}
              {[8, 12, 7, 15, 10, 8, 11, 9, 6, 13, 8, 7].map((value, i) => (
                <div key={`hist-${i}`} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-blue-500 rounded-t transition-all"
                    style={{ height: `${(value / 20) * 100}%` }}
                  />
                </div>
              ))}
              {/* Forecast */}
              {[7, 6, 6, 5, 5, 5, 4, 4, 4, 4, 3, 3].map((value, i) => (
                <div key={`fore-${i}`} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-emerald-500/50 border-2 border-dashed border-emerald-500 rounded-t transition-all"
                    style={{ height: `${(value / 20) * 100}%` }}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-500 rounded" />
                <span className="text-sm text-gray-400">Historical</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-emerald-500/50 border-2 border-dashed border-emerald-500 rounded" />
                <span className="text-sm text-gray-400">Forecast (95% CI)</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <h3 className="text-lg font-semibold text-white mb-4">Forecast Summary</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Trend Direction</span>
                  <span className="flex items-center gap-2 text-emerald-400">
                    <TrendingDown className="w-4 h-4" />
                    Decreasing
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Predicted 3-month</span>
                  <span className="text-white font-semibold">18 incidents</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Confidence Level</span>
                  <span className="text-white font-semibold">95%</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Prediction Range</span>
                  <span className="text-white font-semibold">15 - 21 incidents</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <h3 className="text-lg font-semibold text-white mb-4">AI Insights</h3>
              <div className="space-y-3">
                <div className="flex gap-3 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                  <Zap className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                  <p className="text-sm text-gray-300">
                    <strong className="text-emerald-400">Positive Trend:</strong> Incident rate shows consistent 
                    improvement over the last 90 days, with a projected 25% reduction by Q2.
                  </p>
                </div>
                <div className="flex gap-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                  <p className="text-sm text-gray-300">
                    <strong className="text-yellow-400">Seasonal Pattern:</strong> Historical data suggests 
                    increased incidents during winter months. Consider enhanced training.
                  </p>
                </div>
                <div className="flex gap-3 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <Activity className="w-5 h-5 text-blue-400 flex-shrink-0" />
                  <p className="text-sm text-gray-300">
                    <strong className="text-blue-400">Correlation Found:</strong> Strong correlation between 
                    training completion rates and incident reduction (r=0.82).
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Benchmarks Tab */}
      {activeTab === 'benchmarks' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Building className="w-5 h-5 text-gray-400" />
                <select className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm">
                  <option value="utilities">Utilities Industry</option>
                  <option value="construction">Construction</option>
                  <option value="manufacturing">Manufacturing</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <Globe className="w-5 h-5 text-gray-400" />
                <select className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm">
                  <option value="uk">United Kingdom</option>
                  <option value="eu">Europe</option>
                  <option value="global">Global</option>
                </select>
              </div>
            </div>
          </div>

          {/* Overall Performance */}
          <div className="bg-gradient-to-r from-emerald-600/20 to-blue-600/20 border border-emerald-500/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-white">Overall Performance Rating</h3>
                <p className="text-gray-400 mt-1">Compared to industry peers</p>
              </div>
              <div className="text-right">
                <div className="text-4xl font-bold text-emerald-400">75th</div>
                <div className="text-gray-400">Percentile</div>
              </div>
            </div>
            <div className="mt-4 flex items-center gap-4">
              <Award className="w-8 h-8 text-yellow-400" />
              <span className="text-lg font-semibold text-white">Good Performance</span>
              <span className="text-gray-400">|</span>
              <span className="text-gray-300">3 of 4 metrics above industry average</span>
            </div>
          </div>

          {/* Benchmark Gauges */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {Object.entries(benchmarks).map(([metric, data]) => (
              <BenchmarkGauge key={metric} metric={metric} data={data} />
            ))}
          </div>

          {/* Comparison Table */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
            <div className="p-5 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">Detailed Comparison</h3>
            </div>
            <table className="w-full">
              <thead className="bg-slate-700/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-gray-400">Metric</th>
                  <th className="text-center p-4 text-sm font-medium text-gray-400">Your Value</th>
                  <th className="text-center p-4 text-sm font-medium text-gray-400">Industry Avg</th>
                  <th className="text-center p-4 text-sm font-medium text-gray-400">Top 10%</th>
                  <th className="text-center p-4 text-sm font-medium text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(benchmarks).map(([metric, data]) => (
                  <tr key={metric} className="border-t border-slate-700">
                    <td className="p-4 text-white capitalize">{metric.replace(/_/g, ' ')}</td>
                    <td className="p-4 text-center text-emerald-400 font-semibold">{data.your_value}</td>
                    <td className="p-4 text-center text-gray-300">{data.industry_average}</td>
                    <td className="p-4 text-center text-gray-300">{data.percentile_90}</td>
                    <td className="p-4 text-center">
                      {data.your_value > data.industry_average ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                          <ArrowUpRight className="w-3 h-3" /> Above Avg
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">
                          <ArrowDownRight className="w-3 h-3" /> Below Avg
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Costs Tab */}
      {activeTab === 'costs' && costs && (
        <div className="space-y-6">
          {/* Total Cost */}
          <div className="bg-gradient-to-r from-red-600/20 to-orange-600/20 border border-red-500/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-300">Total Cost of Non-Compliance</h3>
                <div className="text-4xl font-bold text-white mt-2">
                  £{costs.total_cost.toLocaleString()}
                </div>
                <p className="text-gray-400 mt-1">Last 12 months</p>
              </div>
              <div className="text-right">
                <div className={`flex items-center gap-2 text-lg ${costs.trend.vs_previous_period < 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {costs.trend.vs_previous_period < 0 ? <TrendingDown className="w-5 h-5" /> : <TrendingUp className="w-5 h-5" />}
                  {Math.abs(costs.trend.vs_previous_period)}%
                </div>
                <p className="text-gray-400 text-sm">vs previous period</p>
              </div>
            </div>
          </div>

          {/* Cost Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <h3 className="text-lg font-semibold text-white mb-4">Cost Breakdown</h3>
              <div className="space-y-4">
                {Object.entries(costs.breakdown).map(([key, data]) => {
                  const amount = 'amount' in data ? data.amount : 0;
                  const percentage = (amount / costs.total_cost) * 100;
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-gray-300 capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="text-white font-semibold">£{amount.toLocaleString()}</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-red-500 to-orange-500 rounded-full"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <h3 className="text-lg font-semibold text-white mb-4">Cost Calculator</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Average Cost per Incident</span>
                  <span className="text-white font-semibold">£{Math.round(costs.breakdown.incident_costs.amount / costs.breakdown.incident_costs.count).toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Cost per Employee</span>
                  <span className="text-white font-semibold">£425</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                  <span className="text-gray-300">Projected Annual Cost</span>
                  <span className="text-white font-semibold">£145,000</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                  <span className="text-gray-300">Potential Savings (with improvements)</span>
                  <span className="text-emerald-400 font-semibold">£35,000</span>
                </div>
              </div>
            </div>
          </div>

          {/* Recommendations */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-white mb-4">Cost Reduction Recommendations</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full" />
                  <span className="text-gray-300">Implement additional safety training</span>
                </div>
                <span className="text-emerald-400 font-semibold">Save £15,000/year</span>
              </div>
              <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full" />
                  <span className="text-gray-300">Automate compliance monitoring</span>
                </div>
                <span className="text-emerald-400 font-semibold">Save £12,000/year</span>
              </div>
              <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-yellow-500 rounded-full" />
                  <span className="text-gray-300">Upgrade PPE equipment</span>
                </div>
                <span className="text-emerald-400 font-semibold">Save £8,000/year</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ROI Tab */}
      {activeTab === 'roi' && roi && (
        <div className="space-y-6">
          {/* ROI Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-blue-500/20">
                  <Coins className="w-5 h-5 text-blue-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-white">£{roi.summary.total_investment.toLocaleString()}</div>
              <div className="text-sm text-gray-400">Total Investment</div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-emerald-500/20">
                  <PiggyBank className="w-5 h-5 text-emerald-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-white">£{roi.summary.total_annual_savings.toLocaleString()}</div>
              <div className="text-sm text-gray-400">Annual Savings</div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-purple-500/20">
                  <Percent className="w-5 h-5 text-purple-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-white">{roi.summary.overall_roi.toFixed(1)}%</div>
              <div className="text-sm text-gray-400">Overall ROI</div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-yellow-500/20">
                  <Shield className="w-5 h-5 text-yellow-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-white">{roi.summary.total_incidents_prevented}</div>
              <div className="text-sm text-gray-400">Incidents Prevented</div>
            </div>
          </div>

          {/* Investments Table */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
            <div className="p-5 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">Safety Investments</h3>
            </div>
            <table className="w-full">
              <thead className="bg-slate-700/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-gray-400">Investment</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-400">Category</th>
                  <th className="text-right p-4 text-sm font-medium text-gray-400">Amount</th>
                  <th className="text-right p-4 text-sm font-medium text-gray-400">Annual Savings</th>
                  <th className="text-right p-4 text-sm font-medium text-gray-400">ROI</th>
                  <th className="text-right p-4 text-sm font-medium text-gray-400">Payback</th>
                </tr>
              </thead>
              <tbody>
                {roi.investments.map(investment => (
                  <tr key={investment.id} className="border-t border-slate-700">
                    <td className="p-4 text-white">{investment.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 bg-slate-700 text-gray-300 rounded text-xs capitalize">
                        {investment.category}
                      </span>
                    </td>
                    <td className="p-4 text-right text-gray-300">£{investment.investment.toLocaleString()}</td>
                    <td className="p-4 text-right text-emerald-400">£{investment.annual_savings.toLocaleString()}</td>
                    <td className="p-4 text-right text-white font-semibold">{investment.roi_percentage}%</td>
                    <td className="p-4 text-right text-gray-300">{investment.payback_months} months</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ROI Visualization */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-white mb-4">Investment vs Returns</h3>
            <div className="space-y-4">
              {roi.investments.map(investment => (
                <div key={investment.id}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-300">{investment.name}</span>
                    <span className="text-emerald-400 font-semibold">{investment.roi_percentage}% ROI</span>
                  </div>
                  <div className="h-8 bg-slate-700 rounded-lg overflow-hidden flex">
                    <div 
                      className="bg-blue-500 flex items-center justify-center text-xs text-white font-medium"
                      style={{ width: `${(investment.investment / (investment.investment + investment.annual_savings)) * 100}%` }}
                    >
                      Investment
                    </div>
                    <div 
                      className="bg-emerald-500 flex items-center justify-center text-xs text-white font-medium"
                      style={{ width: `${(investment.annual_savings / (investment.investment + investment.annual_savings)) * 100}%` }}
                    >
                      Returns
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Drill-down Modal */}
      {drillDownOpen && drillDownData && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">
                Drill Down: {drillDownData.metric} - {drillDownData.value}
              </h3>
              <button onClick={() => setDrillDownOpen(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 overflow-y-auto max-h-[60vh]">
              <table className="w-full">
                <thead className="bg-slate-700/50">
                  <tr>
                    <th className="text-left p-3 text-sm font-medium text-gray-400">ID</th>
                    <th className="text-left p-3 text-sm font-medium text-gray-400">Title</th>
                    <th className="text-left p-3 text-sm font-medium text-gray-400">Date</th>
                    <th className="text-left p-3 text-sm font-medium text-gray-400">Status</th>
                    <th className="text-left p-3 text-sm font-medium text-gray-400">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {drillDownData.records.map((record: any) => (
                    <tr key={record.id} className="border-t border-slate-700 hover:bg-slate-700/30 cursor-pointer">
                      <td className="p-3 text-blue-400">{record.id}</td>
                      <td className="p-3 text-white">{record.title}</td>
                      <td className="p-3 text-gray-300">{record.date}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded text-xs ${
                          record.status === 'open' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-emerald-500/20 text-emerald-400'
                        }`}>
                          {record.status}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded text-xs ${
                          record.severity === 'high' ? 'bg-red-500/20 text-red-400' :
                          record.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-emerald-500/20 text-emerald-400'
                        }`}>
                          {record.severity}
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
    </div>
  );
}
