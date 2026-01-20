import { useState } from 'react';
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
import { cn } from '../lib/utils';

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
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | '1y'>('30d');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  const kpis: KPICard[] = [
    {
      id: 'total-records',
      title: 'Total Records',
      value: '2,847',
      change: 12.5,
      changeType: 'increase',
      icon: <FileText className="w-6 h-6" />,
      variant: 'info',
      sparkline: [20, 25, 30, 28, 35, 40, 38, 45, 50, 48, 55, 60]
    },
    {
      id: 'open-items',
      title: 'Open Items',
      value: 156,
      change: -8.3,
      changeType: 'decrease',
      icon: <Clock className="w-6 h-6" />,
      variant: 'warning',
      sparkline: [45, 42, 40, 38, 35, 33, 30, 28, 26, 25, 23, 20]
    },
    {
      id: 'resolution-rate',
      title: 'Resolution Rate',
      value: '94.5%',
      change: 3.2,
      changeType: 'increase',
      icon: <CheckCircle2 className="w-6 h-6" />,
      variant: 'success',
      sparkline: [85, 87, 88, 89, 90, 91, 92, 93, 93, 94, 94, 95]
    },
    {
      id: 'avg-resolution',
      title: 'Avg Resolution Time',
      value: '4.2 days',
      change: -15.8,
      changeType: 'decrease',
      icon: <Activity className="w-6 h-6" />,
      variant: 'primary',
      sparkline: [8, 7.5, 7, 6.5, 6, 5.5, 5, 4.8, 4.6, 4.4, 4.3, 4.2]
    },
    {
      id: 'compliance-score',
      title: 'Compliance Score',
      value: '98.2%',
      change: 1.5,
      changeType: 'increase',
      icon: <Shield className="w-6 h-6" />,
      variant: 'info',
      sparkline: [95, 95.5, 96, 96.5, 97, 97, 97.5, 97.8, 98, 98, 98.1, 98.2]
    },
    {
      id: 'high-priority',
      title: 'High Priority',
      value: 23,
      change: 0,
      changeType: 'neutral',
      icon: <AlertTriangle className="w-6 h-6" />,
      variant: 'destructive',
      sparkline: [25, 24, 23, 24, 23, 22, 23, 24, 23, 23, 23, 23]
    }
  ];

  const moduleStats: ModuleStats[] = [
    { module: 'Incidents', total: 847, open: 45, closed: 802, avgResolutionDays: 3.2, trend: 5.2 },
    { module: 'RTAs', total: 234, open: 12, closed: 222, avgResolutionDays: 8.5, trend: -12.3 },
    { module: 'Complaints', total: 456, open: 34, closed: 422, avgResolutionDays: 5.1, trend: 2.1 },
    { module: 'Risks', total: 189, open: 28, closed: 161, avgResolutionDays: 15.3, trend: -5.8 },
    { module: 'Audits', total: 156, open: 18, closed: 138, avgResolutionDays: 21.2, trend: 0 },
    { module: 'Actions', total: 523, open: 67, closed: 456, avgResolutionDays: 7.4, trend: 8.9 }
  ];

  const monthlyTrends = [
    { month: 'Jan', incidents: 65, rtas: 18, complaints: 42 },
    { month: 'Feb', incidents: 72, rtas: 22, complaints: 38 },
    { month: 'Mar', incidents: 58, rtas: 15, complaints: 45 },
    { month: 'Apr', incidents: 81, rtas: 28, complaints: 52 },
    { month: 'May', incidents: 69, rtas: 20, complaints: 48 },
    { month: 'Jun', incidents: 75, rtas: 25, complaints: 41 },
    { month: 'Jul', incidents: 88, rtas: 31, complaints: 55 },
    { month: 'Aug', incidents: 92, rtas: 27, complaints: 49 },
    { month: 'Sep', incidents: 78, rtas: 23, complaints: 44 },
    { month: 'Oct', incidents: 85, rtas: 29, complaints: 51 },
    { month: 'Nov', incidents: 71, rtas: 19, complaints: 46 },
    { month: 'Dec', incidents: 67, rtas: 16, complaints: 39 }
  ];

  const handleRefresh = () => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 1500);
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
    </div>
  );
}
