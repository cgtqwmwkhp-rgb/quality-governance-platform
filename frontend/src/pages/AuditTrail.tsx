import { useState, useEffect, useCallback } from 'react';
import { auditTrailApi } from '../api/client';
import type { AuditLogEntry } from '../api/client';
import {
  History,
  Search,
  Download,
  ChevronDown,
  FileText,
  Edit,
  Trash2,
  Plus,
  Eye,
  LogIn,
  LogOut,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  RefreshCw
} from 'lucide-react';

interface AuditEntry {
  id: string;
  timestamp: string;
  user: {
    name: string;
    email: string;
    avatar?: string;
  };
  action: 'create' | 'update' | 'delete' | 'view' | 'login' | 'logout' | 'approve' | 'reject' | 'export';
  module: string;
  resource: string;
  resourceId: string;
  details: string;
  ipAddress: string;
  changes?: {
    field: string;
    oldValue: string;
    newValue: string;
  }[];
}

export default function AuditTrail() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAction, setSelectedAction] = useState<string>('all');
  const [selectedModule, setSelectedModule] = useState<string>('all');
  const [dateRange, setDateRange] = useState<string>('today');
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [page, setPage] = useState(1);

  const mapApiEntry = (e: AuditLogEntry): AuditEntry => ({
    id: String(e.id),
    timestamp: e.timestamp,
    user: { name: e.user_name || 'System', email: e.user_email || '' },
    action: (e.action || 'view') as AuditEntry['action'],
    module: (e.entity_type || 'system').charAt(0).toUpperCase() + (e.entity_type || 'system').slice(1),
    resource: e.entity_type || '',
    resourceId: e.entity_id || '',
    details: e.entity_name || `${e.action} on ${e.entity_type} ${e.entity_id}`,
    ipAddress: e.ip_address || '',
    changes: e.changed_fields?.map(f => ({
      field: String(f),
      oldValue: e.old_values?.[String(f)] != null ? String(e.old_values[String(f)]) : '',
      newValue: e.new_values?.[String(f)] != null ? String(e.new_values[String(f)]) : '',
    })),
  });

  const loadEntries = useCallback(async () => {
    setIsLoading(true);
    try {
      const actionParam = selectedAction !== 'all' ? selectedAction : undefined;
      const entityParam = selectedModule !== 'all' ? selectedModule.toLowerCase() : undefined;
      const res = await auditTrailApi.list({ action: actionParam, entity_type: entityParam, page, per_page: 50 });
      const raw = res.data;
      const items = Array.isArray(raw) ? raw : raw?.items || [];
      const entries = items.map(mapApiEntry);
      if (page === 1) {
        setAuditEntries(entries);
      } else {
        setAuditEntries(prev => [...prev, ...entries]);
      }
    } catch {
      console.error('Failed to load audit trail');
    } finally {
      setIsLoading(false);
    }
  }, [selectedAction, selectedModule, page]);

  useEffect(() => { setPage(1); }, [selectedAction, selectedModule, dateRange]);
  useEffect(() => { loadEntries(); }, [loadEntries]);

  const actionIcons: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
    create: { icon: <Plus className="w-4 h-4" />, color: 'text-success', bg: 'bg-success/20' },
    update: { icon: <Edit className="w-4 h-4" />, color: 'text-info', bg: 'bg-info/20' },
    delete: { icon: <Trash2 className="w-4 h-4" />, color: 'text-destructive', bg: 'bg-destructive/20' },
    view: { icon: <Eye className="w-4 h-4" />, color: 'text-muted-foreground', bg: 'bg-muted' },
    login: { icon: <LogIn className="w-4 h-4" />, color: 'text-info', bg: 'bg-info/20' },
    logout: { icon: <LogOut className="w-4 h-4" />, color: 'text-muted-foreground', bg: 'bg-muted' },
    approve: { icon: <CheckCircle2 className="w-4 h-4" />, color: 'text-success', bg: 'bg-success/20' },
    reject: { icon: <AlertTriangle className="w-4 h-4" />, color: 'text-warning', bg: 'bg-warning/20' },
    export: { icon: <Download className="w-4 h-4" />, color: 'text-purple-400', bg: 'bg-purple-500/20' }
  };

  const modules = ['Incidents', 'RTAs', 'Complaints', 'Risks', 'Audits', 'Actions', 'Documents', 'Reports', 'System'];
  const actions = ['create', 'update', 'delete', 'view', 'login', 'logout', 'approve', 'reject', 'export'];

  const filteredEntries = auditEntries.filter(entry => {
    if (!searchQuery) return true;
    return entry.details.toLowerCase().includes(searchQuery.toLowerCase()) ||
           entry.user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
           entry.resourceId.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const handleRefresh = () => {
    setPage(1);
    loadEntries();
  };

  const handleExport = async () => {
    try {
      await auditTrailApi.exportLog({ format: 'json', reason: 'Manual export' });
    } catch {
      console.error('Failed to export');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl">
              <History className="w-8 h-8 text-primary" />
            </div>
            Audit Trail
          </h1>
          <p className="text-muted-foreground mt-1">Complete history of system activities</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className={`p-2 bg-secondary rounded-lg text-muted-foreground hover:text-foreground transition-all ${
              isLoading ? 'animate-spin' : ''
            }`}
          >
            <RefreshCw className="w-5 h-5" />
          </button>
          
          <button onClick={handleExport} className="px-4 py-2 bg-secondary border border-border text-foreground font-medium rounded-xl hover:bg-surface transition-all flex items-center gap-2">
            <Download className="w-5 h-5" />
            Export Log
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-card/50 backdrop-blur-sm rounded-xl border border-border p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by user, action, or resource..."
              className="w-full pl-10 pr-4 py-2.5 bg-background border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          
          {/* Action Filter */}
          <div className="relative">
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="appearance-none pl-4 pr-10 py-2.5 bg-background border border-border rounded-xl text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 min-w-[150px]"
            >
              <option value="all">All Actions</option>
              {actions.map((action) => (
                <option key={action} value={action}>{action.charAt(0).toUpperCase() + action.slice(1)}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground pointer-events-none" />
          </div>
          
          {/* Module Filter */}
          <div className="relative">
            <select
              value={selectedModule}
              onChange={(e) => setSelectedModule(e.target.value)}
              className="appearance-none pl-4 pr-10 py-2.5 bg-background border border-border rounded-xl text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 min-w-[150px]"
            >
              <option value="all">All Modules</option>
              {modules.map((module) => (
                <option key={module} value={module}>{module}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground pointer-events-none" />
          </div>
          
          {/* Date Range */}
          <div className="relative">
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="appearance-none pl-4 pr-10 py-2.5 bg-background border border-border rounded-xl text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 min-w-[150px]"
            >
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
              <option value="all">All Time</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-4">
        {filteredEntries.map((entry, index) => (
          <div
            key={entry.id}
            className="relative pl-8"
          >
            {/* Timeline Line */}
            {index < filteredEntries.length - 1 && (
              <div className="absolute left-3 top-10 bottom-0 w-0.5 bg-border" />
            )}
            
            {/* Timeline Dot */}
            <div className={`absolute left-0 top-3 w-6 h-6 rounded-full flex items-center justify-center ${actionIcons[entry.action].bg}`}>
              <div className={actionIcons[entry.action].color}>
                {actionIcons[entry.action].icon}
              </div>
            </div>
            
            {/* Entry Card */}
            <div
              className={`bg-card/50 backdrop-blur-sm rounded-xl border transition-all cursor-pointer ${
                expandedEntry === entry.id
                  ? 'border-primary/50'
                  : 'border-border hover:border-border-strong'
              }`}
              onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
            >
              <div className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary-hover flex items-center justify-center text-primary-foreground text-sm font-semibold">
                        {entry.user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <span className="font-medium text-foreground">{entry.user.name}</span>
                        <span className="text-muted-foreground mx-2">•</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${actionIcons[entry.action].bg} ${actionIcons[entry.action].color}`}>
                          {entry.action}
                        </span>
                      </div>
                    </div>
                    
                    <p className="text-muted-foreground">{entry.details}</p>
                    
                    <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        {entry.timestamp}
                      </span>
                      <span className="flex items-center gap-1">
                        <FileText className="w-4 h-4" />
                        {entry.resourceId}
                      </span>
                      <span className="px-2 py-0.5 bg-slate-700/50 rounded text-slate-400">
                        {entry.module}
                      </span>
                    </div>
                  </div>
                  
                  <ChevronDown className={`w-5 h-5 text-slate-400 transition-transform ${
                    expandedEntry === entry.id ? 'rotate-180' : ''
                  }`} />
                </div>
                
                {/* Expanded Details */}
                {expandedEntry === entry.id && (
                  <div className="mt-4 pt-4 border-t border-slate-700/50 space-y-4 animate-in slide-in-from-top duration-200">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-slate-500">User Email</span>
                        <p className="text-slate-300">{entry.user.email}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">IP Address</span>
                        <p className="text-slate-300">{entry.ipAddress}</p>
                      </div>
                    </div>
                    
                    {entry.changes && entry.changes.length > 0 && (
                      <div>
                        <span className="text-sm text-slate-500 block mb-2">Changes Made</span>
                        <div className="space-y-2">
                          {entry.changes.map((change, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-3 p-2 bg-slate-900/50 rounded-lg text-sm"
                            >
                              <span className="text-slate-400 font-medium min-w-[100px]">
                                {change.field}:
                              </span>
                              <span className="text-red-400 line-through">
                                {change.oldValue || '(empty)'}
                              </span>
                              <ArrowRight className="w-4 h-4 text-slate-600" />
                              <span className="text-emerald-400">
                                {change.newValue}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {filteredEntries.length === 0 && (
        <div className="text-center py-12">
          <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
            <History className="w-10 h-10 text-slate-600" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">No audit entries found</h3>
          <p className="text-slate-400">Try adjusting your filters</p>
        </div>
      )}

      {/* Load More */}
      {filteredEntries.length > 0 && (
        <div className="text-center">
          <button onClick={() => setPage(p => p + 1)} className="px-6 py-2 bg-slate-800/50 border border-slate-700 text-slate-300 font-medium rounded-xl hover:bg-slate-700/50 transition-all">
            Load More
          </button>
        </div>
      )}
    </div>
  );
}
