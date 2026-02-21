/**
 * Advanced Analytics Dashboard
 *
 * Wired to backend analytics API for:
 * - KPI summaries from /api/v1/analytics/kpis
 * - Trend data from /api/v1/analytics/trends/{data_source}
 * - Forecasting from /api/v1/analytics/forecast
 * - Benchmarks from /api/v1/analytics/benchmarks
 * - Cost analysis from /api/v1/analytics/costs/non-compliance
 * - ROI tracking from /api/v1/analytics/roi
 * - Drill-down from /api/v1/analytics/drill-down/{data_source}
 */

import React, { useState, useEffect, useCallback } from "react";
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
} from "lucide-react";
import { cn } from "../helpers/utils";
import { Button } from "../components/ui/Button";
import { analyticsApi } from "../api/client";

interface KPIData {
  incidents: {
    total: number;
    open: number;
    closed: number;
    trend: number;
    avg_resolution_days: number;
  };
  actions: {
    total: number;
    open: number;
    overdue: number;
    completed_on_time_rate: number;
    trend: number;
  };
  audits: {
    total: number;
    completed: number;
    in_progress: number;
    avg_score: number;
    trend: number;
  };
  risks: {
    total: number;
    high: number;
    medium: number;
    low: number;
    mitigated: number;
  };
  compliance: {
    overall_score: number;
    iso_9001: number;
    iso_14001: number;
    iso_45001: number;
  };
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
  projected_annual?: number;
  cost_per_employee?: number;
  recommendations?: Array<{
    action: string;
    estimated_savings: number;
    priority: string;
  }>;
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

interface TrendDataset {
  labels: string[];
  datasets: Array<{
    label: string;
    data: number[];
    borderColor: string;
    backgroundColor: string;
  }>;
  summary: {
    total: number;
    average: number;
    min: number;
    max: number;
    trend_direction: string;
    trend_percentage: number;
  };
}

interface ForecastData {
  historical: { labels: string[]; values: number[] };
  forecast: {
    forecast: number[];
    lower_bound: number[];
    upper_bound: number[];
    confidence_level: number;
    trend_direction: string;
    trend_strength: number;
  };
}

interface BenchmarkSummary {
  comparisons: Record<string, BenchmarkData>;
  overall_percentile: number;
  above_average_count: number;
  total_metrics: number;
  performance_rating: string;
}

interface DrillDownRecord {
  id: string;
  title: string;
  date: string;
  status: string;
  severity: string;
}

const timeRanges = [
  { value: "last_7_days", label: "Last 7 Days" },
  { value: "last_30_days", label: "Last 30 Days" },
  { value: "last_90_days", label: "Last 90 Days" },
  { value: "last_12_months", label: "Last 12 Months" },
  { value: "year_to_date", label: "Year to Date" },
];

export default function AdvancedAnalytics() {
  const [timeRange, setTimeRange] = useState("last_30_days");
  const [activeTab, setActiveTab] = useState<
    "overview" | "trends" | "benchmarks" | "costs" | "roi"
  >("overview");
  const [kpis, setKpis] = useState<KPIData | null>(null);
  const [benchmarkSummary, setBenchmarkSummary] =
    useState<BenchmarkSummary | null>(null);
  const [costs, setCosts] = useState<CostData | null>(null);
  const [roi, setRoi] = useState<ROIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [incidentTrend, setIncidentTrend] = useState<TrendDataset | null>(null);
  const [actionTrend, setActionTrend] = useState<TrendDataset | null>(null);
  const [forecastData, setForecastData] = useState<ForecastData | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);

  const [selectedIndustry, setSelectedIndustry] = useState("utilities");

