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
    pdf: { icon: <FileText className="w-5 h-5" />, color: 'text-red-400', bg: 'bg-red-500/20' },
    excel: { icon: <FileSpreadsheet className="w-5 h-5" />, color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
    csv: { icon: <File className="w-5 h-5" />, color: 'text-blue-400', bg: 'bg-blue-500/20' },
    json: { icon: <FileJson className="w-5 h-5" />, color: 'text-amber-400', bg: 'bg-amber-500/20' }
  };

  const statusColors: Record<string, { bg: string; text: string }> = {
    pending: { bg: 'bg-slate-500/20', text: 'text-slate-400' },
    processing: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
    completed: { bg: 'bg-emerald-500/20', text: 'text-emerald-400' },
    failed: { bg: 'bg-red-500/20', text: 'text-red-400' }
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
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-teal-500 to-cyan-600 rounded-xl">
              <Download className="w-8 h-8" />
            </div>
            Export Center
          </h1>
          <p className="text-slate-400 mt-1">Generate reports and export data</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700/50">
        <button
          onClick={() => setActiveTab('new')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'new'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Zap className="w-5 h-5" />
            New Export
          </span>
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'history'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <History className="w-5 h-5" />
            Export History
          </span>
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'templates'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
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
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Filter className="w-5 h-5 text-violet-400" />
                Select Modules
              </h2>
              
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {modules.map((module) => (
                  <button
                    key={module.id}
                    onClick={() => toggleModule(module.id)}
                    className={`p-4 rounded-xl border transition-all ${
                      selectedModules.includes(module.id)
                        ? 'bg-violet-500/20 border-violet-500 text-white'
                        : 'bg-slate-900/30 border-slate-700 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">{module.name}</span>
                      {selectedModules.includes(module.id) && (
                        <CheckCircle2 className="w-5 h-5 text-violet-400" />
                      )}
                    </div>
                    <span className="text-sm text-slate-500">{module.count} records</span>
                  </button>
                ))}
              </div>
              
              <div className="flex items-center gap-4 mt-4">
                <button
                  onClick={() => setSelectedModules(modules.map(m => m.id))}
                  className="text-sm text-violet-400 hover:text-violet-300"
                >
                  Select All
                </button>
                <button
                  onClick={() => setSelectedModules([])}
                  className="text-sm text-slate-400 hover:text-white"
                >
                  Clear Selection
                </button>
              </div>
            </div>

            {/* Date Range */}
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Calendar className="w-5 h-5 text-violet-400" />
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
                    className={`p-3 rounded-xl border transition-all ${
                      dateRange === option.value
                        ? 'bg-violet-500/20 border-violet-500 text-white'
                        : 'bg-slate-900/30 border-slate-700 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Export Options Sidebar */}
          <div className="space-y-6">
            {/* Format Selection */}
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Export Format</h2>
              
              <div className="space-y-2">
                {Object.entries(formatIcons).map(([format, { icon, color, bg }]) => (
                  <button
                    key={format}
                    onClick={() => setSelectedFormat(format as any)}
                    className={`w-full p-3 rounded-xl border flex items-center gap-3 transition-all ${
                      selectedFormat === format
                        ? 'bg-violet-500/20 border-violet-500'
                        : 'bg-slate-900/30 border-slate-700 hover:border-slate-600'
                    }`}
                  >
                    <div className={`p-2 rounded-lg ${bg}`}>
                      <div className={color}>{icon}</div>
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-white uppercase">{format}</p>
                      <p className="text-xs text-slate-500">
                        {format === 'pdf' && 'Formatted report'}
                        {format === 'excel' && 'Spreadsheet with charts'}
                        {format === 'csv' && 'Raw data export'}
                        {format === 'json' && 'API-ready format'}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Export Summary */}
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Summary</h2>
              
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-400">Modules</span>
                  <span className="text-white font-medium">{selectedModules.length} selected</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Date Range</span>
                  <span className="text-white font-medium capitalize">{dateRange}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Format</span>
                  <span className="text-white font-medium uppercase">{selectedFormat}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Est. Records</span>
                  <span className="text-white font-medium">
                    {selectedModules.reduce((acc, id) => {
                      const mod = modules.find(m => m.id === id);
                      return acc + (mod?.count || 0);
                    }, 0).toLocaleString()}
                  </span>
                </div>
              </div>
              
              <button
                onClick={handleExport}
                disabled={selectedModules.length === 0 || isExporting}
                className={`w-full mt-6 py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 ${
                  selectedModules.length === 0
                    ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    : 'bg-gradient-to-r from-violet-600 to-purple-600 text-white hover:from-violet-500 hover:to-purple-500'
                }`}
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
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-slate-400">Export</th>
                  <th className="text-left p-4 text-sm font-medium text-slate-400">Format</th>
                  <th className="text-left p-4 text-sm font-medium text-slate-400">Modules</th>
                  <th className="text-left p-4 text-sm font-medium text-slate-400">Status</th>
                  <th className="text-left p-4 text-sm font-medium text-slate-400">Created</th>
                  <th className="text-center p-4 text-sm font-medium text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {exportJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors"
                  >
                    <td className="p-4">
                      <p className="font-medium text-white">{job.name}</p>
                      <p className="text-xs text-slate-500">{job.id}</p>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <div className={`p-1.5 rounded-lg ${formatIcons[job.format].bg}`}>
                          <div className={formatIcons[job.format].color}>
                            {formatIcons[job.format].icon}
                          </div>
                        </div>
                        <span className="uppercase text-sm text-slate-300">{job.format}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-1">
                        {job.modules.map((mod, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 bg-slate-700/50 text-slate-300 rounded text-xs"
                          >
                            {mod}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[job.status].bg} ${statusColors[job.status].text}`}>
                          {job.status}
                        </span>
                        {job.status === 'processing' && job.progress && (
                          <span className="text-xs text-slate-400">{job.progress}%</span>
                        )}
                      </div>
                      {job.status === 'processing' && job.progress && (
                        <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full transition-all"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      )}
                    </td>
                    <td className="p-4">
                      <p className="text-sm text-slate-300">{job.createdAt}</p>
                      {job.fileSize && (
                        <p className="text-xs text-slate-500">{job.fileSize}</p>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-center gap-2">
                        {job.status === 'completed' && job.downloadUrl && (
                          <a
                            href={job.downloadUrl}
                            className="p-2 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors"
                            title="Download"
                          >
                            <Download className="w-4 h-4" />
                          </a>
                        )}
                        <button
                          className="p-2 text-slate-400 hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <div
              key={template.id}
              className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6 hover:border-violet-500/50 transition-all"
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl ${formatIcons[template.format].bg}`}>
                  <div className={formatIcons[template.format].color}>
                    {formatIcons[template.format].icon}
                  </div>
                </div>
                <button className="p-2 text-slate-400 hover:text-white transition-colors">
                  <Settings className="w-5 h-5" />
                </button>
              </div>
              
              <h3 className="text-lg font-semibold text-white mb-1">{template.name}</h3>
              <p className="text-sm text-slate-400 mb-4">{template.description}</p>
              
              <div className="flex flex-wrap gap-1 mb-4">
                {template.modules.map((mod, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 bg-slate-700/50 text-slate-300 rounded text-xs"
                  >
                    {mod}
                  </span>
                ))}
              </div>
              
              <div className="pt-4 border-t border-slate-700/50 space-y-2 text-sm">
                {template.schedule && (
                  <div className="flex items-center gap-2 text-slate-400">
                    <Clock className="w-4 h-4" />
                    {template.schedule}
                  </div>
                )}
                {template.lastRun && (
                  <div className="flex items-center gap-2 text-slate-500">
                    <History className="w-4 h-4" />
                    Last run: {template.lastRun}
                  </div>
                )}
              </div>
              
              <button className="w-full mt-4 py-2 bg-violet-500/20 text-violet-400 rounded-lg font-medium hover:bg-violet-500/30 transition-all flex items-center justify-center gap-2">
                <Play className="w-4 h-4" />
                Run Now
              </button>
            </div>
          ))}
          
          {/* Add Template Card */}
          <button className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-dashed border-slate-700 p-6 flex flex-col items-center justify-center gap-3 hover:border-violet-500/50 hover:bg-slate-800/50 transition-all min-h-[280px]">
            <div className="p-3 rounded-xl bg-slate-700/50">
              <Settings className="w-6 h-6 text-slate-400" />
            </div>
            <span className="text-slate-400 font-medium">Create Template</span>
          </button>
        </div>
      )}
    </div>
  );
}
