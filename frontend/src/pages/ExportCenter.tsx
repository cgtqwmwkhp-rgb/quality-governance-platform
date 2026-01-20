import { useState } from 'react';
import {
  Download,
  FileText,
  FileSpreadsheet,
  FileJson,
  File,
  Calendar,
  Filter,
  Clock,
  CheckCircle2,
  RefreshCw,
  Trash2,
  Play,
  Settings,
  History,
  Zap
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';

interface ExportJob {
  id: string;
  name: string;
  format: 'pdf' | 'excel' | 'csv' | 'json';
  modules: string[];
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  createdAt: string;
  completedAt?: string;
  fileSize?: string;
  downloadUrl?: string;
}

interface ExportTemplate {
  id: string;
  name: string;
  description: string;
  modules: string[];
  format: 'pdf' | 'excel' | 'csv' | 'json';
  schedule?: string;
  lastRun?: string;
}

export default function ExportCenter() {
  const [activeTab, setActiveTab] = useState<'new' | 'history' | 'templates'>('new');
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [selectedFormat, setSelectedFormat] = useState<'pdf' | 'excel' | 'csv' | 'json'>('excel');
  const [dateRange, setDateRange] = useState<string>('all');
  const [isExporting, setIsExporting] = useState(false);

  const modules = [
    { id: 'incidents', name: 'Incidents', count: 847 },
    { id: 'rtas', name: 'RTAs', count: 234 },
    { id: 'complaints', name: 'Complaints', count: 456 },
    { id: 'risks', name: 'Risks', count: 189 },
    { id: 'audits', name: 'Audits', count: 156 },
    { id: 'actions', name: 'Actions', count: 523 },
    { id: 'documents', name: 'Documents', count: 312 }
  ];

  const exportJobs: ExportJob[] = [
    {
      id: 'EXP001',
      name: 'Monthly Incident Report',
      format: 'pdf',
      modules: ['incidents'],
      status: 'completed',
      createdAt: '2024-01-19 10:30',
      completedAt: '2024-01-19 10:32',
      fileSize: '2.4 MB',
      downloadUrl: '#'
    },
    {
      id: 'EXP002',
      name: 'Full Data Export',
      format: 'excel',
      modules: ['incidents', 'rtas', 'complaints', 'risks'],
      status: 'processing',
      progress: 65,
      createdAt: '2024-01-19 10:45'
    },
    {
      id: 'EXP003',
      name: 'Audit Evidence Pack',
      format: 'pdf',
      modules: ['audits', 'actions'],
      status: 'completed',
      createdAt: '2024-01-18 14:00',
      completedAt: '2024-01-18 14:05',
      fileSize: '8.7 MB',
      downloadUrl: '#'
    },
    {
      id: 'EXP004',
      name: 'Risk Register JSON',
      format: 'json',
      modules: ['risks'],
      status: 'failed',
      createdAt: '2024-01-17 09:00'
    }
  ];

  const templates: ExportTemplate[] = [
    {
      id: 'TPL001',
      name: 'Weekly Safety Summary',
      description: 'Automated weekly export of incidents and RTAs',
      modules: ['incidents', 'rtas'],
      format: 'pdf',
      schedule: 'Every Monday 6:00 AM',
      lastRun: '2024-01-15 06:00'
    },
    {
      id: 'TPL002',
      name: 'Monthly Compliance Pack',
      description: 'Full compliance data for management review',
      modules: ['audits', 'risks', 'actions'],
      format: 'excel',
      schedule: 'First day of month',
      lastRun: '2024-01-01 08:00'
    },
    {
      id: 'TPL003',
      name: 'Customer Feedback Report',
      description: 'Quarterly complaints analysis',
      modules: ['complaints'],
      format: 'pdf',
      schedule: 'Quarterly'
    }
  ];

  const formatIcons: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
    pdf: { icon: <FileText className="w-5 h-5" />, color: 'text-destructive', bg: 'bg-destructive/20' },
    excel: { icon: <FileSpreadsheet className="w-5 h-5" />, color: 'text-success', bg: 'bg-success/20' },
    csv: { icon: <File className="w-5 h-5" />, color: 'text-info', bg: 'bg-info/20' },
    json: { icon: <FileJson className="w-5 h-5" />, color: 'text-warning', bg: 'bg-warning/20' }
  };

  const statusVariants: Record<string, 'default' | 'in-progress' | 'resolved' | 'destructive'> = {
    pending: 'default',
    processing: 'in-progress',
    completed: 'resolved',
    failed: 'destructive'
  };

  const toggleModule = (moduleId: string) => {
    setSelectedModules(prev =>
      prev.includes(moduleId)
        ? prev.filter(m => m !== moduleId)
        : [...prev, moduleId]
    );
  };

  const handleExport = () => {
    if (selectedModules.length === 0) return;
    setIsExporting(true);
    setTimeout(() => {
      setIsExporting(false);
      setActiveTab('history');
    }, 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-primary to-primary-hover rounded-xl">
              <Download className="w-8 h-8 text-primary-foreground" />
            </div>
            Export Center
          </h1>
          <p className="text-muted-foreground mt-1">Generate reports and export data</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('new')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'new'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-2">
            <Zap className="w-5 h-5" />
            New Export
          </span>
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'history'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-2">
            <History className="w-5 h-5" />
            Export History
          </span>
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'templates'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Templates
          </span>
        </button>
      </div>

      {/* New Export Tab */}
      {activeTab === 'new' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Module Selection */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Filter className="w-5 h-5 text-primary" />
                  Select Modules
                </h2>
                
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {modules.map((module) => (
                    <button
                      key={module.id}
                      onClick={() => toggleModule(module.id)}
                      className={cn(
                        "p-4 rounded-xl border transition-all",
                        selectedModules.includes(module.id)
                          ? 'bg-primary/20 border-primary text-foreground'
                          : 'bg-muted/30 border-border text-muted-foreground hover:border-primary/50'
                      )}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{module.name}</span>
                        {selectedModules.includes(module.id) && (
                          <CheckCircle2 className="w-5 h-5 text-primary" />
                        )}
                      </div>
                      <span className="text-sm text-muted-foreground">{module.count} records</span>
                    </button>
                  ))}
                </div>
                
                <div className="flex items-center gap-4 mt-4">
                  <button
                    onClick={() => setSelectedModules(modules.map(m => m.id))}
                    className="text-sm text-primary hover:text-primary-hover"
                  >
                    Select All
                  </button>
                  <button
                    onClick={() => setSelectedModules([])}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    Clear Selection
                  </button>
                </div>
              </CardContent>
            </Card>

            {/* Date Range */}
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-primary" />
                  Date Range
                </h2>
                
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { value: 'today', label: 'Today' },
                    { value: 'week', label: 'This Week' },
                    { value: 'month', label: 'This Month' },
                    { value: 'quarter', label: 'This Quarter' },
                    { value: 'year', label: 'This Year' },
                    { value: 'all', label: 'All Time' }
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => setDateRange(option.value)}
                      className={cn(
                        "p-3 rounded-xl border transition-all",
                        dateRange === option.value
                          ? 'bg-primary/20 border-primary text-foreground'
                          : 'bg-muted/30 border-border text-muted-foreground hover:border-primary/50'
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Export Options Sidebar */}
          <div className="space-y-6">
            {/* Format Selection */}
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold text-foreground mb-4">Export Format</h2>
                
                <div className="space-y-2">
                  {Object.entries(formatIcons).map(([format, { icon, color, bg }]) => (
                    <button
                      key={format}
                      onClick={() => setSelectedFormat(format as 'pdf' | 'excel' | 'csv' | 'json')}
                      className={cn(
                        "w-full p-3 rounded-xl border flex items-center gap-3 transition-all",
                        selectedFormat === format
                          ? 'bg-primary/20 border-primary'
                          : 'bg-muted/30 border-border hover:border-primary/50'
                      )}
                    >
                      <div className={cn("p-2 rounded-lg", bg)}>
                        <div className={color}>{icon}</div>
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground uppercase">{format}</p>
                        <p className="text-xs text-muted-foreground">
                          {format === 'pdf' && 'Formatted report'}
                          {format === 'excel' && 'Spreadsheet with charts'}
                          {format === 'csv' && 'Raw data export'}
                          {format === 'json' && 'API-ready format'}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Export Summary */}
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold text-foreground mb-4">Summary</h2>
                
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Modules</span>
                    <span className="text-foreground font-medium">{selectedModules.length} selected</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Date Range</span>
                    <span className="text-foreground font-medium capitalize">{dateRange}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Format</span>
                    <span className="text-foreground font-medium uppercase">{selectedFormat}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Est. Records</span>
                    <span className="text-foreground font-medium">
                      {selectedModules.reduce((acc, id) => {
                        const mod = modules.find(m => m.id === id);
                        return acc + (mod?.count || 0);
                      }, 0).toLocaleString()}
                    </span>
                  </div>
                </div>
                
                <Button
                  onClick={handleExport}
                  disabled={selectedModules.length === 0 || isExporting}
                  className="w-full mt-6"
                >
                  {isExporting ? (
                    <>
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      Exporting...
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5" />
                      Start Export
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Export</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Format</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Modules</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Status</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Created</th>
                  <th className="text-center p-4 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {exportJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-border hover:bg-muted/30 transition-colors"
                  >
                    <td className="p-4">
                      <p className="font-medium text-foreground">{job.name}</p>
                      <p className="text-xs text-muted-foreground">{job.id}</p>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <div className={cn("p-1.5 rounded-lg", formatIcons[job.format].bg)}>
                          <div className={formatIcons[job.format].color}>
                            {formatIcons[job.format].icon}
                          </div>
                        </div>
                        <span className="uppercase text-sm text-foreground">{job.format}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-1">
                        {job.modules.map((mod, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 bg-muted text-muted-foreground rounded text-xs"
                          >
                            {mod}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <Badge variant={statusVariants[job.status]}>
                          {job.status}
                        </Badge>
                        {job.status === 'processing' && job.progress && (
                          <span className="text-xs text-muted-foreground">{job.progress}%</span>
                        )}
                      </div>
                      {job.status === 'processing' && job.progress && (
                        <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-primary to-primary-hover rounded-full transition-all"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      )}
                    </td>
                    <td className="p-4">
                      <p className="text-sm text-foreground">{job.createdAt}</p>
                      {job.fileSize && (
                        <p className="text-xs text-muted-foreground">{job.fileSize}</p>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-center gap-2">
                        {job.status === 'completed' && job.downloadUrl && (
                          <Button variant="ghost" size="sm" className="text-success hover:text-success" asChild>
                            <a href={job.downloadUrl} title="Download">
                              <Download className="w-4 h-4" />
                            </a>
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" title="Delete">
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <Card
              key={template.id}
              className="hover:border-primary/50 transition-all"
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className={cn("p-3 rounded-xl", formatIcons[template.format].bg)}>
                    <div className={formatIcons[template.format].color}>
                      {formatIcons[template.format].icon}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm">
                    <Settings className="w-5 h-5" />
                  </Button>
                </div>
                
                <h3 className="text-lg font-semibold text-foreground mb-1">{template.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">{template.description}</p>
                
                <div className="flex flex-wrap gap-1 mb-4">
                  {template.modules.map((mod, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 bg-muted text-muted-foreground rounded text-xs"
                    >
                      {mod}
                    </span>
                  ))}
                </div>
                
                <div className="pt-4 border-t border-border space-y-2 text-sm">
                  {template.schedule && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Clock className="w-4 h-4" />
                      {template.schedule}
                    </div>
                  )}
                  {template.lastRun && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <History className="w-4 h-4" />
                      Last run: {template.lastRun}
                    </div>
                  )}
                </div>
                
                <Button variant="outline" className="w-full mt-4">
                  <Play className="w-4 h-4" />
                  Run Now
                </Button>
              </CardContent>
            </Card>
          ))}
          
          {/* Add Template Card */}
          <button className="bg-card/30 rounded-xl border border-dashed border-border p-6 flex flex-col items-center justify-center gap-3 hover:border-primary/50 hover:bg-card/50 transition-all min-h-[280px]">
            <div className="p-3 rounded-xl bg-muted">
              <Settings className="w-6 h-6 text-muted-foreground" />
            </div>
            <span className="text-muted-foreground font-medium">Create Template</span>
          </button>
        </div>
      )}
    </div>
  );
}
