import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText,
  Search,
  HelpCircle,
  ChevronRight,
  Smartphone,
  LogOut,
  User,
  Briefcase,
  Bell,
  GraduationCap,
  Wrench,
  Truck,
  ClipboardCheck,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Info,
  Layers,
} from 'lucide-react'
import { BrandMarkTile } from '../components/BrandMark'
import { usePortalAuth } from '../contexts/PortalAuthContext'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import {
  actionsApi,
  auditsApi,
  documentCampaignApi,
  portalComplianceApi,
  trainingMatrixApi,
  type PortalMyCompliance,
} from '../api/client'
import { assignedAuditQueueTotal } from './portalAssignedAuditsHonesty'
import { Card } from '../components/ui/Card'
import { ThemeToggle } from '../components/ui/ThemeToggle'
import { cn } from '../helpers/utils'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { countOpenAssignedActions } from '../utils/portalHonestyHelpers'
import { isGapStatus } from './workforce/trainingMatrix/trainingMatrixBoardHelpers'

function clearStateCopy(state: PortalMyCompliance['clear_state']): {
  title: string
  detail: string
} {
  if (state === 'blocked') {
    return {
      title: 'Not clear to work',
      detail: 'Quarantined tools or P1 faults need attention before you start.',
    }
  }
  if (state === 'attention') {
    return {
      title: 'Needs attention',
      detail: 'Overdue tools, due-soon kit, or open faults on your van.',
    }
  }
  if (state === 'no_data') {
    return {
      title: 'Nothing to report yet',
      detail: 'No assets or van are recorded against you, so there is nothing to check.',
    }
  }
  return {
    title: 'Clear to work',
    detail: 'Your tools and van checks look OK right now.',
  }
}

function vanHomeSubtitle(summary: PortalMyCompliance['van_summary']): string {
  if (summary.vehicle_reg) {
    return `${summary.vehicle_reg} · daily & monthly`
  }
  switch (summary.empty_reason) {
    case 'no_driver_profile':
      return 'Driver profile not linked'
    case 'no_van':
      return 'No van allocated'
    case 'assignment_conflict':
      return 'Assignment needs admin review'
    case 'multiple_assigned':
      return 'Multiple vans assigned — contact admin'
    default:
      return 'Daily and monthly checks · open faults'
  }
}

