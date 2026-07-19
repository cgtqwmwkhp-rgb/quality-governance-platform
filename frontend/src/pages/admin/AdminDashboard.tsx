import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
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
  Webhook,
  Loader2,
  Megaphone,
  MessageSquare,
} from 'lucide-react'
import { auditTrailApi, contractsApi, libraryReviewApi } from '../../api/client'
import { formConfigApi } from '../../api/formConfigClient'
import { Card } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'
import { AdminLoadUnavailable, captureAdminLoadError } from './adminLoadHelpers'

interface QuickAction {
  title: string
  description: string
  icon: React.ReactNode
  href: string
  color: string
}

interface StatCard {
  label: string
  value: string
  change: string
  trend: 'up' | 'down' | 'neutral'
  icon: React.ReactNode
  unavailable?: boolean
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
  {
    title: 'Campaign Compliance',
    description: 'Document campaign completion and reminders',
    icon: <Megaphone className="w-6 h-6" />,
    href: '/admin/campaign-compliance',
    color: 'bg-amber-100 text-amber-700',
  },
  {
    title: 'HSEQ Inbox',
    description: 'Answer engineer questions on assigned reads',
    icon: <MessageSquare className="w-6 h-6" />,
    href: '/admin/hsec-inbox',
    color: 'bg-indigo-100 text-indigo-600',
  },
  {
    title: 'Library roles',
    description: 'Staff / manager / admin facets and restricted category gates',
    icon: <Users className="w-6 h-6" />,
    href: '/admin/library-roles',
    color: 'bg-violet-100 text-violet-700',
  },
  {
    title: 'Engineer groups',
    description: 'Campaign audience groups for HSEQ launches',
    icon: <Users className="w-6 h-6" />,
    href: '/admin/engineer-groups',
    color: 'bg-emerald-100 text-emerald-700',
  },
  {
    title: 'Partner Webhooks',
    description: 'Manage partner event subscriptions',
    icon: <Webhook className="w-6 h-6" />,
    href: '/admin/partner-webhooks',
    color: 'bg-cyan-100 text-cyan-600',
  },
]

function formatTimeAgo(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? '' : 's'} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  if (diffDays === 1) return 'Yesterday'
  return `${diffDays} days ago`
}

