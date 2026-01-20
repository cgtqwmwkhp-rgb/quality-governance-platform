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
import { cn } from '../lib/utils';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardHeader, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/Dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/Select';

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
          <h1 className="text-2xl font-bold text-foreground">Report Generator</h1>
          <p className="text-muted-foreground mt-1">Create and schedule automated reports</p>
        </div>
        <Button onClick={() => setShowScheduleModal(true)}>
          <Plus className="w-4 h-4" />
          Schedule New Report
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted/50 p-1 rounded-xl">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            )}
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
            <h2 className="text-lg font-semibold text-foreground">Select Report Template</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {reportTemplates.map(template => (
                <Card
                  key={template.id}
                  onClick={() => setSelectedTemplate(template.id)}
                  className={cn(
                    "cursor-pointer transition-all",
                    selectedTemplate === template.id
                      ? 'border-primary ring-2 ring-primary/30'
                      : 'hover:border-primary/50'
                  )}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "p-2.5 rounded-lg",
                        selectedTemplate === template.id ? 'bg-primary/20' : 'bg-muted'
                      )}>
                        <template.icon className={cn(
                          "w-5 h-5",
                          selectedTemplate === template.id ? 'text-primary' : 'text-muted-foreground'
                        )} />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-medium text-foreground">{template.name}</h3>
                        <p className="text-sm text-muted-foreground mt-1">{template.description}</p>
                        <div className="flex flex-wrap gap-1 mt-3">
                          {template.sections.map(section => (
                            <span key={section} className="px-2 py-0.5 bg-muted rounded text-xs text-muted-foreground">
                              {section}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Report Configuration */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Report Options</h2>
            <Card>
              <CardContent className="p-5 space-y-4">
                {/* Time Range */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Time Range</label>
                  <Select
                    value={reportConfig.timeRange}
                    onValueChange={(value) => setReportConfig(prev => ({ ...prev, timeRange: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="last_week">Last Week</SelectItem>
                      <SelectItem value="last_month">Last Month</SelectItem>
                      <SelectItem value="last_quarter">Last Quarter</SelectItem>
                      <SelectItem value="last_year">Last Year</SelectItem>
                      <SelectItem value="year_to_date">Year to Date</SelectItem>
                      <SelectItem value="custom">Custom Range</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Format */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Export Format</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { value: 'pdf', label: 'PDF', icon: FileText },
                      { value: 'excel', label: 'Excel', icon: FileSpreadsheet },
                      { value: 'pptx', label: 'PowerPoint', icon: Presentation },
                    ].map(format => (
                      <button
                        key={format.value}
                        onClick={() => setReportConfig(prev => ({ ...prev, format: format.value }))}
                        className={cn(
                          "flex flex-col items-center p-3 rounded-lg border transition-all",
                          reportConfig.format === format.value
                            ? 'bg-primary/20 border-primary text-primary'
                            : 'bg-muted/50 border-border text-muted-foreground hover:border-primary/50'
                        )}
                      >
                        <format.icon className="w-5 h-5 mb-1" />
                        <span className="text-xs">{format.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Include Options */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Include</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={reportConfig.includeCharts}
                        onChange={(e) => setReportConfig(prev => ({ ...prev, includeCharts: e.target.checked }))}
                        className="w-4 h-4 rounded border-border bg-muted text-primary focus:ring-primary"
                      />
                      <span className="text-sm text-foreground">Charts & Visualizations</span>
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={reportConfig.includeData}
                        onChange={(e) => setReportConfig(prev => ({ ...prev, includeData: e.target.checked }))}
                        className="w-4 h-4 rounded border-border bg-muted text-primary focus:ring-primary"
                      />
                      <span className="text-sm text-foreground">Raw Data Tables</span>
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
                      className="w-4 h-4 rounded border-border bg-muted text-primary focus:ring-primary"
                    />
                    <span className="text-sm text-foreground">Send via Email</span>
                  </label>
                  {reportConfig.sendEmail && (
                    <Input
                      type="email"
                      placeholder="Enter email addresses"
                      value={reportConfig.recipients}
                      onChange={(e) => setReportConfig(prev => ({ ...prev, recipients: e.target.value }))}
                      className="mt-2"
                    />
                  )}
                </div>

                {/* Generate Button */}
                <Button
                  onClick={handleGenerateReport}
                  disabled={!selectedTemplate || generating}
                  className="w-full"
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
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Scheduled Reports Tab */}
      {activeTab === 'scheduled' && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Report</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Schedule</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Next Run</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Recipients</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Status</th>
                  <th className="text-right p-4 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map(report => (
                  <tr key={report.id} className="border-t border-border">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-primary" />
                        <div>
                          <div className="font-medium text-foreground">{report.name}</div>
                          <div className="text-sm text-muted-foreground">{report.format.toUpperCase()}</div>
                        </div>
                      </div>
                    </td>
                    <td className="p-4 text-foreground">{report.schedule}</td>
                    <td className="p-4 text-foreground">{report.nextRun}</td>
                    <td className="p-4">
                      <div className="flex items-center gap-1">
                        <Mail className="w-4 h-4 text-muted-foreground" />
                        <span className="text-foreground">{report.recipients.length}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <Badge variant={report.status === 'active' ? 'resolved' : 'submitted'}>
                        {report.status === 'active' ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                        {report.status}
                      </Badge>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => toggleReportStatus(report.id)}>
                          {report.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                        </Button>
                        <Button variant="ghost" size="sm">
                          <Settings className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive">
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

      {/* History Tab */}
      {activeTab === 'history' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <h3 className="font-medium text-foreground">Recent Reports</h3>
            <Button variant="ghost" size="sm">
              <Filter className="w-4 h-4" />
              Filter
            </Button>
          </CardHeader>
          <div className="divide-y divide-border">
            {[
              { name: 'Monthly Executive Summary', date: '2026-01-01 09:00', status: 'success', size: '2.4 MB' },
              { name: 'Weekly Safety Report', date: '2026-01-13 08:00', status: 'success', size: '1.8 MB' },
              { name: 'Weekly Safety Report', date: '2026-01-06 08:00', status: 'success', size: '1.7 MB' },
              { name: 'Quarterly Compliance', date: '2025-10-01 09:00', status: 'success', size: '3.2 MB' },
              { name: 'Monthly Executive Summary', date: '2025-12-01 09:00', status: 'failed', size: '-' },
            ].map((report, i) => (
              <div key={i} className="p-4 flex items-center justify-between hover:bg-muted/30">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "p-2 rounded-lg",
                    report.status === 'success' ? 'bg-success/20' : 'bg-destructive/20'
                  )}>
                    {report.status === 'success' 
                      ? <CheckCircle className="w-5 h-5 text-success" />
                      : <AlertCircle className="w-5 h-5 text-destructive" />
                    }
                  </div>
                  <div>
                    <div className="font-medium text-foreground">{report.name}</div>
                    <div className="text-sm text-muted-foreground">{report.date}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-muted-foreground">{report.size}</span>
                  {report.status === 'success' && (
                    <Button variant="secondary" size="sm">
                      <Download className="w-4 h-4" />
                      Download
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Schedule Modal */}
      <Dialog open={showScheduleModal} onOpenChange={setShowScheduleModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule New Report</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground">Report scheduling coming soon...</p>
          <Button variant="secondary" onClick={() => setShowScheduleModal(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
