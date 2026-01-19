/**
 * Report Generator
 * 
 * Features:
 * - Automated monthly reports
 * - PDF/Excel export
 * - Scheduled reports
 * - Template management
 */

import React, { useState } from 'react';
import {
  FileText,
  Download,
  Calendar,
  Clock,
  Mail,
  Users,
  Settings,
  Play,
  Pause,
  Trash2,
  Plus,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  FileSpreadsheet,
  Presentation,
  Filter,
} from 'lucide-react';

interface ScheduledReport {
  id: number;
  name: string;
  template: string;
  schedule: string;
  nextRun: string;
  recipients: string[];
  format: string;
  status: 'active' | 'paused';
  lastRun?: string;
  lastStatus?: 'success' | 'failed';
}

interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  icon: React.ElementType;
  sections: string[];
}

const reportTemplates: ReportTemplate[] = [
  {
    id: 'executive',
    name: 'Executive Summary',
    description: 'High-level KPIs, trends, and key insights for leadership',
    icon: Presentation,
    sections: ['KPI Overview', 'Trend Analysis', 'Top Issues', 'Recommendations'],
  },
  {
    id: 'safety',
    name: 'Safety Performance',
    description: 'Comprehensive safety metrics and incident analysis',
    icon: AlertCircle,
    sections: ['Incident Summary', 'RIDDOR Report', 'Near Misses', 'Action Status'],
  },
  {
    id: 'compliance',
    name: 'Compliance Report',
    description: 'ISO compliance status and audit findings',
    icon: CheckCircle,
    sections: ['Compliance Score', 'Gap Analysis', 'Audit Results', 'Evidence Status'],
  },
  {
    id: 'audit',
    name: 'Audit Summary',
    description: 'Audit results, findings, and corrective actions',
    icon: FileText,
    sections: ['Audit Schedule', 'Findings', 'Non-Conformances', 'CAPA Tracker'],
  },
  {
    id: 'risk',
    name: 'Risk Assessment',
    description: 'Risk register overview and mitigation progress',
    icon: AlertCircle,
    sections: ['Risk Matrix', 'Top Risks', 'Mitigation Status', 'Emerging Risks'],
  },
  {
    id: 'training',
    name: 'Training Report',
    description: 'Training completion and compliance status',
    icon: Users,
    sections: ['Completion Rates', 'Expiring Certifications', 'Training Matrix', 'Gaps'],
  },
];

const scheduledReports: ScheduledReport[] = [
  {
    id: 1,
    name: 'Monthly Executive Summary',
    template: 'executive',
    schedule: 'Monthly (1st)',
    nextRun: '2026-02-01 09:00',
    recipients: ['leadership@plantexpand.com'],
    format: 'pdf',
    status: 'active',
    lastRun: '2026-01-01 09:00',
    lastStatus: 'success',
  },
  {
    id: 2,
    name: 'Weekly Safety Report',
    template: 'safety',
    schedule: 'Weekly (Monday)',
    nextRun: '2026-01-20 08:00',
    recipients: ['safety@plantexpand.com', 'operations@plantexpand.com'],
    format: 'pdf',
    status: 'active',
    lastRun: '2026-01-13 08:00',
    lastStatus: 'success',
  },
  {
    id: 3,
    name: 'Quarterly Compliance',
    template: 'compliance',
    schedule: 'Quarterly',
    nextRun: '2026-04-01 09:00',
    recipients: ['compliance@plantexpand.com'],
    format: 'pdf',
    status: 'paused',
    lastRun: '2025-10-01 09:00',
    lastStatus: 'success',
  },
];

