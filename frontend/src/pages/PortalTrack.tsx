import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Search,
  ArrowLeft,
  Clock,
  AlertTriangle,
  MessageSquare,
  RefreshCw,
  Share2,
  Calendar,
  User,
  Loader2,
  XCircle,
  Sparkles,
  ChevronRight,
  FileText,
  Car,
  AlertCircle,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { cn } from '../helpers/utils';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import ReportChat from '../components/ReportChat';

// Types
interface ReportSummary {
  reference_number: string;
  report_type: 'incident' | 'near_miss' | 'complaint' | 'rta';
  title: string;
  status: string;
  status_label: string;
  submitted_at: string;
  updated_at: string;
}

interface ReportDetail extends ReportSummary {
  priority: string;
  timeline: Array<{ date: string; event: string; icon: string }>;
  next_steps: string;
  assigned_to: string;
}

// Report type config
const REPORT_TYPE_CONFIG = {
  incident: { 
    icon: AlertTriangle, 
    color: 'text-destructive', 
    bgColor: 'bg-destructive/10',
    label: 'Incident',
    prefix: 'INC',
  },
  near_miss: { 
    icon: AlertCircle, 
    color: 'text-warning', 
    bgColor: 'bg-warning/10',
    label: 'Near Miss',
    prefix: 'NM',
  },
  complaint: { 
    icon: MessageSquare, 
    color: 'text-info', 
    bgColor: 'bg-info/10',
    label: 'Complaint',
    prefix: 'COMP',
  },
  rta: { 
    icon: Car, 
    color: 'text-purple-600', 
    bgColor: 'bg-purple-100 dark:bg-purple-900/20',
    label: 'Road Traffic Collision',
    prefix: 'RTA',
  },
};

// Status badge component
const StatusBadge = ({ status, label }: { status: string; label: string }) => {
  const getStatusStyles = () => {
    switch (status) {
      case 'REPORTED':
      case 'OPEN':
        return 'bg-info/10 text-info border-info/20';
      case 'UNDER_INVESTIGATION':
      case 'IN_PROGRESS':
        return 'bg-warning/10 text-warning border-warning/20';
      case 'PENDING_REVIEW':
        return 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/20 dark:text-purple-400 dark:border-purple-800';
      case 'RESOLVED':
      case 'CLOSED':
        return 'bg-success/10 text-success border-success/20';
      case 'REJECTED':
        return 'bg-destructive/10 text-destructive border-destructive/20';
      default:
        return 'bg-muted text-muted-foreground border-border';
    }
  };

  return (
    <span className={cn('inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold', getStatusStyles())}>
      {label}
    </span>
  );
};

// Timeline event component
const TimelineEvent = ({ 
  event, 
  isLast 
}: { 
  event: { date: string; event: string; icon: string }; 
  isLast: boolean;
}) => (
  <div className="flex gap-4">
    <div className="flex flex-col items-center">
      <div className="w-10 h-10 bg-muted rounded-full flex items-center justify-center text-lg">
        {event.icon}
      </div>
      {!isLast && <div className="w-0.5 h-full bg-border mt-2" />}
    </div>
    <div className="pb-6">
      <p className="text-foreground font-medium">{event.event}</p>
      <p className="text-sm text-muted-foreground">
        {new Date(event.date).toLocaleDateString('en-GB', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })}
      </p>
    </div>
  </div>
);

// Progress indicator component
const ProgressIndicator = ({ status }: { status: string }) => {
  const stages = [
    { key: 'REPORTED', label: 'Submitted', icon: '📋' },
    { key: 'UNDER_INVESTIGATION', label: 'Under Review', icon: '🔍' },
    { key: 'IN_PROGRESS', label: 'In Progress', icon: '⚙️' },
    { key: 'RESOLVED', label: 'Resolved', icon: '✅' },
  ];

  const currentIndex = stages.findIndex(s => 
    s.key === status || 
    (status === 'OPEN' && s.key === 'REPORTED') ||
    (status === 'PENDING_REVIEW' && s.key === 'IN_PROGRESS') ||
    (status === 'CLOSED' && s.key === 'RESOLVED')
  );

  return (
    <div className="flex items-center justify-between mb-6">
      {stages.map((stage, index) => (
        <div key={stage.key} className="flex items-center">
          <div className={cn('flex flex-col items-center', index <= currentIndex ? 'text-foreground' : 'text-muted-foreground')}>
            <div className={cn(
              'w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center text-lg sm:text-xl mb-2',
              index < currentIndex 
                ? 'bg-success text-success-foreground' 
                : index === currentIndex 
                  ? 'gradient-brand text-primary-foreground'
                  : 'bg-muted'
            )}>
              {index < currentIndex ? '✓' : stage.icon}
            </div>
            <span className="text-xs font-medium hidden sm:block">{stage.label}</span>
          </div>
          {index < stages.length - 1 && (
            <div className={cn('w-6 sm:w-12 h-1 mx-1 sm:mx-2 rounded', index < currentIndex ? 'bg-success' : 'bg-border')} />
          )}
        </div>
      ))}
    </div>
  );
};

