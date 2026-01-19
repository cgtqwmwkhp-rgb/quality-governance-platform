import { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Shield,
  Car,
  MessageSquare,
  Activity,
  PieChart,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  RefreshCw,
  Download,
  Filter,
  Sparkles
} from 'lucide-react';

interface KPICard {
  id: string;
  title: string;
  value: number | string;
  change: number;
  changeType: 'increase' | 'decrease' | 'neutral';
  icon: React.ReactNode;
  color: string;
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

  // Simulated KPI data
  const kpis: KPICard[] = [
    {
      id: 'total-records',
      title: 'Total Records',
      value: '2,847',
      change: 12.5,
      changeType: 'increase',
      icon: <FileText className="w-6 h-6" />,
      color: 'from-blue-500 to-cyan-500',
      sparkline: [20, 25, 30, 28, 35, 40, 38, 45, 50, 48, 55, 60]
    },
    {
      id: 'open-items',
      title: 'Open Items',
      value: 156,
      change: -8.3,
      changeType: 'decrease',
      icon: <Clock className="w-6 h-6" />,
      color: 'from-amber-500 to-orange-500',
      sparkline: [45, 42, 40, 38, 35, 33, 30, 28, 26, 25, 23, 20]
    },
    {
      id: 'resolution-rate',
      title: 'Resolution Rate',
      value: '94.5%',
      change: 3.2,
      changeType: 'increase',
      icon: <CheckCircle2 className="w-6 h-6" />,
      color: 'from-emerald-500 to-green-500',
      sparkline: [85, 87, 88, 89, 90, 91, 92, 93, 93, 94, 94, 95]
    },
    {
      id: 'avg-resolution',
      title: 'Avg Resolution Time',
      value: '4.2 days',
      change: -15.8,
      changeType: 'decrease',
      icon: <Activity className="w-6 h-6" />,
      color: 'from-purple-500 to-violet-500',
      sparkline: [8, 7.5, 7, 6.5, 6, 5.5, 5, 4.8, 4.6, 4.4, 4.3, 4.2]
    },
    {
      id: 'compliance-score',
      title: 'Compliance Score',
      value: '98.2%',
      change: 1.5,
      changeType: 'increase',
      icon: <Shield className="w-6 h-6" />,
      color: 'from-indigo-500 to-blue-500',
      sparkline: [95, 95.5, 96, 96.5, 97, 97, 97.5, 97.8, 98, 98, 98.1, 98.2]
    },
    {
      id: 'high-priority',
      title: 'High Priority',
      value: 23,
      change: 0,
      changeType: 'neutral',
      icon: <AlertTriangle className="w-6 h-6" />,
      color: 'from-red-500 to-rose-500',
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
        <span className="flex items-center gap-1 text-slate-400 text-sm">
          <Minus className="w-4 h-4" />
          No change
        </span>
      );
    }
    
    const isPositive = type === 'decrease' ? change < 0 : change > 0;
    const Icon = change > 0 ? ArrowUpRight : ArrowDownRight;
    