export default function ReportGenerator() {
  const [activeTab, setActiveTab] = useState<'generate' | 'scheduled' | 'history'>('generate');
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [reports, setReports] = useState(scheduledReports);

  const [reportConfig, setReportConfig] = useState({
    timeRange: 'last_month',
    format: 'pdf',
    includeCharts: true,
    includeData: true,
    sendEmail: false,
    recipients: '',
  });

  const handleGenerateReport = async () => {
    if (!selectedTemplate) return;
    setGenerating(true);
    await new Promise(resolve => setTimeout(resolve, 2000));
    setGenerating(false);
    // Trigger download
    alert('Report generated! Download starting...');
  };

  const toggleReportStatus = (id: number) => {
    setReports(prev => prev.map(r => 
      r.id === id ? { ...r, status: r.status === 'active' ? 'paused' : 'active' } : r
    ));
  };

  const tabs = [
    { id: 'generate', label: 'Generate Report', icon: FileText },
    { id: 'scheduled', label: 'Scheduled Reports', icon: Calendar },
    { id: 'history', label: 'Report History', icon: Clock },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Report Generator</h1>
          <p className="text-gray-400 mt-1">Create and schedule automated reports</p>
        </div>
        <button
          onClick={() => setShowScheduleModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Schedule New Report
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/50 p-1 rounded-xl">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-emerald-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Generate Tab */}
      {activeTab === 'generate' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Template Selection */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-semibold text-white">Select Report Template</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {reportTemplates.map(template => (
                <div
                  key={template.id}
                  onClick={() => setSelectedTemplate(template.id)}
                  className={`p-4 bg-slate-800/50 border rounded-xl cursor-pointer transition-all ${
                    selectedTemplate === template.id
                      ? 'border-emerald-500 ring-2 ring-emerald-500/30'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`p-2.5 rounded-lg ${
                      selectedTemplate === template.id ? 'bg-emerald-500/20' : 'bg-slate-700'
                    }`}>
                      <template.icon className={`w-5 h-5 ${
                        selectedTemplate === template.id ? 'text-emerald-400' : 'text-gray-400'
                      }`} />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium text-white">{template.name}</h3>
                      <p className="text-sm text-gray-400 mt-1">{template.description}</p>
                      <div className="flex flex-wrap gap-1 mt-3">
                        {template.sections.map(section => (
                          <span key={section} className="px-2 py-0.5 bg-slate-700 rounded text-xs text-gray-300">
                            {section}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Report Configuration */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-white">Report Options</h2>
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
              {/* Time Range */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Time Range</label>
                <select
                  value={reportConfig.timeRange}
                  onChange={(e) => setReportConfig(prev => ({ ...prev, timeRange: e.target.value }))}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="last_week">Last Week</option>
                  <option value="last_month">Last Month</option>
                  <option value="last_quarter">Last Quarter</option>
                  <option value="last_year">Last Year</option>
                  <option value="year_to_date">Year to Date</option>
                  <option value="custom">Custom Range</option>
                </select>
              </div>

              {/* Format */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Export Format</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: 'pdf', label: 'PDF', icon: FileText },
                    { value: 'excel', label: 'Excel', icon: FileSpreadsheet },
                    { value: 'pptx', label: 'PowerPoint', icon: Presentation },
                  ].map(format => (
                    <button
                      key={format.value}
                      onClick={() => setReportConfig(prev => ({ ...prev, format: format.value }))}
                      className={`flex flex-col items-center p-3 rounded-lg border transition-all ${
                        reportConfig.format === format.value
                          ? 'bg-emerald-600/20 border-emerald-500 text-emerald-400'
                          : 'bg-slate-700/50 border-slate-600 text-gray-400 hover:border-slate-500'
                      }`}
                    >
                      <format.icon className="w-5 h-5 mb-1" />
                      <span className="text-xs">{format.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Include Options */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Include</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reportConfig.includeCharts}
                      onChange={(e) => setReportConfig(prev => ({ ...prev, includeCharts: e.target.checked }))}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500"
                    />
                    <span className="text-sm text-gray-300">Charts & Visualizations</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reportConfig.includeData}
                      onChange={(e) => setReportConfig(prev => ({ ...prev, includeData: e.target.checked }))}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500"
                    />
                    <span className="text-sm text-gray-300">Raw Data Tables</span>
                  </label>
                </div>
              </div>

              {/* Email Option */}
              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={reportConfig.sendEmail}
                    onChange={(e) => setReportConfig(prev => ({ ...prev, sendEmail: e.target.checked }))}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span className="text-sm text-gray-300">Send via Email</span>
                </label>
                {reportConfig.sendEmail && (
                  <input
                    type="email"
                    placeholder="Enter email addresses"
                    value={reportConfig.recipients}
                    onChange={(e) => setReportConfig(prev => ({ ...prev, recipients: e.target.value }))}
                    className="w-full mt-2 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm"
                  />
                )}
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerateReport}
                disabled={!selectedTemplate || generating}
                className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors ${
                  selectedTemplate && !generating
                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    : 'bg-slate-700 text-gray-500 cursor-not-allowed'
                }`}
              >
                {generating ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    Generate Report
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Scheduled Reports Tab */}
      {activeTab === 'scheduled' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-700/50">
              <tr>
                <th className="text-left p-4 text-sm font-medium text-gray-400">Report</th>
                <th className="text-left p-4 text-sm font-medium text-gray-400">Schedule</th>
                <th className="text-left p-4 text-sm font-medium text-gray-400">Next Run</th>
                <th className="text-left p-4 text-sm font-medium text-gray-400">Recipients</th>
                <th className="text-left p-4 text-sm font-medium text-gray-400">Status</th>
                <th className="text-right p-4 text-sm font-medium text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map(report => (
                <tr key={report.id} className="border-t border-slate-700">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-emerald-400" />
                      <div>
                        <div className="font-medium text-white">{report.name}</div>
                        <div className="text-sm text-gray-400">{report.format.toUpperCase()}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4 text-gray-300">{report.schedule}</td>
                  <td className="p-4 text-gray-300">{report.nextRun}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-1">
                      <Mail className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-300">{report.recipients.length}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                      report.status === 'active'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {report.status === 'active' ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                      {report.status}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center justify-end gap-2">
                      <button 
                        onClick={() => toggleReportStatus(report.id)}
                        className="p-2 text-gray-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                      >
                        {report.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      </button>
                      <button className="p-2 text-gray-400 hover:text-white hover:bg-slate-700 rounded transition-colors">
                        <Settings className="w-4 h-4" />
                      </button>
                      <button className="p-2 text-gray-400 hover:text-red-400 hover:bg-slate-700 rounded transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h3 className="font-medium text-white">Recent Reports</h3>
            <button className="flex items-center gap-2 text-sm text-gray-400 hover:text-white">
              <Filter className="w-4 h-4" />
              Filter
            </button>
          </div>
          <div className="divide-y divide-slate-700">
            {[
              { name: 'Monthly Executive Summary', date: '2026-01-01 09:00', status: 'success', size: '2.4 MB' },
              { name: 'Weekly Safety Report', date: '2026-01-13 08:00', status: 'success', size: '1.8 MB' },
              { name: 'Weekly Safety Report', date: '2026-01-06 08:00', status: 'success', size: '1.7 MB' },
              { name: 'Quarterly Compliance', date: '2025-10-01 09:00', status: 'success', size: '3.2 MB' },
              { name: 'Monthly Executive Summary', date: '2025-12-01 09:00', status: 'failed', size: '-' },
            ].map((report, i) => (
              <div key={i} className="p-4 flex items-center justify-between hover:bg-slate-700/30">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${
                    report.status === 'success' ? 'bg-emerald-500/20' : 'bg-red-500/20'
                  }`}>
                    {report.status === 'success' 
                      ? <CheckCircle className="w-5 h-5 text-emerald-400" />
                      : <AlertCircle className="w-5 h-5 text-red-400" />
                    }
                  </div>
                  <div>
                    <div className="font-medium text-white">{report.name}</div>
                    <div className="text-sm text-gray-400">{report.date}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-400">{report.size}</span>
                  {report.status === 'success' && (
                    <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors">
                      <Download className="w-4 h-4" />
                      Download
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">Schedule New Report</h3>
              <button onClick={() => setShowScheduleModal(false)} className="text-gray-400 hover:text-white">
                ×
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-gray-400">Report scheduling coming soon...</p>
              <button
                onClick={() => setShowScheduleModal(false)}
                className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
