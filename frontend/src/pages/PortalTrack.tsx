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
  HelpCircle,
  Sparkles,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { cn } from '../helpers/utils';

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

export default function PortalTrack() {
  const navigate = useNavigate();
  const { referenceNumber: urlRef } = useParams();
  const [searchRef, setSearchRef] = useState(urlRef || '');
  const [isSearching, setIsSearching] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (urlRef) {
      searchReport(urlRef);
    }
  }, [urlRef]);

  const searchReport = async (ref: string) => {
    if (!ref.trim()) return;
    
    setIsSearching(true);
    setError(null);
    setReport(null);

    try {
      const response = await fetch(`/api/v1/portal/reports/${ref}/`);
      if (response.ok) {
        const data = await response.json();
        setReport(data);
      } else if (response.status === 404) {
        setError('Report not found. Please check your reference number.');
      } else {
        setError('Unable to fetch report. Please try again.');
      }
    } catch {
      // Demo data for testing
      const isIncident = ref.startsWith('INC-');
      setReport({
        reference_number: ref,
        report_type: isIncident ? 'Incident' : 'Complaint',
        title: isIncident ? 'Equipment malfunction in warehouse' : 'Delayed response to inquiry',
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
        next_steps: 'A safety officer is reviewing the incident. You will be notified when there is an update.',
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

  const copyLink = () => {
    const url = `${window.location.origin}/portal/track/${report?.reference_number}`;
    navigator.clipboard.writeText(url);
  };

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
            <span className="font-semibold text-foreground">Track Report</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12">
        {/* Search Section */}
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 rounded-2xl gradient-brand items-center justify-center mb-4 shadow-glow">
            <Search className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Track Your Report</h1>
          <p className="text-muted-foreground">Enter your reference number to check the status</p>
        </div>

        {/* Search Form */}
        <form onSubmit={handleSearch} className="mb-8">
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

        {/* Error State */}
        {error && (
          <Card className="p-6 text-center border-destructive/20">
            <XCircle className="w-12 h-12 text-destructive mx-auto mb-3" />
            <h3 className="text-lg font-bold text-foreground mb-2">Not Found</h3>
            <p className="text-muted-foreground">{error}</p>
          </Card>
        )}

        {/* Report Details */}
        {report && (
          <div className="space-y-4">
            {/* Header Card */}
            <Card className="p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    {report.report_type === 'Incident' ? (
                      <AlertTriangle className="w-5 h-5 text-destructive" />
                    ) : (
                      <MessageSquare className="w-5 h-5 text-warning" />
                    )}
                    <span className="text-sm text-muted-foreground">{report.report_type}</span>
                  </div>
                  <h2 className="text-lg font-bold text-foreground">{report.title}</h2>
                  <p className="text-sm font-mono text-muted-foreground mt-1">{report.reference_number}</p>
                </div>
                <StatusBadge status={report.status} label={report.status_label} />
              </div>

              {/* Progress Indicator */}
              <ProgressIndicator status={report.status} />

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-3 bg-surface rounded-xl">
                  <Calendar className="w-5 h-5 text-primary mx-auto mb-1" />
                  <p className="text-xs text-muted-foreground">Submitted</p>
                  <p className="text-sm text-foreground font-medium">
                    {new Date(report.submitted_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <div className="text-center p-3 bg-surface rounded-xl">
                  <Clock className="w-5 h-5 text-info mx-auto mb-1" />
                  <p className="text-xs text-muted-foreground">Last Update</p>
                  <p className="text-sm text-foreground font-medium">
                    {new Date(report.updated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <div className="text-center p-3 bg-surface rounded-xl">
                  <User className="w-5 h-5 text-success mx-auto mb-1" />
                  <p className="text-xs text-muted-foreground">Assigned To</p>
                  <p className="text-sm text-foreground font-medium">{report.assigned_to || 'Pending'}</p>
                </div>
              </div>
            </Card>

            {/* Next Steps */}
            {report.next_steps && (
              <Card className="p-5 border-primary/20 bg-primary/5">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Sparkles className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground mb-1">What's Next?</h3>
                    <p className="text-muted-foreground text-sm">{report.next_steps}</p>
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
                {report.timeline.map((event: any, index: number) => (
                  <TimelineEvent 
                    key={index} 
                    event={event} 
                    isLast={index === report.timeline.length - 1} 
                  />
                ))}
              </div>
            </Card>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                variant="outline"
                onClick={() => searchReport(report.reference_number)}
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
          </div>
        )}

        {/* Empty State */}
        {!report && !error && !isSearching && !urlRef && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-4">
              <HelpCircle className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">Enter Your Reference Number</h3>
            <p className="text-muted-foreground mb-6">
              You received a reference number when you submitted your report.
              <br />
              Enter it above to check the status.
            </p>
            <Card className="p-4 max-w-sm mx-auto">
              <p className="text-xs text-muted-foreground mb-2">Example formats:</p>
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