export default function AdminDashboard() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [stats, setStats] = useState<StatCard[]>([])
  const [recentActivity, setRecentActivity] = useState<
    { action: string; user: string; time: string; type: string }[]
  >([])
  const [activityUnavailable, setActivityUnavailable] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    setActivityUnavailable(false)

    try {
      const [formsRes, contractsRes, trailRes, librarySummaryRes] = await Promise.allSettled([
        formConfigApi.listTemplates({ page_size: 1, is_active: true }),
        contractsApi.list(true),
        auditTrailApi.list({ page: 1, per_page: 5 }),
        libraryReviewApi.getDashboardSummary(),
      ])

      const formsTotal =
        formsRes.status === 'fulfilled'
          ? formsRes.value.total ?? formsRes.value.items?.length ?? 0
          : null
      const contractsTotal =
        contractsRes.status === 'fulfilled'
          ? contractsRes.value.total ?? contractsRes.value.items?.length ?? 0
          : null
      const librarySummary = librarySummaryRes.status === 'fulfilled' ? librarySummaryRes.value.data : null

      if (formsRes.status === 'rejected') {
        captureAdminLoadError(
          formsRes.reason,
          { component: 'AdminDashboard', action: 'loadForms' },
          '',
        )
      }
      if (contractsRes.status === 'rejected') {
        captureAdminLoadError(
          contractsRes.reason,
          { component: 'AdminDashboard', action: 'loadContracts' },
          '',
        )
      }
      if (trailRes.status === 'rejected') {
        captureAdminLoadError(
          trailRes.reason,
          { component: 'AdminDashboard', action: 'loadActivity' },
          '',
        )
      }
      if (librarySummaryRes.status === 'rejected') {
        captureAdminLoadError(
          librarySummaryRes.reason,
          { component: 'AdminDashboard', action: 'loadLibrarySummary' },
          '',
        )
      }

      setStats([
        {
          label: t('admin.dashboard.stat_active_forms', 'Active Forms'),
          value: formsTotal === null ? '—' : String(formsTotal),
          change:
            formsTotal === null
              ? t('admin.dashboard.stat_unavailable', 'Count unavailable')
              : t('admin.dashboard.stat_live', 'Live from API'),
          trend: 'neutral',
          icon: <FileText className="w-5 h-5" />,
          unavailable: formsTotal === null,
        },
        {
          label: t('admin.dashboard.stat_active_contracts', 'Active Contracts'),
          value: contractsTotal === null ? '—' : String(contractsTotal),
          change:
            contractsTotal === null
              ? t('admin.dashboard.stat_unavailable', 'Count unavailable')
              : t('admin.dashboard.stat_live', 'Live from API'),
          trend: 'neutral',
          icon: <Building className="w-5 h-5" />,
          unavailable: contractsTotal === null,
        },
        {
          label: t('admin.dashboard.stat_statutory_documents', 'Statutory Documents'),
          value: librarySummary === null ? '—' : String(librarySummary.statutory_documents),
          change:
            librarySummary === null
              ? t('admin.dashboard.stat_unavailable', 'Count unavailable')
              : t('admin.dashboard.stat_hseq_live', 'Live HSEQ library count'),
          trend: 'neutral',
          icon: <Shield className="w-5 h-5" />,
          unavailable: librarySummary === null,
        },
        {
          label: t('admin.dashboard.stat_overdue_reviews', 'Overdue Reviews'),
          value: librarySummary === null ? '—' : String(librarySummary.overdue_reviews),
          change:
            librarySummary === null
              ? t('admin.dashboard.stat_unavailable', 'Count unavailable')
              : t('admin.dashboard.stat_requires_hseq_attention', 'Requires HSEQ attention'),
          trend: librarySummary && librarySummary.overdue_reviews > 0 ? 'down' : 'neutral',
          icon: <Clock className="w-5 h-5" />,
          unavailable: librarySummary === null,
        },
        {
          label: t('admin.dashboard.stat_open_review_packs', 'Open Review Packs'),
          value: librarySummary === null ? '—' : String(librarySummary.open_review_packs),
          change:
            librarySummary === null
              ? t('admin.dashboard.stat_unavailable', 'Count unavailable')
              : t('admin.dashboard.stat_hseq_live', 'Live HSEQ library count'),
          trend: 'neutral',
          icon: <ClipboardList className="w-5 h-5" />,
          unavailable: librarySummary === null,
        },
      ])

      if (trailRes.status === 'fulfilled') {
        const entries = trailRes.value.data?.items ?? []
        setRecentActivity(
          entries.slice(0, 5).map((entry) => {
            const actionType =
              entry.action === 'create'
                ? 'add'
                : entry.action === 'update'
                  ? 'edit'
                  : entry.action === 'delete'
                    ? 'settings'
                    : 'publish'
            return {
              action:
                entry.entity_name ||
                `${entry.action} on ${entry.entity_type} ${entry.entity_id}`,
              user: entry.user_name || 'System',
              time: formatTimeAgo(entry.timestamp || ''),
              type: actionType,
            }
          }),
        )
      } else {
        setRecentActivity([])
        setActivityUnavailable(true)
      }

      if (formsTotal === null || contractsTotal === null || librarySummary === null) {
        setLoadError(
          t(
            'admin.dashboard.load_unavailable',
            'Admin summary data could not be loaded. Quick actions remain available below.',
          ),
        )
      }
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void loadData()
  }, [loadData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                {t('admin.dashboard.title', 'Admin Dashboard')}
              </h1>
              <p className="text-muted-foreground mt-2">
                {t(
                  'admin.dashboard.subtitle',
                  'Manage forms, contracts, settings, and system configuration',
                )}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg',
                  loadError
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-green-100 text-green-700',
                )}
              >
                {loadError ? (
                  <AlertTriangle className="w-4 h-4" />
                ) : (
                  <CheckCircle className="w-4 h-4" />
                )}
                <span className="text-sm font-medium">
                  {loadError
                    ? t('admin.dashboard.partial_status', 'Partial data')
                    : t('admin.dashboard.system_healthy', 'System Healthy')}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {loadError && (
          <AdminLoadUnavailable
            testId="admin-dashboard-unavailable"
            title={t('admin.dashboard.unavailable_title', 'Admin summary unavailable')}
            description={loadError}
            onRetry={() => void loadData()}
          />
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((stat) => (
            <Card key={stat.label} className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="text-2xl font-bold text-foreground mt-1">{stat.value}</p>
                  <p
                    className={cn(
                      'text-xs mt-1 flex items-center gap-1',
                      stat.unavailable && 'text-warning',
                      stat.trend === 'up' && 'text-green-600',
                      stat.trend === 'down' && 'text-destructive',
                      stat.trend === 'neutral' && !stat.unavailable && 'text-muted-foreground',
                    )}
                  >
                    {stat.trend === 'up' && <TrendingUp className="w-3 h-3" />}
                    {stat.trend === 'down' && <TrendingUp className="w-3 h-3 rotate-180" />}
                    {stat.change}
                  </p>
                </div>
                <div className="p-2 bg-primary/10 text-primary rounded-lg">{stat.icon}</div>
              </div>
            </Card>
          ))}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            {t('admin.dashboard.quick_actions', 'Quick Actions')}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {QUICK_ACTIONS.map((action) => (
              <Card
                key={action.title}
                className="p-5 cursor-pointer hover:shadow-md transition-all group"
                onClick={() => navigate(action.href)}
              >
                <div className="flex items-start gap-4">
                  <div className={cn('p-3 rounded-xl', action.color)}>{action.icon}</div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                      {action.title}
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">{action.description}</p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                </div>
              </Card>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">
              {t('admin.dashboard.recent_activity', 'Recent Activity')}
            </h2>
            {activityUnavailable ? (
              <AdminLoadUnavailable
                testId="admin-dashboard-activity-unavailable"
                title={t('admin.dashboard.activity_unavailable', 'Recent activity unavailable')}
                description={t(
                  'admin.dashboard.activity_unavailable_description',
                  'Audit trail feed could not be loaded — this is not an empty activity log.',
                )}
                onRetry={() => void loadData()}
              />
            ) : recentActivity.length === 0 ? (
              <div className="text-center py-8">
                <Activity className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
                <p className="text-muted-foreground">
                  {t('admin.dashboard.no_recent_activity', 'No recent activity')}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((activity, index) => (
                  <div
                    key={`${activity.action}-${index}`}
                    className="flex items-start gap-3 pb-4 border-b border-border last:border-0 last:pb-0"
                  >
                    <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-primary/10 text-primary">
                      <Activity className="w-4 h-4" />
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
            )}
          </Card>

          <Card className="p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">
              {t('admin.dashboard.system_status', 'System Status')}
            </h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-800">API Server</p>
                    <p className="text-xs text-green-600">
                      {loadError
                        ? t('admin.dashboard.api_degraded', 'Some admin APIs unavailable')
                        : t('admin.dashboard.api_ok', 'Admin APIs responding')}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-800">Database</p>
                    <p className="text-xs text-green-600">Connected</p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-800">Authentication</p>
                    <p className="text-xs text-green-600">Session active</p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  )
}
