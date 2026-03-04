import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Building,
  Settings,
  Users,
  ClipboardList,
  Bell,
  Shield,
  Database,
  Activity,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { cn } from '../../helpers/utils';

interface QuickAction {
  title: string;
  description: string;
  icon: React.ReactNode;
  href: string;
  color: string;
}

interface StatCard {
  label: string;
  value: string;
  change: string;
  trend: 'up' | 'down' | 'neutral';
  icon: React.ReactNode;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    title: 'Form Builder',
    description: 'Create and manage forms',
    icon: <FileText className="w-6 h-6" />,
    href: '/admin/forms',
    color: 'bg-primary/10 text-primary',
  },
  {
    title: 'Contracts',
    description: 'Manage contract options',
    icon: <Building className="w-6 h-6" />,
    href: '/admin/contracts',
    color: 'bg-blue-100 text-blue-600',
  },
  {
    title: 'System Settings',
    description: 'Configure system preferences',
    icon: <Settings className="w-6 h-6" />,
    href: '/admin/settings',
    color: 'bg-purple-100 text-purple-600',
  },
  {
    title: 'User Management',
    description: 'Manage users and roles',
    icon: <Users className="w-6 h-6" />,
    href: '/admin/users',
    color: 'bg-green-100 text-green-600',
  },
  {
    title: 'Lookup Tables',
    description: 'Manage dropdown options',
    icon: <ClipboardList className="w-6 h-6" />,
    href: '/admin/lookups',
    color: 'bg-orange-100 text-orange-600',
  },
  {
    title: 'Notifications',
    description: 'Email and alert settings',
    icon: <Bell className="w-6 h-6" />,
    href: '/admin/notifications',
    color: 'bg-pink-100 text-pink-600',
  },
];

const STATS: StatCard[] = [
  {
    label: 'Active Forms',
    value: '12',
    change: '+2 this month',
    trend: 'up',
    icon: <FileText className="w-5 h-5" />,
  },
  {
    label: 'Active Contracts',
    value: '10',
    change: 'No change',
    trend: 'neutral',
    icon: <Building className="w-5 h-5" />,
  },
  {
    label: 'Submissions Today',
    value: '24',
    change: '+15% vs yesterday',
    trend: 'up',
    icon: <Activity className="w-5 h-5" />,
  },
  {
    label: 'Pending Actions',
    value: '8',
    change: '-3 from last week',
    trend: 'down',
    icon: <Clock className="w-5 h-5" />,
  },
];

const RECENT_ACTIVITY = [
  { action: 'Form "Incident Report" updated', user: 'David Harris', time: '2 hours ago', type: 'edit' },
  { action: 'New contract "National Grid" added', user: 'Admin', time: '4 hours ago', type: 'add' },
  { action: 'System settings updated', user: 'David Harris', time: '1 day ago', type: 'settings' },
  { action: 'Form "RTA Report" published', user: 'Admin', time: '2 days ago', type: 'publish' },
  { action: 'User "John Smith" added', user: 'Admin', time: '3 days ago', type: 'add' },
];

export default function AdminDashboard() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">Admin Dashboard</h1>
              <p className="text-muted-foreground mt-2">
                Manage forms, contracts, settings, and system configuration
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 bg-green-100 text-green-700 rounded-lg">
                <CheckCircle className="w-4 h-4" />
                <span className="text-sm font-medium">System Healthy</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {STATS.map((stat) => (
            <Card key={stat.label} className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="text-2xl font-bold text-foreground mt-1">{stat.value}</p>
                  <p
                    className={cn(
                      'text-xs mt-1 flex items-center gap-1',
                      stat.trend === 'up' && 'text-green-600',
                      stat.trend === 'down' && 'text-destructive',
                      stat.trend === 'neutral' && 'text-muted-foreground'
                    )}
                  >
                    {stat.trend === 'up' && <TrendingUp className="w-3 h-3" />}
                    {stat.trend === 'down' && <TrendingUp className="w-3 h-3 rotate-180" />}
                    {stat.change}
                  </p>
                </div>
                <div className="p-2 bg-primary/10 text-primary rounded-lg">
                  {stat.icon}
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {QUICK_ACTIONS.map((action) => (
              <Card
                key={action.title}
                className="p-5 cursor-pointer hover:shadow-md transition-all group"
                onClick={() => navigate(action.href)}
              >
                <div className="flex items-start gap-4">
                  <div className={cn('p-3 rounded-xl', action.color)}>
                    {action.icon}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                      {action.title}
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {action.description}
                    </p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Recent Activity & System Status */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Activity */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">Recent Activity</h2>
            <div className="space-y-4">
              {RECENT_ACTIVITY.map((activity, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 pb-4 border-b border-border last:border-0 last:pb-0"
                >
                  <div
                    className={cn(
                      'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                      activity.type === 'edit' && 'bg-blue-100 text-blue-600',
                      activity.type === 'add' && 'bg-green-100 text-green-600',
                      activity.type === 'settings' && 'bg-purple-100 text-purple-600',
                      activity.type === 'publish' && 'bg-primary/10 text-primary'
                    )}
                  >
                    {activity.type === 'edit' && <FileText className="w-4 h-4" />}
                    {activity.type === 'add' && <Building className="w-4 h-4" />}
                    {activity.type === 'settings' && <Settings className="w-4 h-4" />}
                    {activity.type === 'publish' && <CheckCircle className="w-4 h-4" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground">{activity.action}</p>
                    <p className="text-xs text-muted-foreground">
                      {activity.user} • {activity.time}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* System Status */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">System Status</h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-800">API Server</p>
                    <p className="text-xs text-green-600">Healthy • 99.9% uptime</p>
                  </div>
                </div>
                <span className="text-xs text-green-600">23ms latency</span>
              </div>

              <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-800">Database</p>
                    <p className="text-xs text-green-600">Connected • Azure SQL</p>
                  </div>
                </div>
                <span className="text-xs text-green-600">5ms query time</span>
              </div>

              <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-800">Authentication</p>
                    <p className="text-xs text-green-600">Azure AD Connected</p>
                  </div>
                </div>
                <span className="text-xs text-green-600">Active</span>
              </div>

              <div className="flex items-center justify-between p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-yellow-600" />
                  <div>
                    <p className="text-sm font-medium text-yellow-800">Background Jobs</p>
                    <p className="text-xs text-yellow-600">2 jobs pending</p>
                  </div>
                </div>
                <span className="text-xs text-yellow-600">Processing</span>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
