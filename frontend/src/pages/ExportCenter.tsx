import { useState, useEffect, useCallback } from "react";
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
  Zap,
} from "lucide-react";
import { cn } from "../helpers/utils";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { analyticsApi } from "../api/client";

interface ExportJob {
  id: string;
  name: string;
  format: "pdf" | "excel" | "csv" | "json";
  modules: string[];
  status: "pending" | "processing" | "completed" | "failed";
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
  format: "pdf" | "excel" | "csv" | "json";
  schedule?: string;
  lastRun?: string;
}

export default function ExportCenter() {
  const [activeTab, setActiveTab] = useState<"new" | "history" | "templates">(
    "new",
  );
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [selectedFormat, setSelectedFormat] = useState<
    "pdf" | "excel" | "csv" | "json"
  >("excel");
  const [dateRange, setDateRange] = useState<string>("all");
  const [isExporting, setIsExporting] = useState(false);

  const [modules, setModules] = useState([
    { id: "incidents", name: "Incidents", count: 0 },
    { id: "actions", name: "Actions", count: 0 },
    { id: "audits", name: "Audits", count: 0 },
    { id: "risks", name: "Risks", count: 0 },
    { id: "complaints", name: "Complaints", count: 0 },
  ]);
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([]);
  const [templates] = useState<ExportTemplate[]>([]);

  const loadModuleCounts = useCallback(async () => {
    try {
      const res = await analyticsApi.getKPIs();
      const kpis = res.data as Record<string, Record<string, number>>;
      setModules((prev) =>
        prev.map((m) => ({
          ...m,
          count: kpis[m.id]?.["total"] || m.count,
        })),
      );
    } catch {
      // keep defaults
    }
  }, []);

  useEffect(() => {
    loadModuleCounts();
  }, [loadModuleCounts]);

  const formatIcons: Record<
    string,
    { icon: React.ReactNode; color: string; bg: string }
  > = {
    pdf: {
      icon: <FileText className="w-5 h-5" />,
      color: "text-destructive",
      bg: "bg-destructive/20",
    },
    excel: {
      icon: <FileSpreadsheet className="w-5 h-5" />,
      color: "text-success",
      bg: "bg-success/20",
    },
    csv: {
      icon: <File className="w-5 h-5" />,
      color: "text-info",
      bg: "bg-info/20",
    },
    json: {
      icon: <FileJson className="w-5 h-5" />,
      color: "text-warning",
      bg: "bg-warning/20",
    },
  };

  const statusVariants: Record<
    string,
    "default" | "in-progress" | "resolved" | "destructive"
  > = {
    pending: "default",
    processing: "in-progress",
    completed: "resolved",
    failed: "destructive",
  };

  const toggleModule = (moduleId: string) => {
    setSelectedModules((prev) =>
      prev.includes(moduleId)
        ? prev.filter((m) => m !== moduleId)
        : [...prev, moduleId],
    );
  };

  const handleExport = async () => {
    if (selectedModules.length === 0) return;
    setIsExporting(true);
    try {
      const res = await analyticsApi.getExecutiveSummary(
        dateRange === "all" ? undefined : dateRange,
      );
      const reportData = res.data;
      const blob = new Blob(
        [
          selectedFormat === "json"
            ? JSON.stringify(reportData, null, 2)
            : JSON.stringify(reportData),
        ],
        { type: selectedFormat === "json" ? "application/json" : "text/plain" },
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `export-${selectedModules.join("-")}-${Date.now()}.${selectedFormat === "excel" ? "json" : selectedFormat}`;
      a.click();
      URL.revokeObjectURL(url);

      const newJob: ExportJob = {
        id: `EXP${Date.now()}`,
        name: `${selectedModules.join(", ")} Export`,
        format: selectedFormat,
        modules: selectedModules,
        status: "completed",
        createdAt: new Date().toLocaleString(),
        completedAt: new Date().toLocaleString(),
        fileSize: `${(blob.size / 1024).toFixed(1)} KB`,
      };
      setExportJobs((prev) => [newJob, ...prev]);
      setActiveTab("history");
    } catch (err) {
      const failedJob: ExportJob = {
        id: `EXP${Date.now()}`,
        name: `${selectedModules.join(", ")} Export`,
        format: selectedFormat,
        modules: selectedModules,
        status: "failed",
        createdAt: new Date().toLocaleString(),
      };
      setExportJobs((prev) => [failedJob, ...prev]);
      setActiveTab("history");
    } finally {
      setIsExporting(false);
    }
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
          <p className="text-muted-foreground mt-1">
            Generate reports and export data
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab("new")}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === "new"
              ? "text-primary border-primary"
              : "text-muted-foreground border-transparent hover:text-foreground",
          )}
        >
          <span className="flex items-center gap-2">
            <Zap className="w-5 h-5" />
            New Export
          </span>
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === "history"
              ? "text-primary border-primary"
              : "text-muted-foreground border-transparent hover:text-foreground",
          )}
        >
          <span className="flex items-center gap-2">
            <History className="w-5 h-5" />
            Export History
          </span>
        </button>
        <button
          onClick={() => setActiveTab("templates")}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === "templates"
              ? "text-primary border-primary"
              : "text-muted-foreground border-transparent hover:text-foreground",
          )}
        >
          <span className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Templates
          </span>
        </button>
      </div>

      {/* New Export Tab */}
      {activeTab === "new" && (
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
                          ? "bg-primary/20 border-primary text-foreground"
                          : "bg-muted/30 border-border text-muted-foreground hover:border-primary/50",
                      )}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{module.name}</span>
                        {selectedModules.includes(module.id) && (
                          <CheckCircle2 className="w-5 h-5 text-primary" />
                        )}
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {module.count} records
                      </span>
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-4 mt-4">
                  <button
                    onClick={() => setSelectedModules(modules.map((m) => m.id))}
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
                    { value: "today", label: "Today" },
                    { value: "week", label: "This Week" },
                    { value: "month", label: "This Month" },
                    { value: "quarter", label: "This Quarter" },
                    { value: "year", label: "This Year" },
                    { value: "all", label: "All Time" },
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => setDateRange(option.value)}
                      className={cn(
                        "p-3 rounded-xl border transition-all",
                        dateRange === option.value
                          ? "bg-primary/20 border-primary text-foreground"
                          : "bg-muted/30 border-border text-muted-foreground hover:border-primary/50",
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
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Export Format
                </h2>

                <div className="space-y-2">
                  {Object.entries(formatIcons).map(
                    ([format, { icon, color, bg }]) => (
                      <button
                        key={format}
                        onClick={() =>
                          setSelectedFormat(
                            format as "pdf" | "excel" | "csv" | "json",
                          )
                        }
                        className={cn(
                          "w-full p-3 rounded-xl border flex items-center gap-3 transition-all",
                          selectedFormat === format
                            ? "bg-primary/20 border-primary"
                            : "bg-muted/30 border-border hover:border-primary/50",
                        )}
                      >
                        <div className={cn("p-2 rounded-lg", bg)}>
                          <div className={color}>{icon}</div>
                        </div>
                        <div className="text-left">
                          <p className="font-medium text-foreground uppercase">
                            {format}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {format === "pdf" && "Formatted report"}
                            {format === "excel" && "Spreadsheet with charts"}
                            {format === "csv" && "Raw data export"}
                            {format === "json" && "API-ready format"}
                          </p>
                        </div>
                      </button>
                    ),
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Export Summary */}
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Summary
                </h2>

                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Modules</span>
                    <span className="text-foreground font-medium">
                      {selectedModules.length} selected
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Date Range</span>
                    <span className="text-foreground font-medium capitalize">
                      {dateRange}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Format</span>
                    <span className="text-foreground font-medium uppercase">
                      {selectedFormat}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Est. Records</span>
                    <span className="text-foreground font-medium">
                      {selectedModules
                        .reduce((acc, id) => {
                          const mod = modules.find((m) => m.id === id);
                          return acc + (mod?.count || 0);
                        }, 0)
                        .toLocaleString()}
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
      {activeTab === "history" && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Export
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Format
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Modules
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    Created
                  </th>
                  <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                    Actions
                  </th>
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
                        <div
                          className={cn(
                            "p-1.5 rounded-lg",
                            formatIcons[job.format]!.bg,
                          )}
                        >
                          <div className={formatIcons[job.format]!.color}>
                            {formatIcons[job.format]!.icon}
                          </div>
                        </div>
                        <span className="uppercase text-sm text-foreground">
                          {job.format}
                        </span>
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
                        {job.status === "processing" && job.progress && (
                          <span className="text-xs text-muted-foreground">
                            {job.progress}%
                          </span>
                        )}
                      </div>
                      {job.status === "processing" && job.progress && (
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
                        <p className="text-xs text-muted-foreground">
                          {job.fileSize}
                        </p>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-center gap-2">
                        {job.status === "completed" && job.downloadUrl && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-success hover:text-success"
                            asChild
                          >
                            <a href={job.downloadUrl} title="Download">
                              <Download className="w-4 h-4" />
                            </a>
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          title="Delete"
                        >
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
      {activeTab === "templates" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <Card
              key={template.id}
              className="hover:border-primary/50 transition-all"
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div
                    className={cn(
                      "p-3 rounded-xl",
                      formatIcons[template.format]!.bg,
                    )}
                  >
                    <div className={formatIcons[template.format]!.color}>
                      {formatIcons[template.format]!.icon}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm">
                    <Settings className="w-5 h-5" />
                  </Button>
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-1">
                  {template.name}
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {template.description}
                </p>

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
            <span className="text-muted-foreground font-medium">
              Create Template
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