  const [drillDownOpen, setDrillDownOpen] = useState(false);
  const [drillDownData, setDrillDownData] = useState<{
    metric: string;
    dimension: string;
    value: string;
    records: DrillDownRecord[];
  } | null>(null);
  const [drillDownLoading, setDrillDownLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [kpiRes, benchRes, costRes, roiRes, incTrendRes, actTrendRes] =
        await Promise.allSettled([
          analyticsApi.getKPIs(timeRange),
          analyticsApi.getBenchmarks(selectedIndustry),
          analyticsApi.getNonComplianceCosts(timeRange),
          analyticsApi.getROI(),
          analyticsApi.getTrends("incidents", timeRange),
          analyticsApi.getTrends("actions", timeRange),
        ]);

      if (kpiRes.status === "fulfilled") setKpis(kpiRes.value.data as KPIData);
      if (benchRes.status === "fulfilled")
        setBenchmarkSummary(benchRes.value.data as BenchmarkSummary);
      if (costRes.status === "fulfilled")
        setCosts(costRes.value.data as CostData);
      if (roiRes.status === "fulfilled") setRoi(roiRes.value.data as ROIData);
      if (incTrendRes.status === "fulfilled")
        setIncidentTrend(incTrendRes.value.data as TrendDataset);
      if (actTrendRes.status === "fulfilled")
        setActionTrend(actTrendRes.value.data as TrendDataset);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load analytics data",
      );
    } finally {
      setLoading(false);
    }
  }, [timeRange, selectedIndustry]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadForecast = useCallback(async () => {
    if (forecastData) return;
    setForecastLoading(true);
    try {
      const res = await analyticsApi.forecast("incidents", "count", 12);
      setForecastData(res.data as ForecastData);
    } catch {
      // forecast is supplementary
    } finally {
      setForecastLoading(false);
    }
  }, [forecastData]);

  useEffect(() => {
    if (activeTab === "trends") loadForecast();
  }, [activeTab, loadForecast]);

  const handleDrillDown = async (
    metric: string,
    dimension: string,
    value: string,
  ) => {
    setDrillDownLoading(true);
    setDrillDownOpen(true);
    try {
      const res = await analyticsApi.getDrillDown(
        metric,
        dimension,
        value,
        timeRange,
      );
      const data = res.data as { records: DrillDownRecord[] };
      setDrillDownData({
        metric,
        dimension,
        value,
        records: data.records || [],
      });
    } catch {
      setDrillDownData({ metric, dimension, value, records: [] });
    } finally {
      setDrillDownLoading(false);
    }
  };

  const KPICard = ({
    title,
    value,
    subtitle,
    trend,
    icon: Icon,
    color,
    onClick,
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
      className="bg-card/50 backdrop-blur-sm border border-border rounded-xl p-5 hover:border-primary/50 transition-all cursor-pointer group"
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-lg bg-${color}-500/20`}>
          <Icon className={`w-5 h-5 text-${color}-400`} />
        </div>
        {trend !== undefined && (
          <div
            className={`flex items-center gap-1 text-sm ${trend >= 0 ? "text-success" : "text-destructive"}`}
          >
            {trend >= 0 ? (
              <ArrowUpRight className="w-4 h-4" />
            ) : (
              <ArrowDownRight className="w-4 h-4" />
            )}
            <span>{Math.abs(trend)}%</span>
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-foreground mb-1">{value}</div>
      <div className="text-sm text-muted-foreground">{title}</div>
      {subtitle && (
        <div className="text-xs text-muted-foreground/70 mt-1">{subtitle}</div>
      )}
      <div className="flex items-center gap-1 mt-3 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
        <Eye className="w-3 h-3" />
        <span>Click to drill down</span>
      </div>
    </div>
  );

  const TrendChart = ({
    data,
    title,
    color = "#10B981",
  }: {
    data: number[];
    title: string;
    color?: string;
  }) => {
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
                minHeight: "4px",
              }}
              title={`Value: ${value.toFixed(1)}`}
            />
          ))}
        </div>
        <div className="flex justify-between mt-2 text-xs text-muted-foreground">
          <span>Start</span>
          <span>Today</span>
        </div>
      </div>
    );
  };

  const BenchmarkGauge = ({
    metric,
    data,
  }: {
    metric: string;
    data: BenchmarkData;
  }) => {
    const position = (data.your_percentile / 100) * 100;

    return (
      <div className="bg-card/50 border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground capitalize">
            {metric.replace(/_/g, " ")}
          </h3>
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${
              data.trend === "improving"
                ? "bg-success/10 text-success"
                : data.trend === "stable"
                  ? "bg-info/10 text-info"
                  : "bg-destructive/10 text-destructive"
            }`}
          >
            {data.trend}
          </span>
        </div>

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
            <span className="text-foreground font-semibold ml-2">
              {data.your_value}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Industry Avg:</span>
            <span className="text-foreground font-semibold ml-2">
              {data.industry_average}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Percentile:</span>
            <span className="text-success font-semibold ml-2">
              {data.your_percentile}th
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Top 10%:</span>
            <span className="text-foreground font-semibold ml-2">
              {data.percentile_90}
            </span>
          </div>
        </div>
      </div>
    );
  };

  const tabs = [
    { id: "overview", label: "Overview", icon: BarChart3 },
    { id: "trends", label: "Trends & Forecast", icon: TrendingUp },
    { id: "benchmarks", label: "Benchmarks", icon: Target },
    { id: "costs", label: "Cost Analysis", icon: DollarSign },
    { id: "roi", label: "ROI Tracking", icon: PiggyBank },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const benchmarks = benchmarkSummary?.comparisons || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Advanced Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Interactive insights with forecasting and benchmarks
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-background border border-border rounded-lg px-4 py-2 text-foreground text-sm focus:ring-2 focus:ring-primary/50"
          >
            {timeRanges.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
          <Button
            onClick={loadData}
            variant="outline"
            size="icon"
            aria-label="Refresh data"
          >
            <RefreshCw className="w-5 h-5" />
          </Button>
          <Button>
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/30 text-destructive rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            className="ml-auto"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-card/50 p-1 rounded-xl border border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
              activeTab === tab.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && kpis && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Total Incidents"
              value={kpis.incidents.total}
              subtitle={`${kpis.incidents.open} open, ${kpis.incidents.closed} closed`}
              trend={kpis.incidents.trend}
              icon={AlertTriangle}
              color="red"
              onClick={() => handleDrillDown("incidents", "status", "all")}
            />
            <KPICard
              title="Actions"
              value={kpis.actions.total}
              subtitle={`${kpis.actions.overdue} overdue`}
              trend={kpis.actions.trend}
              icon={CheckCircle}
              color="blue"
              onClick={() => handleDrillDown("actions", "status", "all")}
            />
            <KPICard
              title="Audit Score"
              value={`${kpis.audits.avg_score}%`}
              subtitle={`${kpis.audits.completed} completed`}
              trend={kpis.audits.trend}
              icon={Shield}
              color="purple"
              onClick={() => handleDrillDown("audits", "status", "all")}
            />
            <KPICard
              title="Compliance"
              value={`${kpis.compliance.overall_score}%`}
              subtitle="Overall score"
              icon={Award}
              color="emerald"
              onClick={() => handleDrillDown("compliance", "standard", "all")}
            />
          </div>

          {/* Trend Charts from API */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {incidentTrend && incidentTrend.datasets[0] ? (
              <TrendChart
                title="Incident Trend"
                data={incidentTrend.datasets[0].data}
                color="#EF4444"
              />
            ) : (
              <div className="bg-card/50 border border-border rounded-xl p-5 flex items-center justify-center h-48 text-muted-foreground">
                No incident trend data
              </div>
            )}
            {actionTrend && actionTrend.datasets[0] ? (
              <TrendChart
                title="Action Completion Trend"
                data={actionTrend.datasets[0].data}
                color="#10B981"
              />
            ) : (
              <div className="bg-card/50 border border-border rounded-xl p-5 flex items-center justify-center h-48 text-muted-foreground">
                No action trend data
              </div>
            )}
          </div>

          {/* Risk Distribution */}
          <div className="bg-card/50 border border-border rounded-xl p-5">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Risk Distribution
            </h3>
            <div className="flex gap-4">
              {[
                {
                  label: "High Risk",
                  count: kpis.risks.high,
                  color: "bg-red-500",
                  textColor: "text-red-400",
                },
                {
                  label: "Medium Risk",
                  count: kpis.risks.medium,
                  color: "bg-yellow-500",
                  textColor: "text-yellow-400",
                },
                {
                  label: "Low Risk",
                  count: kpis.risks.low,
                  color: "bg-emerald-500",
                  textColor: "text-emerald-400",
                },
              ].map((item) => (
                <div key={item.label} className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">
                      {item.label}
                    </span>
                    <span className={`text-sm font-semibold ${item.textColor}`}>
                      {item.count}
                    </span>
                  </div>
                  <div className="h-3 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full ${item.color} rounded-full`}
                      style={{
                        width: `${(item.count / kpis.risks.total) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ISO Compliance */}
          <div className="bg-card/50 border border-border rounded-xl p-5">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              ISO Compliance Scores
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                {
                  standard: "ISO 9001",
                  score: kpis.compliance.iso_9001,
                  color: "#3B82F6",
                },
                {
                  standard: "ISO 14001",
                  score: kpis.compliance.iso_14001,
                  color: "#10B981",
                },
                {
                  standard: "ISO 45001",
                  score: kpis.compliance.iso_45001,
                  color: "#8B5CF6",
                },
              ].map((item) => (
                <div key={item.standard} className="text-center">
                  <div className="relative w-24 h-24 mx-auto mb-3">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        className="stroke-muted"
                        strokeWidth="8"
                        fill="none"
                      />
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        stroke={item.color}
                        strokeWidth="8"
                        fill="none"
                        strokeDasharray={`${(item.score / 100) * 251.2} 251.2`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xl font-bold text-foreground">
                        {item.score}%
                      </span>
                    </div>
                  </div>
                  <div className="text-sm font-medium text-muted-foreground">
                    {item.standard}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Trends Tab */}
      {activeTab === "trends" && (
        <div className="space-y-6">
          <div className="bg-card/50 border border-border rounded-xl p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Incident Forecast (Next 12 Periods)
            </h3>
            {forecastLoading ? (
              <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent" />
              </div>
            ) : forecastData ? (
              <>
                <div className="h-64 flex items-end gap-1">
                  {forecastData.historical.values.slice(-12).map((value, i) => (
                    <div
                      key={`hist-${i}`}
                      className="flex-1 flex flex-col items-center gap-1"
                    >
                      <div
                        className="w-full bg-blue-500 rounded-t transition-all"
                        style={{
                          height: `${(value / Math.max(...forecastData.historical.values.slice(-12), ...forecastData.forecast.forecast)) * 100}%`,
                        }}
                      />
                    </div>
                  ))}
                  {forecastData.forecast.forecast.map((value, i) => (
                    <div
                      key={`fore-${i}`}
                      className="flex-1 flex flex-col items-center gap-1"
                    >
                      <div
                        className="w-full bg-emerald-500/50 border-2 border-dashed border-emerald-500 rounded-t transition-all"
                        style={{
                          height: `${(value / Math.max(...forecastData.historical.values.slice(-12), ...forecastData.forecast.forecast)) * 100}%`,
                        }}
                      />
                    </div>
                  ))}
                </div>
                <div className="flex justify-center gap-6 mt-4">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-blue-500 rounded" />
                    <span className="text-sm text-muted-foreground">
                      Historical
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-emerald-500/50 border-2 border-dashed border-emerald-500 rounded" />
                    <span className="text-sm text-muted-foreground">
                      Forecast (
                      {(forecastData.forecast.confidence_level * 100).toFixed(
                        0,
                      )}
                      % CI)
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="h-64 flex items-center justify-center text-muted-foreground">
                Unable to generate forecast — insufficient data
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Forecast Summary
              </h3>
              <div className="space-y-4">
                {forecastData?.forecast ? (
                  <>
                    <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                      <span className="text-muted-foreground">
                        Trend Direction
                      </span>
                      <span
                        className={`flex items-center gap-2 ${forecastData.forecast.trend_direction === "decreasing" ? "text-success" : "text-destructive"}`}
                      >
                        {forecastData.forecast.trend_direction ===
                        "decreasing" ? (
                          <TrendingDown className="w-4 h-4" />
                        ) : (
                          <TrendingUp className="w-4 h-4" />
                        )}
                        {forecastData.forecast.trend_direction === "decreasing"
                          ? "Decreasing"
                          : "Increasing"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                      <span className="text-muted-foreground">
                        Predicted 3-month
                      </span>
                      <span className="text-foreground font-semibold">
                        {forecastData.forecast.forecast
                          .slice(0, 3)
                          .reduce((a, b) => a + b, 0)
                          .toFixed(0)}{" "}
                        incidents
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                      <span className="text-muted-foreground">
                        Confidence Level
                      </span>
                      <span className="text-foreground font-semibold">
                        {(forecastData.forecast.confidence_level * 100).toFixed(
                          0,
                        )}
                        %
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                      <span className="text-muted-foreground">
                        Trend Strength
                      </span>
                      <span className="text-foreground font-semibold">
                        {forecastData.forecast.trend_strength.toFixed(2)}
                      </span>
                    </div>
                  </>
                ) : (
                  <p className="text-muted-foreground text-sm">
                    Forecast data unavailable
                  </p>
                )}
              </div>
            </div>

            <div className="bg-card/50 border border-border rounded-xl p-5">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                AI Insights
              </h3>
              <div className="space-y-3">
                {incidentTrend?.summary && (
                  <div className="flex gap-3 p-3 bg-success/10 border border-success/30 rounded-lg">
                    <Zap className="w-5 h-5 text-success flex-shrink-0" />
                    <p className="text-sm text-muted-foreground">
                      <strong className="text-success">Trend Analysis:</strong>{" "}
                      Incidents are trending{" "}
                      {incidentTrend.summary.trend_direction} (
                      {incidentTrend.summary.trend_percentage > 0 ? "+" : ""}
                      {incidentTrend.summary.trend_percentage.toFixed(1)}%) over
                      the selected period.
                    </p>
                  </div>
                )}
                {forecastData?.forecast && (
                  <div className="flex gap-3 p-3 bg-warning/10 border border-warning/30 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0" />
                    <p className="text-sm text-muted-foreground">
                      <strong className="text-warning">Forecast:</strong> Model
                      predicts a {forecastData.forecast.trend_direction} trend
                      with strength{" "}
                      {forecastData.forecast.trend_strength.toFixed(2)} per
                      period.
                    </p>
                  </div>
                )}
                {actionTrend?.summary && (
                  <div className="flex gap-3 p-3 bg-info/10 border border-info/30 rounded-lg">
                    <Activity className="w-5 h-5 text-info flex-shrink-0" />
                    <p className="text-sm text-muted-foreground">
                      <strong className="text-info">Action Performance:</strong>{" "}
                      Average of {actionTrend.summary.average.toFixed(1)}{" "}
                      actions per period, range{" "}
                      {actionTrend.summary.min.toFixed(0)}-
                      {actionTrend.summary.max.toFixed(0)}.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Benchmarks Tab */}
      {activeTab === "benchmarks" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Building className="w-5 h-5 text-muted-foreground" />
                <select
                  value={selectedIndustry}
                  onChange={(e) => setSelectedIndustry(e.target.value)}
                  className="bg-background border border-border rounded-lg px-3 py-2 text-foreground text-sm"
                >
                  <option value="utilities">Utilities Industry</option>
                  <option value="construction">Construction</option>
                  <option value="manufacturing">Manufacturing</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <Globe className="w-5 h-5 text-muted-foreground" />
                <select className="bg-background border border-border rounded-lg px-3 py-2 text-foreground text-sm">
                  <option value="uk">United Kingdom</option>
                  <option value="eu">Europe</option>
                  <option value="global">Global</option>
                </select>
              </div>
            </div>
          </div>

          {/* Overall Performance */}
          {benchmarkSummary && (
            <div className="bg-gradient-to-r from-emerald-600/20 to-blue-600/20 border border-emerald-500/30 rounded-xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-bold text-foreground">
                    Overall Performance Rating
                  </h3>
                  <p className="text-muted-foreground mt-1">
                    Compared to industry peers
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-4xl font-bold text-emerald-400">
                    {benchmarkSummary.overall_percentile.toFixed(0)}th
                  </div>
                  <div className="text-muted-foreground">Percentile</div>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-4">
                <Award className="w-8 h-8 text-yellow-400" />
                <span className="text-lg font-semibold text-foreground">
                  {benchmarkSummary.performance_rating}
                </span>
                <span className="text-muted-foreground">|</span>
                <span className="text-muted-foreground">
                  {benchmarkSummary.above_average_count} of{" "}
                  {benchmarkSummary.total_metrics} metrics above industry
                  average
                </span>
              </div>
            </div>
          )}

          {/* Benchmark Gauges */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {Object.entries(benchmarks).map(([metric, data]) => (
              <BenchmarkGauge key={metric} metric={metric} data={data} />
            ))}
          </div>

          {/* Comparison Table */}
          {Object.keys(benchmarks).length > 0 && (
            <div className="bg-card/50 border border-border rounded-xl overflow-hidden">
              <div className="p-5 border-b border-border">
                <h3 className="text-lg font-semibold text-foreground">
                  Detailed Comparison
                </h3>
              </div>
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                      Metric
                    </th>
                    <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                      Your Value
                    </th>
                    <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                      Industry Avg
                    </th>
                    <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                      Top 10%
                    </th>
                    <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(benchmarks).map(([metric, data]) => (
                    <tr key={metric} className="border-t border-border">
                      <td className="p-4 text-foreground capitalize">
                        {metric.replace(/_/g, " ")}
                      </td>
                      <td className="p-4 text-center text-success font-semibold">
                        {data.your_value}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {data.industry_average}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {data.percentile_90}
                      </td>
                      <td className="p-4 text-center">
                        {data.your_value > data.industry_average ? (
                          <span className="inline-flex items-center gap-1 px-2 py-1 bg-success/20 text-success rounded text-xs">
                            <ArrowUpRight className="w-3 h-3" /> Above Avg
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-1 bg-destructive/20 text-destructive rounded text-xs">
                            <ArrowDownRight className="w-3 h-3" /> Below Avg
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Costs Tab */}
      {activeTab === "costs" && costs && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-red-600/20 to-orange-600/20 border border-red-500/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-muted-foreground">
                  Total Cost of Non-Compliance
                </h3>
                <div className="text-4xl font-bold text-foreground mt-2">
                  £{costs.total_cost.toLocaleString()}
                </div>
                <p className="text-muted-foreground mt-1">Selected period</p>
              </div>
              <div className="text-right">
                <div
                  className={`flex items-center gap-2 text-lg ${costs.trend.vs_previous_period < 0 ? "text-success" : "text-destructive"}`}
                >
                  {costs.trend.vs_previous_period < 0 ? (
                    <TrendingDown className="w-5 h-5" />
                  ) : (
                    <TrendingUp className="w-5 h-5" />
                  )}
                  {Math.abs(costs.trend.vs_previous_period)}%
                </div>
                <p className="text-muted-foreground text-sm">
                  vs previous period
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Cost Breakdown
              </h3>
              <div className="space-y-4">
                {Object.entries(costs.breakdown).map(([key, data]) => {
                  const amount = "amount" in data ? data.amount : 0;
                  const percentage = (amount / costs.total_cost) * 100;
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-muted-foreground capitalize">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="text-foreground font-semibold">
                          £{amount.toLocaleString()}
                        </span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
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

            <div className="bg-card/50 border border-border rounded-xl p-5">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Cost Calculator
              </h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                  <span className="text-muted-foreground">
                    Average Cost per Incident
                  </span>
                  <span className="text-foreground font-semibold">
                    £
                    {costs.breakdown.incident_costs.count > 0
                      ? Math.round(
                          costs.breakdown.incident_costs.amount /
                            costs.breakdown.incident_costs.count,
                        ).toLocaleString()
                      : "0"}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                  <span className="text-muted-foreground">
                    Cost per Employee
                  </span>
                  <span className="text-foreground font-semibold">
                    £{(costs.cost_per_employee ?? 0).toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                  <span className="text-muted-foreground">
                    Projected Annual Cost
                  </span>
                  <span className="text-foreground font-semibold">
                    £{(costs.projected_annual ?? 0).toLocaleString()}
                  </span>
                </div>
                {costs.recommendations && costs.recommendations.length > 0 && (
                  <div className="flex items-center justify-between p-3 bg-success/10 border border-success/30 rounded-lg">
                    <span className="text-muted-foreground">
                      Potential Savings (with improvements)
                    </span>
                    <span className="text-success font-semibold">
                      £
                      {costs.recommendations
                        .reduce((sum, r) => sum + r.estimated_savings, 0)
                        .toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Recommendations from API */}
          {costs.recommendations && costs.recommendations.length > 0 && (
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Cost Reduction Recommendations
              </h3>
              <div className="space-y-3">
                {costs.recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-4 bg-muted/30 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-2 h-2 rounded-full ${rec.priority === "high" ? "bg-red-500" : rec.priority === "medium" ? "bg-yellow-500" : "bg-blue-500"}`}
                      />
                      <span className="text-muted-foreground">
                        {rec.action}
                      </span>
                    </div>
                    <span className="text-success font-semibold">
                      Save £{rec.estimated_savings.toLocaleString()}/year
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ROI Tab */}
      {activeTab === "roi" && roi && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-blue-500/20">
                  <Coins className="w-5 h-5 text-blue-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-foreground">
                £{roi.summary.total_investment.toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">
                Total Investment
              </div>
            </div>
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-emerald-500/20">
                  <PiggyBank className="w-5 h-5 text-emerald-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-foreground">
                £{roi.summary.total_annual_savings.toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">
                Annual Savings
              </div>
            </div>
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-purple-500/20">
                  <Percent className="w-5 h-5 text-purple-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-foreground">
                {roi.summary.overall_roi.toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">Overall ROI</div>
            </div>
            <div className="bg-card/50 border border-border rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-yellow-500/20">
                  <Shield className="w-5 h-5 text-yellow-400" />
                </div>
              </div>
              <div className="text-2xl font-bold text-foreground">
                {roi.summary.total_incidents_prevented}
              </div>
              <div className="text-sm text-muted-foreground">
                Incidents Prevented
              </div>
            </div>
          </div>

          <div className="bg-card/50 border border-border rounded-xl overflow-hidden">
            <div className="p-5 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">
                Safety Investments
              </h3>
            </div>
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Investment
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Category
                  </th>
                  <th className="text-right p-4 text-sm font-medium text-muted-foreground">
                    Amount
                  </th>
                  <th className="text-right p-4 text-sm font-medium text-muted-foreground">
                    Annual Savings
                  </th>
                  <th className="text-right p-4 text-sm font-medium text-muted-foreground">
                    ROI
                  </th>
                  <th className="text-right p-4 text-sm font-medium text-muted-foreground">
                    Payback
                  </th>
                </tr>
              </thead>
              <tbody>
                {roi.investments.map((investment) => (
                  <tr key={investment.id} className="border-t border-border">
                    <td className="p-4 text-foreground">{investment.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 bg-muted text-muted-foreground rounded text-xs capitalize">
                        {investment.category}
                      </span>
                    </td>
                    <td className="p-4 text-right text-muted-foreground">
                      £{investment.investment.toLocaleString()}
                    </td>
                    <td className="p-4 text-right text-success">
                      £{investment.annual_savings.toLocaleString()}
                    </td>
                    <td className="p-4 text-right text-foreground font-semibold">
                      {investment.roi_percentage}%
                    </td>
                    <td className="p-4 text-right text-muted-foreground">
                      {investment.payback_months} months
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-card/50 border border-border rounded-xl p-5">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Investment vs Returns
            </h3>
            <div className="space-y-4">
              {roi.investments.map((investment) => (
                <div key={investment.id}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-muted-foreground">
                      {investment.name}
                    </span>
                    <span className="text-success font-semibold">
                      {investment.roi_percentage}% ROI
                    </span>
                  </div>
                  <div className="h-8 bg-muted rounded-lg overflow-hidden flex">
                    <div
                      className="bg-blue-500 flex items-center justify-center text-xs text-white font-medium"
                      style={{
                        width: `${(investment.investment / (investment.investment + investment.annual_savings)) * 100}%`,
                      }}
                    >
                      Investment
                    </div>
                    <div
                      className="bg-emerald-500 flex items-center justify-center text-xs text-white font-medium"
                      style={{
                        width: `${(investment.annual_savings / (investment.investment + investment.annual_savings)) * 100}%`,
                      }}
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
      {drillDownOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-card border border-border rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">
                Drill Down: {drillDownData?.metric} - {drillDownData?.value}
              </h3>
              <button
                onClick={() => setDrillDownOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 overflow-y-auto max-h-[60vh]">
              {drillDownLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent" />
                </div>
              ) : drillDownData?.records && drillDownData.records.length > 0 ? (
                <table className="w-full">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                        ID
                      </th>
                      <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                        Title
                      </th>
                      <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                        Date
                      </th>
                      <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                        Status
                      </th>
                      <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                        Severity
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {drillDownData.records.map((record) => (
                      <tr
                        key={record.id}
                        className="border-t border-border hover:bg-muted/30 cursor-pointer"
                      >
                        <td className="p-3 text-primary">{record.id}</td>
                        <td className="p-3 text-foreground">{record.title}</td>
                        <td className="p-3 text-muted-foreground">
                          {record.date}
                        </td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-1 rounded text-xs ${
                              record.status === "open"
                                ? "bg-warning/20 text-warning"
                                : "bg-success/20 text-success"
                            }`}
                          >
                            {record.status}
                          </span>
                        </td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-1 rounded text-xs ${
                              record.severity === "high"
                                ? "bg-destructive/20 text-destructive"
                                : record.severity === "medium"
                                  ? "bg-warning/20 text-warning"
                                  : "bg-success/20 text-success"
                            }`}
                          >
                            {record.severity}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-center text-muted-foreground py-8">
                  No records found for this drill-down.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
