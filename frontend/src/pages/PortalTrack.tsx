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

// Animated background
const AnimatedBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900" />
    <div className="absolute top-0 -left-4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
    <div className="absolute bottom-0 -right-4 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
  </div>
);

// Status badge component
const StatusBadge = ({ status, label }: { status: string; label: string }) => {
  const getStatusStyles = () => {
    switch (status) {
      case 'REPORTED':
      case 'OPEN':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'UNDER_INVESTIGATION':
      case 'IN_PROGRESS':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'PENDING_REVIEW':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'RESOLVED':
      case 'CLOSED':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'REJECTED':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-semibold ${getStatusStyles()}`}>
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
      <div className="w-10 h-10 bg-white/10 rounded-full flex items-center justify-center text-lg">
        {event.icon}
      </div>
      {!isLast && <div className="w-0.5 h-full bg-white/10 mt-2" />}
    </div>
    <div className="pb-6">
      <p className="text-white font-medium">{event.event}</p>
      <p className="text-sm text-gray-400">
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
    <div className="flex items-center justify-between mb-8">
      {stages.map((stage, index) => (
        <div key={stage.key} className="flex items-center">
          <div className={`flex flex-col items-center ${
            index <= currentIndex ? 'text-white' : 'text-gray-500'
          }`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center text-xl mb-2 ${
              index < currentIndex 
                ? 'bg-green-500' 
                : index === currentIndex 
                  ? 'bg-gradient-to-br from-purple-500 to-cyan-500 animate-pulse'
                  : 'bg-white/10'
            }`}>
              {index < currentIndex ? '✓' : stage.icon}
            </div>
            <span className="text-xs font-medium hidden sm:block">{stage.label}</span>
          </div>
          {index < stages.length - 1 && (
            <div className={`w-8 sm:w-16 h-1 mx-2 rounded ${
              index < currentIndex ? 'bg-green-500' : 'bg-white/10'
            }`} />
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
    } catch (err) {
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
    <div className="min-h-screen relative">
      <AnimatedBackground />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-black/20 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <button
              onClick={() => navigate('/portal')}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back to Portal</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-3xl mx-auto">
        {/* Search Section */}
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-2xl items-center justify-center mb-4">
            <Search className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Track Your Report</h1>
          <p className="text-gray-400">Enter your reference number to check the status</p>
        </div>

        {/* Search Form */}
        <form onSubmit={handleSearch} className="mb-8">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <input
                type="text"
                placeholder="Enter reference number (e.g., INC-2026-0001)"
                value={searchRef}
                onChange={(e) => setSearchRef(e.target.value.toUpperCase())}
                className="w-full px-5 py-4 bg-white/5 border border-white/10 rounded-2xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={isSearching || !searchRef.trim()}
              className="px-6 py-4 bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-semibold rounded-2xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSearching ? (
                <Loader2 className="w-6 h-6 animate-spin" />
              ) : (
                <Search className="w-6 h-6" />
              )}
            </button>
          </div>
        </form>

        {/* Error State */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6 text-center">
            <XCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
            <h3 className="text-xl font-bold text-white mb-2">Not Found</h3>
            <p className="text-gray-400">{error}</p>
          </div>
        )}

        {/* Report Details */}
        {report && (
          <div className="space-y-6">
            {/* Header Card */}
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-3xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    {report.report_type === 'Incident' ? (
                      <AlertTriangle className="w-5 h-5 text-red-400" />
                    ) : (
                      <MessageSquare className="w-5 h-5 text-amber-400" />
                    )}
                    <span className="text-sm text-gray-400">{report.report_type}</span>
                  </div>
                  <h2 className="text-xl font-bold text-white">{report.title}</h2>
                  <p className="text-sm font-mono text-gray-400 mt-1">{report.reference_number}</p>
                </div>
                <StatusBadge status={report.status} label={report.status_label} />
              </div>

              {/* Progress Indicator */}
              <ProgressIndicator status={report.status} />

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-white/5 rounded-xl">
                  <Calendar className="w-5 h-5 text-purple-400 mx-auto mb-1" />
                  <p className="text-xs text-gray-400">Submitted</p>
                  <p className="text-sm text-white font-medium">
                    {new Date(report.submitted_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <div className="text-center p-4 bg-white/5 rounded-xl">
                  <Clock className="w-5 h-5 text-cyan-400 mx-auto mb-1" />
                  <p className="text-xs text-gray-400">Last Update</p>
                  <p className="text-sm text-white font-medium">
                    {new Date(report.updated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <div className="text-center p-4 bg-white/5 rounded-xl">
                  <User className="w-5 h-5 text-green-400 mx-auto mb-1" />
                  <p className="text-xs text-gray-400">Assigned To</p>
                  <p className="text-sm text-white font-medium">{report.assigned_to || 'Pending'}</p>
                </div>
              </div>
            </div>

            {/* Next Steps */}
            {report.next_steps && (
              <div className="bg-gradient-to-r from-purple-500/20 to-cyan-500/20 border border-purple-500/30 rounded-2xl p-6">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-purple-500/20 rounded-lg">
                    <Sparkles className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white mb-1">What's Next?</h3>
                    <p className="text-gray-300 text-sm">{report.next_steps}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Timeline */}
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5 text-cyan-400" />
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
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => searchReport(report.reference_number)}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-white/10 text-white font-semibold rounded-xl hover:bg-white/20 transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
                Refresh Status
              </button>
              <button
                onClick={copyLink}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-white/10 text-white font-semibold rounded-xl hover:bg-white/20 transition-colors"
              >
                <Share2 className="w-5 h-5" />
                Share Link
              </button>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!report && !error && !isSearching && !urlRef && (
          <div className="text-center py-12">
            <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
              <HelpCircle className="w-10 h-10 text-gray-500" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Enter Your Reference Number</h3>
            <p className="text-gray-400 mb-6">
              You received a reference number when you submitted your report.
              <br />
              Enter it above to check the status.
            </p>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 max-w-sm mx-auto">
              <p className="text-xs text-gray-400 mb-2">Example formats:</p>
              <div className="flex flex-wrap gap-2 justify-center">
                <span className="px-3 py-1 bg-white/10 rounded-lg text-sm font-mono text-white">INC-2026-0001</span>
                <span className="px-3 py-1 bg-white/10 rounded-lg text-sm font-mono text-white">COMP-2026-0001</span>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
