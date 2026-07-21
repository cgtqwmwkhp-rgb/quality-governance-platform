import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  BarChart3,
  ClipboardCheck,
  FileText,
  GraduationCap,
  RefreshCw,
  Search,
  Shield,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { HighlightRail } from './dashboard/HighlightRail'
import { MyDaySection } from './dashboard/MyDaySection'
import { PulseTrendsStrip } from './dashboard/PulseTrendsStrip'
import { OrgCommandStrip } from './dashboard/OrgCommandStrip'
import { useDashboardData } from './dashboard/useDashboardData'
import {
  personaOrgStripIsCompact,
  personaShowsMyDay,
  personaShowsOrgStrip,
} from './dashboard/dashboardMetrics'

export default function Dashboard() {
  const {
    loading,
    error,
    persona,
    unreadCount,
    myDay,
    pulse,
    org,
    highlights,
    refresh,
  } = useDashboardData()

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-2">
            <div className="h-9 w-48 rounded bg-muted animate-pulse" />
            <div className="h-4 w-64 rounded bg-muted/70 animate-pulse" />
          </div>
        </div>
        <CardSkeleton count={1} className="grid-cols-1" />
        <CardSkeleton count={4} className="grid-cols-2 md:grid-cols-4" />
        <CardSkeleton count={3} className="grid-cols-1 md:grid-cols-3" />
      </div>
    )
  }

  const showMyDay = personaShowsMyDay(persona)
  const showOrg = personaShowsOrgStrip(persona)
  const orgCompact = personaOrgStripIsCompact(persona)

  return (
    <div className="space-y-6">
      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={refresh} className="text-sm font-medium text-destructive hover:underline">
            Try Again
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
          <p className="text-muted-foreground">Quality Governance Platform Overview</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" asChild>
            <Link to="/notifications">
              <Bell className="w-4 h-4" />
              <span className="hidden sm:inline">Notifications</span>
              {unreadCount > 0 && (
                <Badge variant="destructive" className="ml-2">
                  {unreadCount}
                </Badge>
              )}
            </Link>
          </Button>
          <Button onClick={refresh}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Live Highlight Rail (locked design §1) */}
      <HighlightRail chips={highlights} />

      {/* Persona-aware stage (locked design §2/§5) */}
      {showMyDay && <MyDaySection data={myDay} />}

      {showOrg && (
        <div className="space-y-4">
          {!orgCompact && (
            <h2 className="text-lg font-semibold text-foreground">Pulse &amp; trends</h2>
          )}
          <PulseTrendsStrip data={pulse} />
          {orgCompact && (
            <p className="text-xs text-muted-foreground">Compact org view — dual role detected.</p>
          )}
          <OrgCommandStrip data={org} compact={orgCompact} />
        </div>
      )}

      {/* Recent incidents (org personas only) */}
      {showOrg && org.recentIncidents.status === 'ok' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent Incidents</CardTitle>
            <Button variant="link" size="sm" asChild>
              <Link to="/incidents">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Reference
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Title
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Severity
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Status
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {org.recentIncidents.value.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-muted-foreground">
                        No incidents found
                      </td>
                    </tr>
                  ) : (
                    org.recentIncidents.value.map((incident) => (
                      <tr
                        key={incident.id}
                        className="border-b border-border/50 hover:bg-surface transition-colors"
                      >
                        <td className="py-3 px-4 text-sm text-primary font-mono">
                          {incident.reference_number}
                        </td>
                        <td className="py-3 px-4 text-sm text-foreground">{incident.title}</td>
                        <td className="py-3 px-4">
                          <Badge
                            variant={
                              incident.severity === 'critical'
                                ? 'critical'
                                : incident.severity === 'high'
                                  ? 'high'
                                  : incident.severity === 'medium'
                                    ? 'medium'
                                    : 'low'
                            }
                          >
                            {incident.severity}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">
                          <Badge
                            variant={
                              incident.status === 'closed'
                                ? 'resolved'
                                : incident.status === 'under_investigation'
                                  ? 'in-progress'
                                  : 'submitted'
                            }
                          >
                            {incident.status.replace('_', ' ')}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {new Date(incident.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Persona-aware quick actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {showMyDay ? (
          <>
            <Link to="/portal/report">
              <Card hoverable className="p-4 bg-primary/5 border-primary/20">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-primary" />
                  <span className="text-foreground font-medium">Submit a Report</span>
                </div>
              </Card>
            </Link>
            <Link to="/portal/work">
              <Card hoverable className="p-4 bg-info/5 border-info/20">
                <div className="flex items-center gap-3">
                  <Search className="w-5 h-5 text-info" />
                  <span className="text-foreground font-medium">My Work</span>
                </div>
              </Card>
            </Link>
            <Link to="/portal/work#training">
              <Card hoverable className="p-4 bg-success/5 border-success/20">
                <div className="flex items-center gap-3">
                  <GraduationCap className="w-5 h-5 text-success" />
                  <span className="text-foreground font-medium">Training</span>
                </div>
              </Card>
            </Link>
            <Link to="/portal/tools">
              <Card hoverable className="p-4 bg-warning/5 border-warning/20">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-warning" />
                  <span className="text-foreground font-medium">My Tools</span>
                </div>
              </Card>
            </Link>
          </>
        ) : (
          <>
            <Link to="/incidents">
              <Card hoverable className="p-4 bg-destructive/5 border-destructive/20">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-destructive" />
                  <span className="text-foreground font-medium">New Incident</span>
                </div>
              </Card>
            </Link>
            <Link to="/audits">
              <Card hoverable className="p-4 bg-info/5 border-info/20">
                <div className="flex items-center gap-3">
                  <ClipboardCheck className="w-5 h-5 text-info" />
                  <span className="text-foreground font-medium">Start Audit</span>
                </div>
              </Card>
            </Link>
            <Link to="/analytics">
              <Card hoverable className="p-4 bg-primary/5 border-primary/20">
                <div className="flex items-center gap-3">
                  <BarChart3 className="w-5 h-5 text-primary" />
                  <span className="text-foreground font-medium">View Analytics</span>
                </div>
              </Card>
            </Link>
            <Link to="/compliance">
              <Card hoverable className="p-4 bg-success/5 border-success/20">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-success" />
                  <span className="text-foreground font-medium">Compliance</span>
                </div>
              </Card>
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
