/**
 * Audit Trail Viewer
 *
 * Wired to backend audit trail API:
 * - GET /api/v1/audit-trail (list with filters)
 * - POST /api/v1/audit-trail/verify (chain verification)
 * - POST /api/v1/audit-trail/export (export logs)
 * - GET /api/v1/audit-trail/stats (statistics)
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  Search,
  Download,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  User,
  Activity,
  Eye,
  Edit,
  Trash2,
  Plus,
  Lock,
  Unlock,
  Filter,
  RefreshCw,
  Hash,
  Link2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { auditTrailApi, AuditLogEntry, AuditVerification } from '../api/client';

const actionIcons: Record<string, React.ElementType> = {
  create: Plus,
  update: Edit,
  delete: Trash2,
  view: Eye,
  login: Lock,
  logout: Unlock,
  approve: CheckCircle,
  reject: XCircle,
};

const actionColors: Record<string, string> = {
  create: 'text-emerald-400 bg-emerald-400/10',
  update: 'text-blue-400 bg-blue-400/10',
  delete: 'text-red-400 bg-red-400/10',
  view: 'text-muted-foreground bg-muted/50',
  login: 'text-purple-400 bg-purple-400/10',
  logout: 'text-amber-400 bg-amber-400/10',
  approve: 'text-emerald-400 bg-emerald-400/10',
  reject: 'text-red-400 bg-red-400/10',
};

export default function AuditTrailViewer() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [verification, setVerification] = useState<AuditVerification | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [expandedEntries, setExpandedEntries] = useState<Set<number>>(new Set());
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);

  const [filters, setFilters] = useState({
    entity_type: '',
    action: '',
    user: '',
    date_from: '',
    date_to: '',
  });

  const loadAuditLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filters.entity_type) params.entity_type = filters.entity_type;
      if (filters.action) params.action = filters.action;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;

      const res = await auditTrailApi.list(params);
      setEntries(res.data || []);
    } catch (err) {
      console.error('Failed to load audit logs', err);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const loadStats = useCallback(async () => {
    try {
      const res = await auditTrailApi.getStats(30);
      setStats(res.data);
    } catch {
      // stats are supplementary
    }
  }, []);

  useEffect(() => {
    loadAuditLogs();
    loadStats();
  }, [loadAuditLogs, loadStats]);

  const verifyChain = async () => {
    setVerifying(true);
    try {
      const res = await auditTrailApi.verify();
      setVerification(res.data);
    } catch (err) {
      console.error('Verification failed', err);
    } finally {
      setVerifying(false);
    }
  };

  const exportLogs = async (format: 'json' | 'csv') => {
    setExportingFormat(format);
    try {
      const res = await auditTrailApi.exportLog({
        format,
        entity_type: filters.entity_type || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
        reason: 'Manual export from Audit Trail Viewer',
      });
      const data = res.data;
      if (format === 'json' && data.data) {
        const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit-trail-export-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Export failed', err);
    } finally {
      setExportingFormat(null);
    }
  };

  const toggleExpanded = (id: number) => {
    const newExpanded = new Set(expandedEntries);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedEntries(newExpanded);
  };

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString();
  };

  const truncateHash = (hash: string) => {
    if (!hash || hash.length < 16) return hash || '';
    return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
  };

  const totalEntries = (stats as any)?.total_entries ?? entries.length;
  const createdCount = (stats as any)?.by_action?.create ?? entries.filter(e => e.action === 'create').length;
  const updatedCount = (stats as any)?.by_action?.update ?? entries.filter(e => e.action === 'update').length;
  const activeUsers = (stats as any)?.unique_users ?? new Set(entries.map(e => e.user_email)).size;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Audit Trail</h1>
            <p className="text-muted-foreground">Immutable blockchain-style change history</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={verifyChain}
            disabled={verifying}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-success/20 text-success hover:bg-success/30 transition-colors disabled:opacity-50"
          >
            {verifying ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Shield className="h-4 w-4" />
            )}
            Verify Chain
          </button>

          <div className="relative group">
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-info/20 text-info hover:bg-info/30 transition-colors">
              {exportingFormat ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Export
            </button>
            <div className="absolute right-0 mt-2 w-48 rounded-lg bg-card border border-border shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
              <button
                onClick={() => exportLogs('json')}
                className="w-full px-4 py-2 text-left text-sm text-muted-foreground hover:bg-muted first:rounded-t-lg"
              >
                Export as JSON
              </button>
              <button
                onClick={() => exportLogs('csv')}
                className="w-full px-4 py-2 text-left text-sm text-muted-foreground hover:bg-muted last:rounded-b-lg"
              >
                Export as CSV
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Verification Status */}
      {verification && (
        <div className={`p-4 rounded-xl border ${
          verification.is_valid
            ? 'bg-success/10 border-success/30'
            : 'bg-destructive/10 border-destructive/30'
        }`}>
          <div className="flex items-center gap-3">
            {verification.is_valid ? (
              <CheckCircle className="h-6 w-6 text-success" />
            ) : (
              <XCircle className="h-6 w-6 text-destructive" />
            )}
            <div>
              <p className={`font-medium ${verification.is_valid ? 'text-success' : 'text-destructive'}`}>
                {verification.is_valid ? 'Chain Verified Successfully' : 'Chain Verification Failed'}
              </p>
              <p className="text-sm text-muted-foreground">
                {verification.entries_verified} entries verified &bull; Last check: {formatTimestamp(verification.verified_at)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="p-4 rounded-xl bg-card/50 border border-border">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">Filters:</span>
          </div>

          <select
            value={filters.entity_type}
            onChange={e => setFilters({ ...filters, entity_type: e.target.value })}
            className="px-3 py-1.5 rounded-lg bg-background border border-border text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="">All Entity Types</option>
            <option value="incident">Incidents</option>
            <option value="audit">Audits</option>
            <option value="risk">Risks</option>
            <option value="document">Documents</option>
            <option value="auth">Authentication</option>
          </select>

          <select
            value={filters.action}
            onChange={e => setFilters({ ...filters, action: e.target.value })}
            className="px-3 py-1.5 rounded-lg bg-background border border-border text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="">All Actions</option>
            <option value="create">Create</option>
            <option value="update">Update</option>
            <option value="delete">Delete</option>
            <option value="view">View</option>
            <option value="login">Login</option>
            <option value="approve">Approve</option>
          </select>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search user..."
              value={filters.user}
              onChange={e => setFilters({ ...filters, user: e.target.value })}
              className="pl-10 pr-4 py-1.5 rounded-lg bg-background border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <button
            onClick={loadAuditLogs}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Audit Log Entries */}
      <div className="space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="h-8 w-8 text-primary animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            No audit entries found
          </div>
        ) : (
          entries.map((entry, index) => {
            const ActionIcon = actionIcons[entry.action] || Activity;
            const isExpanded = expandedEntries.has(entry.id);

            return (
              <div
                key={entry.id}
                className="rounded-xl bg-card/50 border border-border overflow-hidden"
              >
                <div
                  className="p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                  onClick={() => toggleExpanded(entry.id)}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex flex-col items-center gap-1">
                      <div className={`p-2 rounded-lg ${actionColors[entry.action] || 'text-muted-foreground bg-muted/50'}`}>
                        <ActionIcon className="h-5 w-5" />
                      </div>
                      {index < entries.length - 1 && (
                        <div className="w-0.5 h-8 bg-gradient-to-b from-purple-500 to-transparent" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-foreground capitalize">{entry.action}</span>
                        <span className="text-muted-foreground">&bull;</span>
                        <span className="text-muted-foreground">{entry.entity_type}</span>
                        {entry.entity_name && (
                          <>
                            <span className="text-muted-foreground">&bull;</span>
                            <span className="text-muted-foreground truncate">{entry.entity_name}</span>
                          </>
                        )}
                      </div>

                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <User className="h-3.5 w-3.5" />
                          {entry.user_name || entry.user_email || 'System'}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" />
                          {formatTimestamp(entry.timestamp)}
                        </span>
                        <span className="flex items-center gap-1 font-mono text-xs">
                          <Hash className="h-3.5 w-3.5" />
                          {truncateHash(entry.entry_hash)}
                        </span>
                      </div>
                    </div>

                    <div>
                      {isExpanded ? (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-0 border-t border-border">
                    <div className="grid grid-cols-2 gap-4 mt-4">
                      <div className="p-3 rounded-lg bg-muted/30">
                        <h4 className="text-xs font-medium text-muted-foreground uppercase mb-2">Hash Chain</h4>
                        <div className="space-y-2">
                          <div>
                            <span className="text-xs text-muted-foreground">Current Hash:</span>
                            <p className="font-mono text-xs text-primary break-all">{entry.entry_hash}</p>
                          </div>
                          <div className="flex items-center gap-1 text-muted-foreground">
                            <Link2 className="h-3 w-3" />
                            <span className="text-xs">Links to previous:</span>
                          </div>
                        </div>
                      </div>

                      <div className="p-3 rounded-lg bg-muted/30">
                        <h4 className="text-xs font-medium text-muted-foreground uppercase mb-2">Change Details</h4>
                        {entry.changed_fields && entry.changed_fields.length > 0 ? (
                          <div className="space-y-2">
                            <p className="text-xs text-muted-foreground">
                              Changed fields: {entry.changed_fields.join(', ')}
                            </p>
                            {entry.old_values && (
                              <div>
                                <span className="text-xs text-destructive">Before:</span>
                                <pre className="text-xs text-muted-foreground mt-1 overflow-auto">
                                  {JSON.stringify(entry.old_values, null, 2)}
                                </pre>
                              </div>
                            )}
                            {entry.new_values && (
                              <div>
                                <span className="text-xs text-success">After:</span>
                                <pre className="text-xs text-muted-foreground mt-1 overflow-auto">
                                  {JSON.stringify(entry.new_values, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        ) : entry.new_values ? (
                          <div>
                            <span className="text-xs text-success">Created with:</span>
                            <pre className="text-xs text-muted-foreground mt-1 overflow-auto">
                              {JSON.stringify(entry.new_values, null, 2)}
                            </pre>
                          </div>
                        ) : (
                          <p className="text-xs text-muted-foreground">No change data recorded</p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-6 mt-4 text-xs text-muted-foreground">
                      <span>Sequence: #{entry.sequence}</span>
                      <span>IP: {entry.ip_address || 'N/A'}</span>
                      <span>Category: {entry.action_category}</span>
                      {entry.is_sensitive && (
                        <span className="flex items-center gap-1 text-warning">
                          <AlertTriangle className="h-3 w-3" />
                          Sensitive
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-card/50 border border-border">
          <p className="text-2xl font-bold text-foreground">{totalEntries}</p>
          <p className="text-sm text-muted-foreground">Total Entries</p>
        </div>
        <div className="p-4 rounded-xl bg-card/50 border border-border">
          <p className="text-2xl font-bold text-success">{createdCount}</p>
          <p className="text-sm text-muted-foreground">Created</p>
        </div>
        <div className="p-4 rounded-xl bg-card/50 border border-border">
          <p className="text-2xl font-bold text-info">{updatedCount}</p>
          <p className="text-sm text-muted-foreground">Updated</p>
        </div>
        <div className="p-4 rounded-xl bg-card/50 border border-border">
          <p className="text-2xl font-bold text-purple-400">{activeUsers}</p>
          <p className="text-sm text-muted-foreground">Active Users</p>
        </div>
      </div>
    </div>
  );
}
