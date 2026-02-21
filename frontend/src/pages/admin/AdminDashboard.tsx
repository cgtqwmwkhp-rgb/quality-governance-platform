import { useState, useEffect, useCallback } from 'react';
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
  Loader2,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { cn } from '../../helpers/utils';
import { useToast, ToastContainer } from '../../components/ui/Toast';
import { usersApi, auditTrailApi, actionsApi } from '../../api/client';

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

function formatTimeAgo(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? '' : 's'} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays === 1) return 'Yesterday';
  return `${diffDays} days ago`;
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<StatCard[]>([]);
  const [recentActivity, setRecentActivity] = useState<{ action: string; user: string; time: string; type: string }[]>([]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [usersRes, actionsRes, trailRes] = await Promise.allSettled([
        usersApi.list(1, 10),
        actionsApi.list(1, 100),
        auditTrailApi.list({ page: 1, per_page: 10 }),
      ]);

      const userCount = usersRes.status === 'fulfilled' ? (usersRes.value.data?.total || 0) : 0;
      const actionItems = actionsRes.status === 'fulfilled' ? (actionsRes.value.data?.items || []) : [];
      const pendingActions = actionItems.filter((a) => a.status !== 'completed' && a.status !== 'closed').length;

      setStats([
        { label: 'Total Users', value: String(userCount), change: '', trend: 'neutral' as const, icon: <Users className="w-5 h-5" /> },
        { label: 'Total Actions', value: String(actionItems.length), change: '', trend: 'neutral' as const, icon: <Activity className="w-5 h-5" /> },
        { label: 'Pending Actions', value: String(pendingActions), change: '', trend: pendingActions > 0 ? 'down' as const : 'neutral' as const, icon: <Clock className="w-5 h-5" /> },
        { label: 'System Status', value: 'Healthy', change: '', trend: 'up' as const, icon: <CheckCircle className="w-5 h-5" /> },
      ]);

      if (trailRes.status === 'fulfilled') {
        const entries = Array.isArray(trailRes.value.data) ? trailRes.value.data : [];
        setRecentActivity(entries.slice(0, 5).map((e) => {
          const actionType = e.action === 'create' ? 'add' : e.action === 'update' ? 'edit' : e.action === 'delete' ? 'settings' : 'publish';
          const timeAgo = formatTimeAgo(e.timestamp || e.created_at || '');
          return {
            action: e.entity_name || `${e.action} on ${e.entity_type} ${e.entity_id}`,
            user: e.user_name || 'System',
            time: timeAgo,
            type: actionType,
          };
        }));
      }
    } catch (err) {
      console.error('Failed to load admin dashboard:', err);
      showToast('Failed to load dashboard data', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

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
          {stats.map((stat) => (
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
              {recentActivity.map((activity, index) => (
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
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
