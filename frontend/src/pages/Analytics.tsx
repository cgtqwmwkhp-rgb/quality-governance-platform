import { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Shield,
  Activity,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  RefreshCw,
  Download,
  Sparkles,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { cn } from "../helpers/utils";
import { CardSkeleton } from '../components/ui/SkeletonLoader';
import { analyticsApi } from '../api/client';
import { useToast, ToastContainer } from '../components/ui/Toast';

interface KPICard {
  id: string;
  title: string;
  value: number | string;
  change: number;
  changeType: 'increase' | 'decrease' | 'neutral';
  icon: React.ReactNode;
  variant: 'primary' | 'info' | 'warning' | 'success' | 'destructive';
  sparkline?: number[];
}

interface ModuleStats {
  module: string;
  total: number;
  open: number;
  closed: number;
  avgResolutionDays: number;
  trend: number;
}

export default function Analytics() {
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | '1y'>('30d');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [kpis, setKpis] = useState<KPICard[]>([]);
  const [moduleStats, setModuleStats] = useState<ModuleStats[]>([]);
  const [monthlyTrends, setMonthlyTrends] = useState<{ month: string; incidents: number; rtas: number; complaints: number }[]>([]);

  const ICON_MAP: Record<string, React.ReactNode> = {
    'total-records': <FileText className="w-6 h-6" />,
    'open-items': <Clock className="w-6 h-6" />,
    'resolution-rate': <CheckCircle2 className="w-6 h-6" />,
    'avg-resolution': <Activity className="w-6 h-6" />,
    'compliance-score': <Shield className="w-6 h-6" />,
    'high-priority': <AlertTriangle className="w-6 h-6" />,
  };

  const loadAnalytics = useCallback(async () => {
    setIsLoading(true);
    try {
      const [kpiRes, trendRes] = await Promise.all([
        analyticsApi.getKPIs(timeRange),
        analyticsApi.getTrends('incidents', timeRange),
      ]);

      const kpiData = kpiRes.data as Record<string, unknown>;
      if (kpiData?.['kpis'] && Array.isArray(kpiData['kpis'])) {
        setKpis((kpiData['kpis'] as Record<string, unknown>[]).map((k) => ({
          id: String(k['id'] || ''),
          title: String(k['title'] || ''),
          value: k['value'] as string | number,
          change: Number(k['change'] || 0),
          changeType: (k['changeType'] || k['change_type'] || 'neutral') as KPICard['changeType'],
          icon: ICON_MAP[String(k['id'])] || <BarChart3 className="w-6 h-6" />,
          variant: (k['variant'] || 'primary') as KPICard['variant'],
          sparkline: k['sparkline'] as number[] | undefined,
        })));
      }

      const trendData = trendRes.data as Record<string, unknown>;
      if (trendData?.['trends'] && Array.isArray(trendData['trends'])) {
        setMonthlyTrends(trendData['trends'] as typeof monthlyTrends);
      }

      const rawKpis = kpiRes.data as Record<string, Record<string, number>>;
      const modules = ['incidents', 'actions', 'audits', 'risks'];
      const stats = modules.map((mod) => {
        const m = rawKpis[mod] || {};
        return {
          module: mod.charAt(0).toUpperCase() + mod.slice(1),
          total: Number(m['total'] || 0),
          open: Number(m['open'] || 0),
          closed: Number(m['closed'] || m['completed'] || m['mitigated'] || 0),
          avgResolutionDays: Number(m['avg_resolution_days'] || 0),
          trend: Number(m['trend'] || 0),
        };
      });
      setModuleStats(stats);
    } catch {
      console.error('Failed to load analytics');
      showToast('Failed to load analytics. Please try again.', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [timeRange]);

  useEffect(() => { loadAnalytics(); }, [loadAnalytics]);

  const handleRefresh = () => {
    loadAnalytics();
  };

  const TrendIndicator = ({ change, type }: { change: number; type: 'increase' | 'decrease' | 'neutral' }) => {
    if (type === 'neutral') {
      return (
        <span className="flex items-center gap-1 text-muted-foreground text-sm">
          <Minus className="w-4 h-4" />
          No change
        </span>
      );
    }
    
    const isPositive = type === 'decrease' ? change < 0 : change > 0;
    const Icon = change > 0 ? ArrowUpRight : ArrowDownRight;
    
    return (
      <span className={cn(
        "flex items-center gap-1 text-sm",
        isPositive ? 'text-success' : 'text-destructive'
      )}>
        <Icon className="w-4 h-4" />
        {Math.abs(change)}%
      </span>
    );
  };

  const MiniSparkline = ({ data, variant }: { data: number[]; variant: string }) => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    
    return (
      <div className="flex items-end gap-0.5 h-8">
        {data.map((value, i) => (
          <div
            key={i}
            className={cn(
              "w-1.5 rounded-full opacity-60",
              variant === 'primary' && "bg-primary",
              variant === 'info' && "bg-info",
              variant === 'warning' && "bg-warning",
              variant === 'success' && "bg-success",
              variant === 'destructive' && "bg-destructive",
            )}
            style={{ height: `${((value - min) / range) * 100}%`, minHeight: '4px' }}
          />
        ))}
      </div>
    );
  };

  if (isLoading) {
    return <CardSkeleton />;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl">
              <BarChart3 className="w-8 h-8 text-primary" />
            </div>
            Analytics Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">Cross-module insights and performance metrics</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex bg-surface rounded-lg p-1 border border-border">
            {(['7d', '30d', '90d', '1y'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={cn(
                  "px-3 py-1.5 text-sm font-medium rounded-md transition-all",
                  timeRange === range
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {range}
              </button>
            ))}
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            className={isLoading ? 'animate-spin' : ''}
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
          
          <Button variant="outline" size="sm">
            <Download className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.id} hoverable className="p-4">
            <div className="flex items-start justify-between mb-3">
              <div className={cn(
                "p-2 rounded-lg",
                kpi.variant === 'primary' && "bg-primary/10 text-primary",
                kpi.variant === 'info' && "bg-info/10 text-info",
                kpi.variant === 'warning' && "bg-warning/10 text-warning",
                kpi.variant === 'success' && "bg-success/10 text-success",
                kpi.variant === 'destructive' && "bg-destructive/10 text-destructive",
              )}>
                {kpi.icon}
              </div>
              <TrendIndicator change={kpi.change} type={kpi.changeType} />
            </div>
            
            <div className="mb-3">
              <p className="text-2xl font-bold text-foreground">{kpi.value}</p>
              <p className="text-sm text-muted-foreground">{kpi.title}</p>
            </div>
            
            {kpi.sparkline && (
              <MiniSparkline data={kpi.sparkline} variant={kpi.variant} />
            )}
          </Card>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend Chart */}
        <Card className="lg:col-span-2 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Monthly Trends
            </h2>
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-info" />
                Incidents
              </span>
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-warning" />
                RTAs
              </span>
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-primary" />
                Complaints
              </span>
            </div>
          </div>
          
          <div className="h-64 flex items-end justify-between gap-2">
            {monthlyTrends.map((month) => (
              <div key={month.month} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex flex-col items-center gap-0.5">
                  <div
                    className="w-full max-w-[20px] bg-info rounded-t"
                    style={{ height: `${month.incidents * 2}px` }}
                  />
                  <div
                    className="w-full max-w-[20px] bg-warning rounded-t"
                    style={{ height: `${month.rtas * 3}px` }}
                  />
                  <div
                    className="w-full max-w-[20px] bg-primary rounded-t"
                    style={{ height: `${month.complaints * 2.5}px` }}
                  />
                </div>
                <span className="text-xs text-muted-foreground mt-2">{month.month}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Module Distribution */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-6">
            <PieChart className="w-5 h-5 text-primary" />
            Module Distribution
          </h2>
          
          <div className="space-y-4">
            {moduleStats.map((stat) => {
              const percentage = (stat.total / moduleStats.reduce((a, b) => a + b.total, 0)) * 100;
              const variants: Record<string, string> = {
                'Incidents': 'bg-info',
                'RTAs': 'bg-warning',
                'Complaints': 'bg-primary',
                'Risks': 'bg-destructive',
                'Audits': 'bg-success',
                'Actions': 'bg-info'
              };
              
              return (
                <div key={stat.module} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-foreground">{stat.module}</span>
                    <span className="text-foreground font-medium">{stat.total}</span>
                  </div>
                  <div className="h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all", variants[stat.module])}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Module Performance Table */}
      <Card className="overflow-hidden">
        <div className="p-6 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Module Performance
          </h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-surface">
              <tr>
                <th className="text-left p-4 text-sm font-medium text-muted-foreground">Module</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Total</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Open</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Closed</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Avg Resolution</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Trend</th>
              </tr>
            </thead>
            <tbody>
              {moduleStats.map((stat) => (
                <tr
                  key={stat.module}
                  className={cn(
                    "border-b border-border hover:bg-surface transition-colors cursor-pointer",
                    selectedModule === stat.module && 'bg-primary/5'
                  )}
                  onClick={() => setSelectedModule(stat.module === selectedModule ? null : stat.module)}
                >
                  <td className="p-4">
                    <span className="font-medium text-foreground">{stat.module}</span>
                  </td>
                  <td className="p-4 text-center text-foreground">{stat.total}</td>
                  <td className="p-4 text-center">
                    <span className="px-2 py-1 bg-warning/20 text-warning rounded-full text-sm">
                      {stat.open}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <span className="px-2 py-1 bg-success/20 text-success rounded-full text-sm">
                      {stat.closed}
                    </span>
                  </td>
                  <td className="p-4 text-center text-foreground">{stat.avgResolutionDays} days</td>
                  <td className="p-4 text-center">
                    <TrendIndicator
                      change={stat.trend}
                      type={stat.trend > 0 ? 'increase' : stat.trend < 0 ? 'decrease' : 'neutral'}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* AI Insights */}
      <Card className="p-6 border-primary/20 bg-primary/5">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-primary/20 rounded-xl">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground mb-2">AI-Powered Insights</h3>
            <div className="space-y-2 text-muted-foreground">
              <p>• <strong className="text-foreground">Incident resolution</strong> has improved by 15.8% this quarter, reducing average time from 5 days to 4.2 days.</p>
              <p>• <strong className="text-foreground">RTA frequency</strong> shows a downward trend (-12.3%), likely due to recent safety training initiatives.</p>
              <p>• <strong className="text-foreground">Complaint volumes</strong> peaked in July (+55 cases) - consider reviewing Q3 service delivery processes.</p>
              <p>• <strong className="text-foreground">Risk register</strong> has 28 open items requiring attention, 8 are overdue for review.</p>
            </div>
          </div>
        </div>
      </Card>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