    return (
      <span className={`flex items-center gap-1 text-sm ${
        isPositive ? 'text-emerald-400' : 'text-red-400'
      }`}>
        <Icon className="w-4 h-4" />
        {Math.abs(change)}%
      </span>
    );
  };

  const MiniSparkline = ({ data, color }: { data: number[]; color: string }) => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    
    return (
      <div className="flex items-end gap-0.5 h-8">
        {data.map((value, i) => (
          <div
            key={i}
            className={`w-1.5 rounded-full bg-gradient-to-t ${color} opacity-60`}
            style={{ height: `${((value - min) / range) * 100}%`, minHeight: '4px' }}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl">
              <BarChart3 className="w-8 h-8" />
            </div>
            Analytics Dashboard
          </h1>
          <p className="text-slate-400 mt-1">Cross-module insights and performance metrics</p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Time Range Selector */}
          <div className="flex bg-slate-800/50 rounded-lg p-1">
            {(['7d', '30d', '90d', '1y'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                  timeRange === range
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
          
          <button
            onClick={handleRefresh}
            className={`p-2 bg-slate-800/50 rounded-lg text-slate-400 hover:text-white transition-all ${
              isLoading ? 'animate-spin' : ''
            }`}
          >
            <RefreshCw className="w-5 h-5" />
          </button>
          
          <button className="p-2 bg-slate-800/50 rounded-lg text-slate-400 hover:text-white transition-all">
            <Download className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.id}
            className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-4 hover:border-violet-500/50 transition-all group"
          >
            <div className="flex items-start justify-between mb-3">
              <div className={`p-2 rounded-lg bg-gradient-to-br ${kpi.color} text-white`}>
                {kpi.icon}
              </div>
              <TrendIndicator change={kpi.change} type={kpi.changeType} />
            </div>
            
            <div className="mb-3">
              <p className="text-2xl font-bold text-white">{kpi.value}</p>
              <p className="text-sm text-slate-400">{kpi.title}</p>
            </div>
            
            {kpi.sparkline && (
              <MiniSparkline data={kpi.sparkline} color={kpi.color} />
            )}
          </div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend Chart */}
        <div className="lg:col-span-2 bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-violet-400" />
              Monthly Trends
            </h2>
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-blue-500" />
                Incidents
              </span>
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-amber-500" />
                RTAs
              </span>
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-purple-500" />
                Complaints
              </span>
            </div>
          </div>
          
          {/* Simple Bar Chart */}
          <div className="h-64 flex items-end justify-between gap-2">
            {monthlyTrends.map((month, i) => (
              <div key={month.month} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex flex-col items-center gap-0.5">
                  <div
                    className="w-full max-w-[20px] bg-gradient-to-t from-blue-600 to-blue-400 rounded-t"
                    style={{ height: `${month.incidents * 2}px` }}
                  />
                  <div
                    className="w-full max-w-[20px] bg-gradient-to-t from-amber-600 to-amber-400 rounded-t"
                    style={{ height: `${month.rtas * 3}px` }}
                  />
                  <div
                    className="w-full max-w-[20px] bg-gradient-to-t from-purple-600 to-purple-400 rounded-t"
                    style={{ height: `${month.complaints * 2.5}px` }}
                  />
                </div>
                <span className="text-xs text-slate-500 mt-2">{month.month}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Module Distribution */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-6">
            <PieChart className="w-5 h-5 text-violet-400" />
            Module Distribution
          </h2>
          
          <div className="space-y-4">
            {moduleStats.map((stat) => {
              const percentage = (stat.total / moduleStats.reduce((a, b) => a + b.total, 0)) * 100;
              const colors: Record<string, string> = {
                'Incidents': 'from-blue-500 to-cyan-500',
                'RTAs': 'from-amber-500 to-orange-500',
                'Complaints': 'from-purple-500 to-violet-500',
                'Risks': 'from-red-500 to-rose-500',
                'Audits': 'from-emerald-500 to-green-500',
                'Actions': 'from-indigo-500 to-blue-500'
              };
              
              return (
                <div key={stat.module} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-300">{stat.module}</span>
                    <span className="text-white font-medium">{stat.total}</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full bg-gradient-to-r ${colors[stat.module]} rounded-full transition-all`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Module Performance Table */}
      <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
        <div className="p-6 border-b border-slate-700/50">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-violet-400" />
            Module Performance
          </h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-900/50">
              <tr>
                <th className="text-left p-4 text-sm font-medium text-slate-400">Module</th>
                <th className="text-center p-4 text-sm font-medium text-slate-400">Total</th>
                <th className="text-center p-4 text-sm font-medium text-slate-400">Open</th>
                <th className="text-center p-4 text-sm font-medium text-slate-400">Closed</th>
                <th className="text-center p-4 text-sm font-medium text-slate-400">Avg Resolution</th>
                <th className="text-center p-4 text-sm font-medium text-slate-400">Trend</th>
              </tr>
            </thead>
            <tbody>
              {moduleStats.map((stat, i) => (
                <tr
                  key={stat.module}
                  className={`border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors ${
                    selectedModule === stat.module ? 'bg-violet-500/10' : ''
                  }`}
                  onClick={() => setSelectedModule(stat.module === selectedModule ? null : stat.module)}
                >
                  <td className="p-4">
                    <span className="font-medium text-white">{stat.module}</span>
                  </td>
                  <td className="p-4 text-center text-slate-300">{stat.total}</td>
                  <td className="p-4 text-center">
                    <span className="px-2 py-1 bg-amber-500/20 text-amber-400 rounded-full text-sm">
                      {stat.open}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm">
                      {stat.closed}
                    </span>
                  </td>
                  <td className="p-4 text-center text-slate-300">{stat.avgResolutionDays} days</td>
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
      </div>

      {/* AI Insights */}
      <div className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border border-violet-500/30 rounded-xl p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-violet-500/20 rounded-xl">
            <Sparkles className="w-6 h-6 text-violet-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">AI-Powered Insights</h3>
            <div className="space-y-2 text-slate-300">
              <p>• <strong>Incident resolution</strong> has improved by 15.8% this quarter, reducing average time from 5 days to 4.2 days.</p>
              <p>• <strong>RTA frequency</strong> shows a downward trend (-12.3%), likely due to recent safety training initiatives.</p>
              <p>• <strong>Complaint volumes</strong> peaked in July (+55 cases) - consider reviewing Q3 service delivery processes.</p>
              <p>• <strong>Risk register</strong> has 28 open items requiring attention, 8 are overdue for review.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