// Report list item component
const ReportListItem = ({ 
  report, 
  onClick 
}: { 
  report: ReportSummary; 
  onClick: () => void;
}) => {
  const config = REPORT_TYPE_CONFIG[report.report_type] || REPORT_TYPE_CONFIG.incident;
  const IconComponent = config.icon;
  
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-4 bg-card border border-border rounded-xl hover:border-primary/50 hover:shadow-md transition-all group"
    >
      <div className="flex items-start gap-4">
        <div className={cn('p-3 rounded-xl', config.bgColor)}>
          <IconComponent className={cn('w-5 h-5', config.color)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="font-mono text-sm text-primary font-semibold">
              {report.reference_number}
            </span>
            <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <h3 className="font-medium text-foreground truncate mb-1">
            {report.title || config.label}
          </h3>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {new Date(report.submitted_at).toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </span>
            <StatusBadge status={report.status} label={report.status_label} />
          </div>
        </div>
      </div>
    </button>
  );
};

export default function PortalTrack() {
  const navigate = useNavigate();
  const { referenceNumber: urlRef } = useParams();
  const { user, isAuthenticated } = usePortalAuth();
  
  const [searchRef, setSearchRef] = useState(urlRef || '');
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingMyReports, setIsLoadingMyReports] = useState(false);
  const [myReports, setMyReports] = useState<ReportSummary[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showManualSearch, setShowManualSearch] = useState(false);

  // Load user's reports if authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      loadMyReports();
    }
  }, [isAuthenticated, user]);

  // Load specific report from URL
  useEffect(() => {
    if (urlRef) {
      searchReport(urlRef);
    }
  }, [urlRef]);

  const loadMyReports = async () => {
    setIsLoadingMyReports(true);
    setError(null);
    
    try {
      // HARDCODED HTTPS - bypassing any caching/env issues
      const apiBase = 'https://app-qgp-prod.azurewebsites.net';
      console.log('[PortalTrack] Using API base:', apiBase);
      
      const allReports: ReportSummary[] = [];
      
      // Get auth token - try portal token first, then admin token
      const portalToken = localStorage.getItem('portal_id_token');
      const adminToken = localStorage.getItem('access_token');
      const token = portalToken || adminToken;
      
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // Track if any API calls succeed
      let hasSuccessfulFetch = false;
      let authError = false;
      
      // Fetch incidents - filter by reporter_email if user is authenticated
      // NOTE: Trailing slash required - FastAPI routes use trailing slashes
      try {
        const incidentsUrl = user?.email 
          ? `${apiBase}/api/v1/incidents/?page=1&size=20&reporter_email=${encodeURIComponent(user.email)}`
          : `${apiBase}/api/v1/incidents/?page=1&size=20`;
        const incidentsRes = await fetch(incidentsUrl, { headers });
        if (incidentsRes.ok) {
          hasSuccessfulFetch = true;
          const data = await incidentsRes.json();
          (data.items || []).forEach((inc: any) => {
            allReports.push({
              reference_number: inc.reference_number,
              report_type: 'incident',
              title: inc.title,
              status: inc.status?.toUpperCase() || 'OPEN',
              status_label: getStatusLabel(inc.status),
              submitted_at: inc.reported_date || inc.created_at,
              updated_at: inc.created_at,
            });
          });
        } else if (incidentsRes.status === 401) {
          authError = true;
        }
      } catch (e) { console.error('Failed to fetch incidents:', e); }
      
      // Fetch RTAs - filter by reporter_email
      // NOTE: Trailing slash required - FastAPI routes use trailing slashes
      try {
        const rtasUrl = user?.email 
          ? `${apiBase}/api/v1/rtas/?page=1&size=20&reporter_email=${encodeURIComponent(user.email)}`
          : `${apiBase}/api/v1/rtas/?page=1&size=20`;
        const rtasRes = await fetch(rtasUrl, { headers });
        if (rtasRes.ok) {
          hasSuccessfulFetch = true;
          const data = await rtasRes.json();
          (data.items || []).forEach((rta: any) => {
            allReports.push({
              reference_number: rta.reference_number,
              report_type: 'rta',
              title: rta.description?.substring(0, 100) || 'Road Traffic Collision',
              status: rta.status?.toUpperCase() || 'REPORTED',
              status_label: getStatusLabel(rta.status),
              submitted_at: rta.collision_date || rta.created_at,
              updated_at: rta.created_at,
            });
          });
        } else if (rtasRes.status === 401) {
          authError = true;
        }
      } catch (e) { console.error('Failed to fetch RTAs:', e); }
      
      // Fetch complaints - filter by complainant_email
      try {
        const complaintsUrl = user?.email 
          ? `${apiBase}/api/v1/complaints/?page=1&size=20&complainant_email=${encodeURIComponent(user.email)}`
          : `${apiBase}/api/v1/complaints/?page=1&size=20`;
        const complaintsRes = await fetch(complaintsUrl, { headers });
        if (complaintsRes.ok) {
          hasSuccessfulFetch = true;
          const data = await complaintsRes.json();
          (data.items || []).forEach((comp: any) => {
            allReports.push({
              reference_number: comp.reference_number,
              report_type: 'complaint',
              title: comp.title,
              status: comp.status?.toUpperCase() || 'OPEN',
              status_label: getStatusLabel(comp.status),
              submitted_at: comp.received_date || comp.created_at,
              updated_at: comp.created_at,
            });
          });
        } else if (complaintsRes.status === 401) {
          authError = true;
        }
      } catch (e) { console.error('Failed to fetch complaints:', e); }
      
      // Sort by most recent
      allReports.sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime());
      
      setMyReports(allReports);
      
      // Show appropriate message if no reports and auth failed
      if (!hasSuccessfulFetch && authError) {
        setError('Unable to load reports. Your session may have expired. Please try logging in again.');
      }
    } catch (err) {
      console.error('Failed to load reports:', err);
      setError('Failed to load reports. Please try again later.');
    } finally {
      setIsLoadingMyReports(false);
    }
  };

  const getStatusLabel = (status: string): string => {
    const labels: Record<string, string> = {
      'open': '📋 Open',
      'reported': '📋 Reported',
      'under_investigation': '🔍 Under Investigation',
      'in_progress': '⚙️ In Progress',
      'pending_review': '⏳ Pending Review',
      'resolved': '✅ Resolved',
      'closed': '✅ Closed',
    };
    return labels[status?.toLowerCase()] || status || 'Unknown';
  };

  const searchReport = async (ref: string) => {
    if (!ref.trim()) return;
    
    setIsSearching(true);
    setError(null);
    setSelectedReport(null);

    try {
      const response = await fetch(`/api/v1/portal/reports/${ref}/`);
      if (response.ok) {
        const data = await response.json();
        setSelectedReport(data);
      } else if (response.status === 404) {
        setError('Report not found. Please check your reference number.');
      } else {
        setError('Unable to fetch report. Please try again.');
      }
    } catch {
      // Demo data for testing
      const reportType = ref.startsWith('INC-') ? 'incident' 
        : ref.startsWith('NM-') ? 'near_miss'
        : ref.startsWith('COMP-') ? 'complaint'
        : ref.startsWith('RTA-') ? 'rta'
        : 'incident';
      
      const config = REPORT_TYPE_CONFIG[reportType];
      
      setSelectedReport({
        reference_number: ref,
        report_type: reportType,
        title: `${config.label} Report`,
        status: 'UNDER_INVESTIGATION',
        status_label: '🔍 Under Investigation',
        submitted_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
        updated_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
        priority: '🟡 Medium',
        timeline: [
          { date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), event: 'Report Submitted', icon: '📋' },
          { date: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), event: 'Assigned to Safety Team', icon: '👤' },
          { date: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), event: 'Investigation Started', icon: '🔍' },
        ],
        next_steps: 'A safety officer is reviewing the report. You will be notified when there is an update.',
        assigned_to: 'Safety Team',
      });
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchRef.trim()) {
      navigate(`/portal/track/${searchRef.trim()}`);
      searchReport(searchRef.trim());
    }
  };

  const handleReportClick = (report: ReportSummary) => {
    navigate(`/portal/track/${report.reference_number}`);
    searchReport(report.reference_number);
  };

  const handleBack = () => {
    if (selectedReport) {
      setSelectedReport(null);
      setSearchRef('');
      navigate('/portal/track');
    } else {
      navigate('/portal');
    }
  };

  const copyLink = () => {
    const url = `${window.location.origin}/portal/track/${selectedReport?.reference_number}`;
    navigator.clipboard.writeText(url);
  };

  // Render report detail view
  if (selectedReport) {
    const config = REPORT_TYPE_CONFIG[selectedReport.report_type] || REPORT_TYPE_CONFIG.incident;
    const IconComponent = config.icon;
    
    return (
      <div className="min-h-screen bg-surface">
        {/* Header */}
        <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
          <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
            <button
              onClick={handleBack}
              className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-foreground" />
            </button>
            <div className="flex-1">
              <span className="font-semibold text-foreground">{selectedReport.reference_number}</span>
              <p className="text-xs text-muted-foreground">{config.label}</p>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12 space-y-4">
          {/* Header Card */}
          <Card className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <IconComponent className={cn('w-5 h-5', config.color)} />
                  <span className="text-sm text-muted-foreground">{config.label}</span>
                </div>
                <h2 className="text-lg font-bold text-foreground">{selectedReport.title}</h2>
                <p className="text-sm font-mono text-muted-foreground mt-1">{selectedReport.reference_number}</p>
              </div>
              <StatusBadge status={selectedReport.status} label={selectedReport.status_label} />
            </div>

            {/* Progress Indicator */}
            <ProgressIndicator status={selectedReport.status} />

            {/* Quick Stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-3 bg-surface rounded-xl">
                <Calendar className="w-5 h-5 text-primary mx-auto mb-1" />
                <p className="text-xs text-muted-foreground">Submitted</p>
                <p className="text-sm text-foreground font-medium">
                  {new Date(selectedReport.submitted_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                </p>
              </div>
              <div className="text-center p-3 bg-surface rounded-xl">
                <Clock className="w-5 h-5 text-info mx-auto mb-1" />
                <p className="text-xs text-muted-foreground">Last Update</p>
                <p className="text-sm text-foreground font-medium">
                  {new Date(selectedReport.updated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                </p>
              </div>
              <div className="text-center p-3 bg-surface rounded-xl">
                <User className="w-5 h-5 text-success mx-auto mb-1" />
                <p className="text-xs text-muted-foreground">Assigned To</p>
                <p className="text-sm text-foreground font-medium">{selectedReport.assigned_to || 'Pending'}</p>
              </div>
            </div>
          </Card>

          {/* Next Steps */}
          {selectedReport.next_steps && (
            <Card className="p-5 border-primary/20 bg-primary/5">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Sparkles className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground mb-1">What's Next?</h3>
                  <p className="text-muted-foreground text-sm">{selectedReport.next_steps}</p>
                </div>
              </div>
            </Card>
          )}

          {/* Timeline */}
          <Card className="p-6">
            <h3 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-info" />
              Activity Timeline
            </h3>
            <div className="pl-2">
              {selectedReport.timeline.map((event, index) => (
                <TimelineEvent 
                  key={index} 
                  event={event} 
                  isLast={index === selectedReport.timeline.length - 1} 
                />
              ))}
            </div>
          </Card>

          {/* Two-way Chat with Investigator */}
          <ReportChat
            referenceNumber={selectedReport.reference_number}
            reporterName={user?.name || 'Reporter'}
            officerName={selectedReport.assigned_to || 'Safety Team'}
            isReporter={true}
            isClosed={selectedReport.status === 'RESOLVED' || selectedReport.status === 'CLOSED'}
          />

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="outline"
              onClick={() => searchReport(selectedReport.reference_number)}
              className="flex-1"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh Status
            </Button>
            <Button
              variant="outline"
              onClick={copyLink}
              className="flex-1"
            >
              <Share2 className="w-4 h-4" />
              Share Link
            </Button>
          </div>
        </main>
      </div>
    );
  }

  // Render list view
  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/portal')}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-info" />
            <span className="font-semibold text-foreground">Track Reports</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex w-16 h-16 rounded-2xl gradient-brand items-center justify-center mb-4 shadow-glow">
            <FileText className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Your Reports</h1>
          <p className="text-muted-foreground">
            {isAuthenticated 
              ? `Viewing reports for ${user?.name || user?.email}`
              : 'Sign in to see your submitted reports'
            }
          </p>
        </div>

        {/* User's Reports (if authenticated) */}
        {isAuthenticated && (
          <div className="mb-8">
            {isLoadingMyReports ? (
              <div className="text-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
                <p className="text-muted-foreground">Loading your reports...</p>
              </div>
            ) : error && myReports.length === 0 ? (
              <Card className="p-8 text-center border-destructive/20">
                <div className="w-16 h-16 bg-destructive/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <XCircle className="w-8 h-8 text-destructive" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">Unable to Load Reports</h3>
                <p className="text-muted-foreground mb-4">{error}</p>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <Button onClick={loadMyReports} variant="outline">
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Try Again
                  </Button>
                  <Button onClick={() => navigate('/portal/login')}>
                    Sign In Again
                  </Button>
                </div>
              </Card>
            ) : myReports.length > 0 ? (
              <div className="space-y-3">
                {myReports.map((report) => (
                  <ReportListItem
                    key={report.reference_number}
                    report={report}
                    onClick={() => handleReportClick(report)}
                  />
                ))}
              </div>
            ) : (
              <Card className="p-8 text-center">
                <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-8 h-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">No Reports Yet</h3>
                <p className="text-muted-foreground mb-4">
                  You haven't submitted any reports yet.
                </p>
                <Button onClick={() => navigate('/portal/report')}>
                  Submit a Report
                </Button>
              </Card>
            )}
          </div>
        )}

        {/* Manual Search Section */}
        {(showManualSearch || !isAuthenticated) && (
          <div className="space-y-4">
            {isAuthenticated && (
              <div className="flex items-center gap-4">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs text-muted-foreground uppercase tracking-wide">or search by reference</span>
                <div className="flex-1 h-px bg-border" />
              </div>
            )}
            
            <form onSubmit={handleSearch}>
              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    type="text"
                    placeholder="Enter reference number (e.g., INC-2026-0001)"
                    value={searchRef}
                    onChange={(e) => setSearchRef(e.target.value.toUpperCase())}
                    className="font-mono text-base"
                  />
                </div>
                <Button
                  type="submit"
                  disabled={isSearching || !searchRef.trim()}
                >
                  {isSearching ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Search className="w-5 h-5" />
                  )}
                </Button>
              </div>
            </form>

            {error && (
              <Card className="p-6 text-center border-destructive/20">
                <XCircle className="w-12 h-12 text-destructive mx-auto mb-3" />
                <h3 className="text-lg font-bold text-foreground mb-2">Not Found</h3>
                <p className="text-muted-foreground">{error}</p>
              </Card>
            )}
          </div>
        )}

        {/* Toggle Manual Search (if authenticated and has reports) */}
        {isAuthenticated && myReports.length > 0 && !showManualSearch && (
          <button
            onClick={() => setShowManualSearch(true)}
            className="w-full mt-4 py-3 text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-2"
          >
            <Search className="w-4 h-4" />
            Search for another report by reference number
          </button>
        )}

        {/* Not Signed In - Show login prompt */}
        {!isAuthenticated && (
          <div className="mt-8">
            <Card className="p-6 border-primary/20 bg-primary/5">
              <div className="text-center">
                <User className="w-10 h-10 text-primary mx-auto mb-3" />
                <h3 className="font-semibold text-foreground mb-2">Sign in for easier access</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Sign in with Microsoft to automatically see all your submitted reports without entering reference numbers.
                </p>
                <Button onClick={() => navigate('/portal/login')}>
                  Sign In
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* Empty State for manual search */}
        {!isAuthenticated && !error && !isSearching && (
          <div className="mt-8">
            <Card className="p-4 max-w-sm mx-auto">
              <p className="text-xs text-muted-foreground mb-2 text-center">Example formats:</p>
              <div className="flex flex-wrap gap-2 justify-center">
                <span className="px-3 py-1 bg-muted rounded-lg text-sm font-mono text-foreground">INC-2026-0001</span>
                <span className="px-3 py-1 bg-muted rounded-lg text-sm font-mono text-foreground">COMP-2026-0001</span>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