export default function Portal() {
  const navigate = useNavigate()
  const jobLifecycleEnabled = useFeatureFlag('job_lifecycle')
  const { user, logout } = usePortalAuth()
  const { announce } = useLiveAnnouncer()
  const [pendingCampaignCount, setPendingCampaignCount] = useState(0)
  const [openActionsCount, setOpenActionsCount] = useState(0)
  const [trainingGapCount, setTrainingGapCount] = useState(0)
  const [compliance, setCompliance] = useState<PortalMyCompliance | null>(null)
  const [complianceFailed, setComplianceFailed] = useState(false)
  const [auditQueueFailed, setAuditQueueFailed] = useState(false)
  const [auditQueueTotal, setAuditQueueTotal] = useState<number | undefined>(undefined)

  useEffect(() => {
    announce('Employee portal loaded')
  }, [announce])

  useEffect(() => {
    void documentCampaignApi
      .listMyAssignments()
      .then((response) => {
        const pending = (response.data.items ?? []).filter(
          (item) => item.status !== 'completed',
        ).length
        setPendingCampaignCount(pending)
      })
      .catch(() => {
        setPendingCampaignCount(0)
      })
    void actionsApi
      .list(1, 50, undefined, undefined, undefined, { assigned_to: 'me' })
      .then((response) => {
        const items = response.data.items ?? []
        setOpenActionsCount(countOpenAssignedActions(items))
      })
      .catch(() => {
        setOpenActionsCount(0)
      })
    void trainingMatrixApi
      .myTraining()
      .then((res) => {
        setTrainingGapCount((res.items || []).filter((row) => isGapStatus(row.status)).length)
      })
      .catch(() => {
        setTrainingGapCount(0)
      })
    void portalComplianceApi
      .myCompliance()
      .then((res) => {
        setCompliance(res)
        setComplianceFailed(false)
      })
      .catch(() => {
        setCompliance(null)
        setComplianceFailed(true)
      })
    void auditsApi
      .listAssignedToMe(1, 100)
      .then((response) => {
        setAuditQueueTotal(response.data.total)
        setAuditQueueFailed(false)
      })
      .catch(() => {
        setAuditQueueTotal(undefined)
        setAuditQueueFailed(true)
      })
  }, [])

  // My Work badge = open assigned actions + pending reading (PX-305).
  const myWorkBadgeCount = pendingCampaignCount + openActionsCount
  const shownAuditTotal = assignedAuditQueueTotal(auditQueueTotal, auditQueueFailed)

  const handleLogout = () => {
    logout()
    navigate('/portal/login')
  }

  return (
    <div data-testid="portal-home" className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BrandMarkTile size={40} />
              <div>
                <h1 className="text-foreground font-semibold">Plantexpand</h1>
                <p className="text-muted-foreground text-xs">Employee Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="p-2 hover:bg-surface rounded-lg transition-colors"
                title="Sign out"
              >
                <LogOut className="w-5 h-5 text-muted-foreground hover:text-foreground" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-8">
        {/* User Welcome Card */}
        <Card className="p-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
              <User className="w-6 h-6 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-foreground font-semibold">{user?.name || 'Employee'}</p>
              <p className="text-muted-foreground text-sm">{user?.email}</p>
            </div>
          </div>
        </Card>

        {/* Welcome Message */}
        <div className="text-center mb-6">
          <h2 className="text-2xl font-semibold text-foreground mb-2">
            What would you like to do?
          </h2>
          <p className="text-muted-foreground">Select an option below</p>
        </div>

        {/* Clear-to-work + tool/van (before Report / Work / Training) */}
        {complianceFailed && (
          <Card
            className="p-4 mb-4 border-amber-500/30 bg-amber-500/5"
            data-testid="portal-compliance-failed"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-foreground">Couldn’t load tool & van status</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Check your connection and refresh — we won’t show fake zeros.
                </p>
              </div>
            </div>
          </Card>
        )}

        {compliance && (
          <div
            data-testid="portal-clear-to-work"
            className={cn(
              'mb-4 rounded-2xl border-2 p-4',
              compliance.clear_state === 'blocked' && 'border-destructive/40 bg-destructive/5',
              compliance.clear_state === 'attention' && 'border-amber-500/40 bg-amber-500/5',
              compliance.clear_state === 'clear' && 'border-emerald-500/30 bg-emerald-500/5',
              compliance.clear_state === 'no_data' && 'border-border bg-muted/40',
            )}
          >
            <div className="flex items-start gap-3">
              {compliance.clear_state === 'clear' ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
              ) : compliance.clear_state === 'blocked' ? (
                <ShieldAlert className="w-6 h-6 text-destructive shrink-0" />
              ) : compliance.clear_state === 'no_data' ? (
                <Info className="w-6 h-6 text-muted-foreground shrink-0" />
              ) : (
                <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
              )}
              <div>
                <p className="font-semibold text-foreground">
                  {clearStateCopy(compliance.clear_state).title}
                </p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {clearStateCopy(compliance.clear_state).detail}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Main Actions */}
        <div className="space-y-3">
          <button
            data-testid="portal-tools-btn"
            type="button"
            aria-label={
              compliance && compliance.tool_badge > 0
                ? `My asset compliance — ${compliance.tool_badge} items need attention`
                : 'My asset compliance'
            }
            onClick={() => navigate('/portal/tools')}
            className={cn(
              'w-full flex items-center gap-4 p-5 rounded-2xl transition-all group relative',
              'bg-card hover:bg-muted/40 border-2 border-border hover:border-primary/30',
            )}
          >
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center relative">
              <Wrench className="w-7 h-7 text-primary" />
              {compliance && compliance.tool_badge > 0 && (
                <span
                  data-testid="portal-tools-badge"
                  className="absolute -top-1 -right-1 flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-xs font-semibold"
                >
                  {compliance.tool_badge}
                </span>
              )}
            </div>
            <div className="flex-1 text-left">
              <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                My asset compliance
              </h3>
              <p className="text-sm text-muted-foreground">
                {compliance
                  ? `${compliance.tool_summary.total} assets · ${compliance.tool_summary.overdue} overdue`
                  : 'Assigned assets and van kit'}
              </p>
            </div>
            <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>

          <button
            data-testid="portal-van-btn"
            type="button"
            aria-label={
              compliance && compliance.van_badge > 0
                ? `My van checks — ${compliance.van_badge} open faults`
                : 'My van checks'
            }
            onClick={() => navigate('/portal/van')}
            className={cn(
              'w-full flex items-center gap-4 p-5 rounded-2xl transition-all group relative',
              'bg-card hover:bg-muted/40 border-2 border-border hover:border-primary/30',
            )}
          >
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center relative">
              <Truck className="w-7 h-7 text-primary" />
              {compliance && compliance.van_badge > 0 && (
                <span
                  data-testid="portal-van-badge"
                  className="absolute -top-1 -right-1 flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-xs font-semibold"
                >
                  {compliance.van_badge}
                </span>
              )}
            </div>
            <div className="flex-1 text-left">
              <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                My van checks
              </h3>
              <p className="text-sm text-muted-foreground">
                {compliance
                  ? vanHomeSubtitle(compliance.van_summary)
                  : 'Daily and monthly checks · open faults'}
              </p>
            </div>
            <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Primary Action: Submit Report */}
          <button
            data-testid="portal-report-btn"
            onClick={() => navigate('/portal/report')}
            className={cn(
              'w-full flex items-center gap-4 p-5 rounded-2xl transition-all group',
              'bg-primary/5 hover:bg-primary/10 border-2 border-primary/20 hover:border-primary/40',
            )}
          >
            <div className="w-14 h-14 rounded-xl gradient-brand flex items-center justify-center shadow-glow">
              <FileText className="w-7 h-7 text-primary-foreground" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                Submit a Report
              </h3>
              <p className="text-sm text-muted-foreground">
                Incident, Near Miss, Complaint, or RTA
              </p>
            </div>
            <ChevronRight className="w-6 h-6 text-primary group-hover:translate-x-1 transition-transform" />
          </button>

          {/* My Work inbox (CUJ-P10) */}
          <button
            data-testid="portal-work-btn"
            type="button"
            aria-label={
              myWorkBadgeCount > 0
                ? `My Work — ${myWorkBadgeCount} items needing attention`
                : 'My Work — assigned actions and pending reading'
            }
            onClick={() => navigate('/portal/work')}
            className={cn(
              'w-full flex items-center gap-4 p-5 rounded-2xl transition-all group relative',
              'bg-card hover:bg-muted/40 border-2 border-border hover:border-primary/30',
            )}
          >
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center relative">
              <Briefcase className="w-7 h-7 text-primary" />
              {myWorkBadgeCount > 0 && (
                <span
                  data-testid="portal-work-pending-badge"
                  className="absolute -top-1 -right-1 flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-xs font-semibold"
                  aria-hidden="true"
                >
                  <Bell className="w-3 h-3" />
                  <span className="sr-only">{myWorkBadgeCount}</span>
                </span>
              )}
            </div>
            <div className="flex-1 text-left">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                  My Work
                </h3>
                {myWorkBadgeCount > 0 && (
                  <span
                    data-testid="portal-work-pending-count"
                    className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-destructive/10 text-destructive text-xs font-semibold"
                  >
                    {myWorkBadgeCount}
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground">Assigned actions and pending reading</p>
            </div>
            <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Assigned audits — logging-device entry (AUD-DEV-1) */}
          <button
            data-testid="portal-audits-btn"
            type="button"
            aria-label={
              shownAuditTotal && shownAuditTotal > 0
                ? `Audits — ${shownAuditTotal} assigned to you`
                : auditQueueFailed
                  ? 'Audits — could not load assigned audits'
                  : 'Audits — no audits assigned to you'
            }
            onClick={() => navigate('/portal/audits')}
            className={cn(
              'w-full flex items-center gap-4 p-5 rounded-2xl transition-all group relative',
              'bg-card hover:bg-muted/40 border-2 border-border hover:border-primary/30',
            )}
          >
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center relative">
              <ClipboardCheck className="w-7 h-7 text-primary" />
              {shownAuditTotal != null && shownAuditTotal > 0 ? (
                <span
                  data-testid="portal-audits-badge"
                  className="absolute -top-1 -right-1 flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-xs font-semibold"
                >
                  {shownAuditTotal}
                </span>
              ) : null}
            </div>
            <div className="flex-1 text-left">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                  Audits
                </h3>
                {shownAuditTotal != null && shownAuditTotal > 0 ? (
                  <span
                    data-testid="portal-audits-count"
                    className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-destructive/10 text-destructive text-xs font-semibold"
                  >
                    {shownAuditTotal}
                  </span>
                ) : null}
              </div>
              <p className="text-sm text-muted-foreground" data-testid="portal-audits-subtitle">
                {auditQueueFailed
                  ? 'Couldn’t load assigned audits'
                  : shownAuditTotal === 0
                    ? 'No audits assigned to you'
                    : shownAuditTotal != null
                      ? 'Assigned inspections for this device'
                      : 'Assigned inspections for this device'}
              </p>
            </div>
            <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Training — first-class (Atlas + QGP frequency), not buried under My Work */}
          <button
            data-testid="portal-training-btn"
            type="button"
            aria-label={
              trainingGapCount > 0
                ? `Training — ${trainingGapCount} modules need attention`
                : 'Training — view your required modules and due dates'
            }
            onClick={() => navigate('/portal/work#training')}
            className={cn(
              'w-full flex items-center gap-4 p-5 rounded-2xl transition-all group relative',
              'bg-card hover:bg-muted/40 border-2 border-border hover:border-primary/30',
            )}
          >
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center relative">
              <GraduationCap className="w-7 h-7 text-primary" />
              {trainingGapCount > 0 && (
                <span
                  data-testid="portal-training-pending-badge"
                  className="absolute -top-1 -right-1 flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-xs font-semibold"
                  aria-hidden="true"
                >
                  {trainingGapCount}
                </span>
              )}
            </div>
            <div className="flex-1 text-left">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                  Training
                </h3>
                {trainingGapCount > 0 && (
                  <span
                    data-testid="portal-training-pending-count"
                    className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-destructive/10 text-destructive text-xs font-semibold"
                  >
                    {trainingGapCount}
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                Required modules, due dates, and Atlas completion
              </p>
            </div>
            <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Job cycles — read-only nested packs (JL-UX-W5) */}
          {jobLifecycleEnabled ? (
            <button
              data-testid="portal-job-cycles-btn"
              type="button"
              onClick={() => navigate('/portal/job-cycles')}
              className={cn(
                'w-full flex items-center gap-4 p-4 rounded-2xl transition-all group text-left',
                'bg-card hover:bg-muted/40 border border-border hover:border-primary/30 cursor-pointer',
              )}
            >
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center">
                <Layers className="w-6 h-6 text-primary" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                  Job cycles
                </h3>
                <p className="text-sm text-muted-foreground">
                  Open nested process packs read-only
                </p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
            </button>
          ) : null}

          {/* Secondary Action: Track Status */}
          <button
            data-testid="portal-track-btn"
            type="button"
            onClick={() => navigate('/portal/track')}
            className={cn(
              'w-full flex items-center gap-4 p-4 rounded-2xl transition-all group text-left',
              'bg-card hover:bg-muted/40 border border-border hover:border-info/30 cursor-pointer',
            )}
          >
            <div className="w-12 h-12 bg-info/10 rounded-xl flex items-center justify-center">
              <Search className="w-6 h-6 text-info" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-foreground group-hover:text-info transition-colors">
                Track My Report
              </h3>
              <p className="text-sm text-muted-foreground">View your submitted reports and status</p>
            </div>
            <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Help & Support */}
          <button
            data-testid="portal-help-btn"
            type="button"
            onClick={() => navigate('/portal/help')}
            className={cn(
              'w-full flex items-center gap-4 p-4 rounded-2xl transition-all group text-left',
              'bg-card hover:bg-muted/40 border border-border hover:border-primary/30 cursor-pointer',
            )}
          >
            <div className="w-12 h-12 bg-muted rounded-xl flex items-center justify-center">
              <HelpCircle className="w-6 h-6 text-muted-foreground" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-foreground group-hover:text-foreground/80 transition-colors">
                Help & Support
              </h3>
              <p className="text-sm text-muted-foreground">FAQs and contact information</p>
            </div>
            <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        {/* Mobile Optimized Badge */}
        <div className="mt-10 flex items-center justify-center gap-2 text-muted-foreground text-sm">
          <Smartphone className="w-4 h-4" />
          <span>Optimized for mobile devices</span>
        </div>
      </main>
    </div>
  )
}
