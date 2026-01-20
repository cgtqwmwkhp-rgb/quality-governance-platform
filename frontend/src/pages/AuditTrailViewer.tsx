/**
 * Audit Trail Viewer
 * 
 * Enterprise-grade immutable audit log viewer with:
 * - Hash chain verification
 * - Filterable history
 * - Export for compliance
 * - Tamper detection
 */

import { useState, useEffect } from 'react';
import {
  Shield,
  Search,
  Download,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  User,
  FileText,
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

// Types
interface AuditEntry {
  id: number;
  sequence: number;
  entry_hash: string;
  previous_hash: string;
  entity_type: string;
  entity_id: string;
  entity_name?: string;
  action: string;
  action_category: string;
  user_email?: string;
  user_name?: string;
  changed_fields?: string[];
  old_values?: Record<string, any>;
  new_values?: Record<string, any>;
  ip_address?: string;
  timestamp: string;
  is_sensitive: boolean;
}

interface Verification {
  id: number;
  is_valid: boolean;
  entries_verified: number;
  invalid_entries?: any[];
  verified_at: string;
}

// Action icons
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

// Action colors
const actionColors: Record<string, string> = {
  create: 'text-emerald-400 bg-emerald-400/10',
  update: 'text-blue-400 bg-blue-400/10',
  delete: 'text-red-400 bg-red-400/10',
  view: 'text-slate-400 bg-slate-400/10',
  login: 'text-purple-400 bg-purple-400/10',
  logout: 'text-amber-400 bg-amber-400/10',
  approve: 'text-emerald-400 bg-emerald-400/10',
  reject: 'text-red-400 bg-red-400/10',
};

export default function AuditTrailViewer() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);
  const [expandedEntries, setExpandedEntries] = useState<Set<number>>(new Set());
  
  // Filters
  const [filters, setFilters] = useState({
    entity_type: '',
    action: '',
    user: '',
    date_from: '',
    date_to: '',
  });

  useEffect(() => {
    loadAuditLogs();
  }, [filters]);

  const loadAuditLogs = async () => {
    setLoading(true);
    try {
      // Mock data - would be API call
      const mockEntries: AuditEntry[] = [
        {
          id: 1,
          sequence: 1001,
          entry_hash: 'a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd',
          previous_hash: '0000000000000000000000000000000000000000000000000000000000000000',
          entity_type: 'incident',
          entity_id: 'INC-2026-0042',
          entity_name: 'Slip hazard in warehouse',
          action: 'create',
          action_category: 'data',
          user_email: 'sarah.johnson@plantexpand.com',
          user_name: 'Sarah Johnson',
          ip_address: '192.168.1.100',
          timestamp: new Date().toISOString(),
          is_sensitive: false,
          new_values: { title: 'Slip hazard in warehouse', severity: 'high' },
        },
        {
          id: 2,
          sequence: 1002,
          entry_hash: 'b2c3d4e5f678901234567890123456789012345678901234567890123456bcde',
          previous_hash: 'a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd',
          entity_type: 'incident',
          entity_id: 'INC-2026-0042',
          entity_name: 'Slip hazard in warehouse',
          action: 'update',
          action_category: 'data',
          user_email: 'mike.chen@plantexpand.com',
          user_name: 'Mike Chen',
          changed_fields: ['status', 'assigned_to'],
          old_values: { status: 'open', assigned_to: null },
          new_values: { status: 'in_progress', assigned_to: 'Mike Chen' },
          ip_address: '192.168.1.105',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          is_sensitive: false,
        },
        {
          id: 3,
          sequence: 1003,
          entry_hash: 'c3d4e5f67890123456789012345678901234567890123456789012345678cdef',
          previous_hash: 'b2c3d4e5f678901234567890123456789012345678901234567890123456bcde',
          entity_type: 'auth',
          entity_id: 'user:15',
          action: 'login',
          action_category: 'auth',
          user_email: 'admin@plantexpand.com',
          user_name: 'Admin User',
          ip_address: '10.0.0.50',
          timestamp: new Date(Date.now() - 7200000).toISOString(),
          is_sensitive: false,
        },
      ];
      
      setEntries(mockEntries);
    } catch (error) {
      console.error('Failed to load audit logs', error);
    } finally {
      setLoading(false);
    }
  };

  const verifyChain = async () => {
    setVerifying(true);
    try {
      // Mock verification - would be API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      setVerification({
        id: 1,
        is_valid: true,
        entries_verified: entries.length,
        verified_at: new Date().toISOString(),
      });
    } catch (error) {
      console.error('Verification failed', error);
    } finally {
      setVerifying(false);
    }
  };

  const exportLogs = async (format: 'json' | 'csv') => {
    // Would trigger API export
    console.log('Exporting as', format);
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
    const date = new Date(ts);
    return date.toLocaleString();
  };

  const truncateHash = (hash: string) => {
    return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600">
              <Shield className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Audit Trail</h1>
              <p className="text-slate-400">Immutable blockchain-style change history</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={verifyChain}
              disabled={verifying}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
            >
              {verifying ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Shield className="h-4 w-4" />
              )}
              Verify Chain
            </button>
            
            <div className="relative group">
              <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors">
                <Download className="h-4 w-4" />
                Export
              </button>
              <div className="absolute right-0 mt-2 w-48 rounded-lg bg-slate-800 border border-slate-700 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                <button
                  onClick={() => exportLogs('json')}
                  className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-700 first:rounded-t-lg"
                >
                  Export as JSON
                </button>
                <button
                  onClick={() => exportLogs('csv')}
                  className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-700 last:rounded-b-lg"
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
              ? 'bg-emerald-500/10 border-emerald-500/30'
              : 'bg-red-500/10 border-red-500/30'
          }`}>
            <div className="flex items-center gap-3">
              {verification.is_valid ? (
                <CheckCircle className="h-6 w-6 text-emerald-400" />
              ) : (
                <XCircle className="h-6 w-6 text-red-400" />
              )}
              <div>
                <p className={`font-medium ${verification.is_valid ? 'text-emerald-400' : 'text-red-400'}`}>
                  {verification.is_valid ? 'Chain Verified Successfully' : 'Chain Verification Failed'}
                </p>
                <p className="text-sm text-slate-400">
                  {verification.entries_verified} entries verified • Last check: {formatTimestamp(verification.verified_at)}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-400">Filters:</span>
            </div>
            
            <select
              value={filters.entity_type}
              onChange={e => setFilters({ ...filters, entity_type: e.target.value })}
              className="px-3 py-1.5 rounded-lg bg-slate-700 border border-slate-600 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="px-3 py-1.5 rounded-lg bg-slate-700 border border-slate-600 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search user..."
                value={filters.user}
                onChange={e => setFilters({ ...filters, user: e.target.value })}
                className="pl-10 pr-4 py-1.5 rounded-lg bg-slate-700 border border-slate-600 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Audit Log Entries */}
        <div className="space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 text-blue-400 animate-spin" />
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              No audit entries found
            </div>
          ) : (
            entries.map((entry, index) => {
              const ActionIcon = actionIcons[entry.action] || Activity;
              const isExpanded = expandedEntries.has(entry.id);
              
              return (
                <div
                  key={entry.id}
                  className="rounded-xl bg-slate-800/50 border border-slate-700/50 overflow-hidden"
                >
                  {/* Entry Header */}
                  <div
                    className="p-4 cursor-pointer hover:bg-slate-700/30 transition-colors"
                    onClick={() => toggleExpanded(entry.id)}
                  >
                    <div className="flex items-center gap-4">
                      {/* Hash Chain Visualization */}
                      <div className="flex flex-col items-center gap-1">
                        <div className={`p-2 rounded-lg ${actionColors[entry.action] || 'text-slate-400 bg-slate-400/10'}`}>
                          <ActionIcon className="h-5 w-5" />
                        </div>
                        {index < entries.length - 1 && (
                          <div className="w-0.5 h-8 bg-gradient-to-b from-purple-500 to-transparent" />
                        )}
                      </div>
                      
                      {/* Entry Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white capitalize">{entry.action}</span>
                          <span className="text-slate-400">•</span>
                          <span className="text-slate-300">{entry.entity_type}</span>
                          {entry.entity_name && (
                            <>
                              <span className="text-slate-400">•</span>
                              <span className="text-slate-300 truncate">{entry.entity_name}</span>
                            </>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-4 text-sm text-slate-400">
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
                      
                      {/* Expand/Collapse */}
                      <div>
                        {isExpanded ? (
                          <ChevronDown className="h-5 w-5 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-5 w-5 text-slate-400" />
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-0 border-t border-slate-700/50">
                      <div className="grid grid-cols-2 gap-4 mt-4">
                        {/* Hash Details */}
                        <div className="p-3 rounded-lg bg-slate-900/50">
                          <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Hash Chain</h4>
                          <div className="space-y-2">
                            <div>
                              <span className="text-xs text-slate-500">Current Hash:</span>
                              <p className="font-mono text-xs text-blue-400 break-all">{entry.entry_hash}</p>
                            </div>
                            <div className="flex items-center gap-1 text-slate-500">
                              <Link2 className="h-3 w-3" />
                              <span className="text-xs">Links to:</span>
                            </div>
                            <div>
                              <span className="text-xs text-slate-500">Previous Hash:</span>
                              <p className="font-mono text-xs text-purple-400 break-all">{entry.previous_hash}</p>
                            </div>
                          </div>
                        </div>
                        
                        {/* Change Details */}
                        <div className="p-3 rounded-lg bg-slate-900/50">
                          <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Change Details</h4>
                          {entry.changed_fields && entry.changed_fields.length > 0 ? (
                            <div className="space-y-2">
                              <p className="text-xs text-slate-400">
                                Changed fields: {entry.changed_fields.join(', ')}
                              </p>
                              {entry.old_values && (
                                <div>
                                  <span className="text-xs text-red-400">Before:</span>
                                  <pre className="text-xs text-slate-300 mt-1 overflow-auto">
                                    {JSON.stringify(entry.old_values, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {entry.new_values && (
                                <div>
                                  <span className="text-xs text-emerald-400">After:</span>
                                  <pre className="text-xs text-slate-300 mt-1 overflow-auto">
                                    {JSON.stringify(entry.new_values, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          ) : entry.new_values ? (
                            <div>
                              <span className="text-xs text-emerald-400">Created with:</span>
                              <pre className="text-xs text-slate-300 mt-1 overflow-auto">
                                {JSON.stringify(entry.new_values, null, 2)}
                              </pre>
                            </div>
                          ) : (
                            <p className="text-xs text-slate-500">No change data recorded</p>
                          )}
                        </div>
                      </div>
                      
                      {/* Metadata */}
                      <div className="flex items-center gap-6 mt-4 text-xs text-slate-500">
                        <span>Sequence: #{entry.sequence}</span>
                        <span>IP: {entry.ip_address || 'N/A'}</span>
                        <span>Category: {entry.action_category}</span>
                        {entry.is_sensitive && (
                          <span className="flex items-center gap-1 text-amber-400">
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
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <p className="text-2xl font-bold text-white">{entries.length}</p>
            <p className="text-sm text-slate-400">Total Entries</p>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <p className="text-2xl font-bold text-emerald-400">
              {entries.filter(e => e.action === 'create').length}
            </p>
            <p className="text-sm text-slate-400">Created</p>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <p className="text-2xl font-bold text-blue-400">
              {entries.filter(e => e.action === 'update').length}
            </p>
            <p className="text-sm text-slate-400">Updated</p>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <p className="text-2xl font-bold text-purple-400">
              {new Set(entries.map(e => e.user_email)).size}
            </p>
            <p className="text-sm text-slate-400">Active Users</p>
          </div>
        </div>
      </div>
    </div>
  );
}
