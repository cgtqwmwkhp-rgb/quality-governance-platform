import { useState, useEffect, useCallback } from "react";
import {
  Shield,
  Leaf,
  HardHat,
  Lock,
  ChevronRight,
  FileText,
  Users,
  Building2,
  Truck,
  Wrench,
  BarChart3,
  RefreshCw,
  Plus,
  Search,
  Filter,
  Download,
  Calendar,
  TrendingUp,
  Award,
  ClipboardList,
  ExternalLink,
  Link2,
  XCircle,
  X,
  Loader2,
} from "lucide-react";
import { ToastContainer, useToast } from "../components/ui/Toast";
import { TableSkeleton } from "../components/ui/SkeletonLoader";
import {
  uvdbApi,
  ErrorClass,
  createApiError,
  getApiErrorMessage,
} from "../api/client";

interface UVDBSection {
  number: string;
  title: string;
  max_score: number;
  question_count: number;
  iso_mapping: Record<string, string>;
}

interface UVDBAudit {
  id: number;
  audit_reference: string;
  company_name: string;
  audit_type: string;
  audit_date: string | null;
  status: string;
  percentage_score: number | null;
  lead_auditor: string | null;
}

// Bounded error state for deterministic UX
type LoadState = "idle" | "loading" | "success" | "error";

export default function UVDBAudits() {
  const [activeTab, setActiveTab] = useState<
    "dashboard" | "protocol" | "audits" | "mapping"
  >("dashboard");
  const [sections, setSections] = useState<UVDBSection[]>([]);
  const [audits, setAudits] = useState<UVDBAudit[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [errorClass, setErrorClass] = useState<ErrorClass | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [showNewAuditModal, setShowNewAuditModal] = useState(false);
  const [auditForm, setAuditForm] = useState({
    audit_name: "",
    audit_type: "verification",
    auditor_name: "",
    planned_date: "",
  });
  const [auditSubmitting, setAuditSubmitting] = useState(false);
  const [exportingProtocol, setExportingProtocol] = useState(false);
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();

  const handleExportProtocol = async () => {
    try {
      setExportingProtocol(true);
      const response = await uvdbApi.getProtocol();
      const blob = new Blob([JSON.stringify(response.data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `uvdb-protocol-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("Protocol exported successfully");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setExportingProtocol(false);
    }
  };

  const handleCreateAudit = async () => {
    if (!auditForm.audit_name.trim()) {
      showToast("Audit name is required", "error");
      return;
    }
    try {
      setAuditSubmitting(true);
      await uvdbApi.createAudit({
        company_name: auditForm.audit_name,
        audit_type: auditForm.audit_type,
        lead_auditor: auditForm.auditor_name || undefined,
        audit_date: auditForm.planned_date || undefined,
      });
      showToast("Audit created successfully");
      setShowNewAuditModal(false);
      setAuditForm({
        audit_name: "",
        audit_type: "verification",
        auditor_name: "",
        planned_date: "",
      });
      setRetryCount(0);
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setAuditSubmitting(false);
    }
  };

  // Transform API section to component type
  const transformSection = (apiSection: {
    section_number: number;
    title: string;
    description: string;
    question_count: number;
    weight: number;
  }): UVDBSection => ({
    number: String(apiSection.section_number),
    title: apiSection.title,
    max_score: apiSection.weight,
    question_count: apiSection.question_count,
    iso_mapping: {}, // Will be populated from ISO mapping endpoint if available
  });

  // Transform API audit to component type
  const transformAudit = (apiAudit: {
    id: number;
    reference_number: string;
    audit_year: number;
    status: string;
    percentage_score?: number;
    total_questions: number;
    answered_questions: number;
    created_at: string;
    submitted_at?: string;
  }): UVDBAudit => ({
    id: apiAudit.id,
    audit_reference: apiAudit.reference_number,
    company_name: "Plantexpand Limited", // Default company
    audit_type: "B2",
    audit_date: apiAudit.submitted_at || null,
    status: apiAudit.status,
    percentage_score: apiAudit.percentage_score || null,
    lead_auditor: null,
  });

  const loadData = useCallback(
    async (isRetry = false) => {
      if (isRetry && retryCount >= 1) {
        // Max 1 retry for transient errors
        return;
      }

      setLoadState("loading");
      setErrorClass(null);

      try {
        // Fetch sections from API
        const sectionsResponse = await uvdbApi.listSections();
        const transformedSections = sectionsResponse.data.map(transformSection);
        // Sort by section number for deterministic ordering
        transformedSections.sort(
          (a, b) => parseInt(a.number) - parseInt(b.number),
        );
        setSections(transformedSections);

        // Fetch audits from API
        const auditsResponse = await uvdbApi.listAudits(1, 50);
        const transformedAudits = auditsResponse.data.items.map(transformAudit);
        // Sort by id descending for deterministic ordering (most recent first)
        transformedAudits.sort((a, b) => b.id - a.id);
        setAudits(transformedAudits);

        // Try to get ISO mapping to enrich sections
        try {
          const mappingResponse = await uvdbApi.getISOMapping();
          const mappings = mappingResponse.data.mappings;
          // Enrich sections with ISO mapping
          const enrichedSections = transformedSections.map((section) => {
            const mapping = mappings.find(
              (m) => m.uvdb_section === section.number,
            );
            if (mapping) {
              const isoMapping: Record<string, string> = {};
              mapping.iso_clauses.forEach((clause) => {
                const [isoStandard, isoClause] = clause.split(":");
                if (isoStandard && isoClause) {
                  isoMapping[isoStandard] = isoClause;
                }
              });
              return { ...section, iso_mapping: isoMapping };
            }
            return section;
          });
          setSections(enrichedSections);
        } catch {
          // ISO mapping endpoint may not exist, sections still usable
        }

        setLoadState("success");
        setRetryCount(0);
      } catch (err) {
        const apiError = createApiError(err);
        setErrorClass(apiError.error_class);

        // Auto-retry once for transient network errors
        if (
          !isRetry &&
          (apiError.error_class === ErrorClass.NETWORK_ERROR ||
            apiError.error_class === ErrorClass.SERVER_ERROR)
        ) {
          setRetryCount((prev) => prev + 1);
          loadData(true);
          return;
        }

        setLoadState("error");
      }
    },
    [retryCount],
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalMaxScore = sections.reduce((sum, s) => sum + s.max_score, 0);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-success/10 text-success";
      case "in_progress":
        return "bg-info/10 text-info";
      case "scheduled":
        return "bg-warning/10 text-warning";
      case "expired":
        return "bg-destructive/10 text-destructive";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  const getSectionIcon = (number: string) => {
    const icons: Record<string, React.ElementType> = {
      "1": Shield,
      "2": ClipboardList,
      "3": HardHat,
      "4": HardHat,
      "5": HardHat,
      "6": Users,
      "7": Users,
      "8": Leaf,
      "9": Leaf,
      "10": Leaf,
      "11": Truck,
      "12": Building2,
      "13": Wrench,
      "14": Wrench,
      "15": BarChart3,
    };
    return icons[number] || FileText;
  };

  const getSectionColor = (number: string) => {
    const colors: Record<string, string> = {
      "1": "bg-blue-500",
      "2": "bg-blue-500",
      "3": "bg-orange-500",
      "4": "bg-orange-500",
      "5": "bg-orange-500",
      "6": "bg-orange-500",
      "7": "bg-orange-500",
      "8": "bg-emerald-500",
      "9": "bg-emerald-500",
      "10": "bg-emerald-500",
      "11": "bg-emerald-500",
      "12": "bg-purple-500",
      "13": "bg-purple-500",
      "14": "bg-yellow-500",
      "15": "bg-gray-500",
    };
    return colors[number] || "bg-gray-500";
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* New Audit Modal */}
      {showNewAuditModal && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowNewAuditModal(false);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setShowNewAuditModal(false);
          }}
        >
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                <Plus className="w-5 h-5 text-primary" />
                New UVDB Audit
              </h2>
              <button
                onClick={() => setShowNewAuditModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Audit Name
                </label>
                <input
                  type="text"
                  value={auditForm.audit_name}
                  onChange={(e) =>
                    setAuditForm((f) => ({ ...f, audit_name: e.target.value }))
                  }
                  placeholder="e.g. Plantexpand Limited - Annual Review"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/50 focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Audit Type
                </label>
                <select
                  value={auditForm.audit_type}
                  onChange={(e) =>
                    setAuditForm((f) => ({ ...f, audit_type: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary/50 focus:border-primary"
                >
                  <option value="verification">Verification</option>
                  <option value="assessment">Assessment</option>
                  <option value="desktop">Desktop</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Auditor Name
                </label>
                <input
                  type="text"
                  value={auditForm.auditor_name}
                  onChange={(e) =>
                    setAuditForm((f) => ({
                      ...f,
                      auditor_name: e.target.value,
                    }))
                  }
                  placeholder="Lead auditor name"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/50 focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Planned Date
                </label>
                <input
                  type="date"
                  value={auditForm.planned_date}
                  onChange={(e) =>
                    setAuditForm((f) => ({
                      ...f,
                      planned_date: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary/50 focus:border-primary"
                />
              </div>
              <button
                onClick={handleCreateAudit}
                disabled={auditSubmitting || !auditForm.audit_name.trim()}
                className="w-full py-3 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {auditSubmitting ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Plus className="w-5 h-5" />
                )}
                {auditSubmitting ? "Creating..." : "Create Audit"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center gap-3">
            <Award className="w-8 h-8 text-warning" />
            UVDB Achilles Verify B2
          </h1>
          <p className="text-muted-foreground">
            Utilities Vendor Database - Supply Chain Qualification Audit
          </p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button
            onClick={handleExportProtocol}
            disabled={exportingProtocol}
            className="flex items-center gap-2 px-4 py-2 bg-secondary border border-border hover:bg-surface rounded-lg transition-colors disabled:opacity-50"
          >
            {exportingProtocol ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Export Protocol
          </button>
          <button
            onClick={() => setShowNewAuditModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Audit
          </button>
        </div>
      </div>

      {/* Protocol Info Banner */}
      <div className="bg-gradient-to-r from-primary to-primary-hover rounded-xl p-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary-foreground mb-1">
              UVDB-QS-003 - Verify B2 Audit Protocol
            </h2>
            <p className="text-primary-foreground/80">
              Version 11.2 - UK Utilities Sector Qualification Standard
            </p>
          </div>
          <div className="mt-4 md:mt-0 flex items-center gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-foreground">
                {sections.length}
              </div>
              <div className="text-primary-foreground/80 text-sm">Sections</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-foreground">
                {totalMaxScore}
              </div>
              <div className="text-primary-foreground/80 text-sm">
                Max Score
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-foreground">
                4
              </div>
              <div className="text-primary-foreground/80 text-sm">
                ISO Aligned
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border pb-2 overflow-x-auto">
        {[
          { id: "dashboard", label: "Dashboard", icon: BarChart3 },
          { id: "protocol", label: "Protocol Sections", icon: ClipboardList },
          { id: "audits", label: "Audit History", icon: Calendar },
          { id: "mapping", label: "ISO Cross-Mapping", icon: Link2 },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-surface hover:text-foreground"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Loading State */}
      {loadState === "loading" && <TableSkeleton />}

      {/* Error State */}
      {loadState === "error" && (
        <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
          <XCircle className="w-12 h-12 text-destructive mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">
            Failed to Load Data
          </h3>
          <p className="text-muted-foreground mb-4">
            {errorClass === ErrorClass.NETWORK_ERROR &&
              "Network connection failed. Please check your connection."}
            {errorClass === ErrorClass.SERVER_ERROR &&
              "Server error occurred. Please try again later."}
            {errorClass === ErrorClass.AUTH_ERROR &&
              "Authentication required. Please log in."}
            {errorClass === ErrorClass.NOT_FOUND && "UVDB data not found."}
            {(errorClass === ErrorClass.UNKNOWN || !errorClass) &&
              "An unexpected error occurred."}
          </p>
          <button
            onClick={() => {
              setRetryCount(0);
              loadData();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        </div>
      )}

      {/* Empty State */}
      {loadState === "success" &&
        sections.length === 0 &&
        audits.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
            <Award className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">
              No UVDB Data Yet
            </h3>
            <p className="text-muted-foreground mb-4">
              Start your UVDB qualification journey by creating a new audit.
            </p>
            <button
              onClick={() => setShowNewAuditModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Audit
            </button>
          </div>
        )}

      {loadState === "success" &&
        (sections.length > 0 || audits.length > 0) && (
          <>
            {/* Dashboard Tab */}
            {activeTab === "dashboard" && (
              <div className="space-y-6">
                {/* ISO Alignment Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    {
                      standard: "ISO 9001:2015",
                      title: "Quality",
                      icon: Shield,
                      color: "bg-blue-500",
                      sections: "1.1, 2.1-2.5, 12-13",
                    },
                    {
                      standard: "ISO 14001:2015",
                      title: "Environmental",
                      icon: Leaf,
                      color: "bg-emerald-500",
                      sections: "1.3, 8-11, 15",
                    },
                    {
                      standard: "ISO 45001:2018",
                      title: "OH&S",
                      icon: HardHat,
                      color: "bg-orange-500",
                      sections: "1.2, 3-7, 14, 15",
                    },
                    {
                      standard: "ISO 27001:2022",
                      title: "Information Security",
                      icon: Lock,
                      color: "bg-purple-500",
                      sections: "2.3",
                    },
                  ].map((iso) => {
                    const Icon = iso.icon;
                    return (
                      <div
                        key={iso.standard}
                        className="bg-slate-800 rounded-xl p-5 border border-slate-700"
                      >
                        <div className="flex items-center gap-3 mb-3">
                          <div className={`p-2 ${iso.color} rounded-lg`}>
                            <Icon className="w-5 h-5 text-white" />
                          </div>
                          <div>
                            <div className="font-bold text-white">
                              {iso.standard}
                            </div>
                            <div className="text-xs text-gray-400">
                              {iso.title}
                            </div>
                          </div>
                        </div>
                        <div className="text-sm text-gray-300">
                          <span className="text-gray-400">UVDB Sections:</span>{" "}
                          {iso.sections}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Recent Audits */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-white">Audit Status</h3>
                      <p className="text-sm text-gray-400">
                        Plantexpand Limited (00019685)
                      </p>
                    </div>
                    <Award className="w-8 h-8 text-yellow-400" />
                  </div>
                  <div className="p-4 space-y-4">
                    {audits.map((audit) => (
                      <div
                        key={audit.id}
                        className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer"
                      >
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-yellow-500/20 rounded-lg">
                            <FileText className="w-5 h-5 text-yellow-400" />
                          </div>
                          <div>
                            <div className="font-medium text-white">
                              {audit.audit_reference}
                            </div>
                            <div className="text-sm text-gray-400">
                              {audit.audit_type} Audit •{" "}
                              {audit.audit_date || "TBD"} • {audit.lead_auditor}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          {audit.percentage_score && (
                            <div className="text-right">
                              <div className="text-2xl font-bold text-emerald-400">
                                {audit.percentage_score}%
                              </div>
                              <div className="text-xs text-gray-400">Score</div>
                            </div>
                          )}
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(audit.status)}`}
                          >
                            {audit.status}
                          </span>
                          <ChevronRight className="w-5 h-5 text-gray-400" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* KPI Summary */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600">
                    <h3 className="font-bold text-white">
                      Section 15: Key Performance Indicators (5 Year Trend)
                    </h3>
                  </div>
                  <div className="p-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
                    {[
                      { label: "Man Hours", value: "1.2M", trend: "up" },
                      { label: "Fatalities", value: "0", trend: "stable" },
                      { label: "RIDDOR", value: "2", trend: "down" },
                      { label: "LTI", value: "3", trend: "down" },
                      { label: "Near Misses", value: "45", trend: "up" },
                      { label: "Env Incidents", value: "1", trend: "stable" },
                      { label: "LTIFR", value: "2.5", trend: "down" },
                    ].map((kpi, i) => (
                      <div
                        key={i}
                        className="bg-slate-700/50 rounded-lg p-4 text-center"
                      >
                        <div className="text-2xl font-bold text-white">
                          {kpi.value}
                        </div>
                        <div className="text-xs text-gray-400">{kpi.label}</div>
                        <div
                          className={`flex items-center justify-center gap-1 mt-1 text-xs ${
                            kpi.trend === "up"
                              ? "text-emerald-400"
                              : kpi.trend === "down"
                                ? "text-red-400"
                                : "text-gray-400"
                          }`}
                        >
                          {kpi.trend === "up" && (
                            <TrendingUp className="w-3 h-3" />
                          )}
                          {kpi.trend === "down" && (
                            <TrendingUp className="w-3 h-3 transform rotate-180" />
                          )}
                          {kpi.trend === "stable" && <span>—</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Protocol Sections Tab */}
            {activeTab === "protocol" && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sections.map((section) => {
                  const Icon = getSectionIcon(section.number);
                  const bgColor = getSectionColor(section.number);
                  return (
                    <div
                      key={section.number}
                      className="bg-slate-800 rounded-xl p-5 border border-slate-700 hover:border-slate-500 transition-colors cursor-pointer"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className={`p-3 ${bgColor} rounded-xl`}>
                          <Icon className="w-6 h-6 text-white" />
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-white">
                            {section.max_score}
                          </div>
                          <div className="text-xs text-gray-400">Max Score</div>
                        </div>
                      </div>
                      <div className="text-lg font-bold text-white mb-1">
                        Section {section.number}
                      </div>
                      <div className="text-sm text-gray-300 mb-4">
                        {section.title}
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-400">
                          {section.question_count} Questions
                        </span>
                        <div className="flex gap-1">
                          {Object.keys(section.iso_mapping).map((iso) => (
                            <span
                              key={iso}
                              className={`px-2 py-0.5 rounded text-xs ${
                                iso === "9001"
                                  ? "bg-blue-500/20 text-blue-400"
                                  : iso === "14001"
                                    ? "bg-emerald-500/20 text-emerald-400"
                                    : iso === "45001"
                                      ? "bg-orange-500/20 text-orange-400"
                                      : "bg-purple-500/20 text-purple-400"
                              }`}
                            >
                              {iso}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Audit History Tab */}
            {activeTab === "audits" && (
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search audits..."
                        className="pl-10 pr-4 py-2 bg-slate-600 border border-slate-500 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
                      />
                    </div>
                    <button className="flex items-center gap-2 px-3 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors">
                      <Filter className="w-4 h-4" />
                      Filter
                    </button>
                  </div>
                  <button
                    onClick={() => setShowNewAuditModal(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    New Audit
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          Reference
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          Company
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          Type
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          Date
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          Lead Auditor
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          Score
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          Status
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                      {audits.map((audit) => (
                        <tr key={audit.id} className="hover:bg-slate-700/50">
                          <td className="px-4 py-3 font-medium text-white">
                            {audit.audit_reference}
                          </td>
                          <td className="px-4 py-3 text-gray-300">
                            {audit.company_name}
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs font-medium">
                              {audit.audit_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-300">
                            {audit.audit_date || "TBD"}
                          </td>
                          <td className="px-4 py-3 text-gray-300">
                            {audit.lead_auditor}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {audit.percentage_score ? (
                              <span className="text-emerald-400 font-bold">
                                {audit.percentage_score}%
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(audit.status)}`}
                            >
                              {audit.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button className="p-2 hover:bg-slate-600 rounded-lg transition-colors">
                              <ExternalLink className="w-4 h-4 text-gray-400" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ISO Cross-Mapping Tab */}
            {activeTab === "mapping" && (
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">
                    UVDB B2 to ISO Standards Cross-Mapping
                  </h3>
                  <p className="text-sm text-gray-400">
                    Demonstrates alignment between UVDB requirements and ISO
                    certification standards
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          UVDB Section
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          Topic
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          ISO 9001
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          ISO 14001
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          ISO 45001
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          ISO 27001
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                      {[
                        {
                          section: "1.1",
                          topic: "Quality Management Systems",
                          iso9001: "4.4, 5.1, 9.2",
                          iso14001: "",
                          iso45001: "",
                          iso27001: "",
                        },
                        {
                          section: "1.2",
                          topic: "Health and Safety Management Systems",
                          iso9001: "",
                          iso14001: "",
                          iso45001: "4.4, 5.1, 9.2",
                          iso27001: "",
                        },
                        {
                          section: "1.3",
                          topic: "Environmental Management Systems",
                          iso9001: "",
                          iso14001: "4.4, 5.1, 9.2",
                          iso45001: "",
                          iso27001: "",
                        },
                        {
                          section: "1.4",
                          topic: "CDM Regulations 2015",
                          iso9001: "",
                          iso14001: "",
                          iso45001: "6.1, 8.1",
                          iso27001: "",
                        },
                        {
                          section: "1.5",
                          topic: "Permits and Licensing",
                          iso9001: "",
                          iso14001: "6.1.3",
                          iso45001: "6.1.3",
                          iso27001: "",
                        },
                        {
                          section: "2.1",
                          topic: "Top Management Quality Assurance",
                          iso9001: "5.1, 5.2, 5.3",
                          iso14001: "",
                          iso45001: "",
                          iso27001: "",
                        },
                        {
                          section: "2.2",
                          topic: "Document Control",
                          iso9001: "7.5",
                          iso14001: "",
                          iso45001: "",
                          iso27001: "7.5",
                        },
                        {
                          section: "2.3",
                          topic: "Information Security",
                          iso9001: "",
                          iso14001: "",
                          iso45001: "",
                          iso27001: "5.1, 8.1, A.8",
                        },
                        {
                          section: "2.4",
                          topic: "Service Provision & Handover",
                          iso9001: "8.5, 8.6",
                          iso14001: "",
                          iso45001: "",
                          iso27001: "",
                        },
                        {
                          section: "2.5",
                          topic: "Internal Auditing",
                          iso9001: "9.2",
                          iso14001: "9.2",
                          iso45001: "9.2",
                          iso27001: "",
                        },
                        {
                          section: "12",
                          topic: "Sub-contractor Management",
                          iso9001: "8.4",
                          iso14001: "",
                          iso45001: "8.1.4",
                          iso27001: "",
                        },
                        {
                          section: "13",
                          topic: "Sourcing (CFSI, Sustainability)",
                          iso9001: "8.4.2",
                          iso14001: "8.1",
                          iso45001: "",
                          iso27001: "",
                        },
                        {
                          section: "14",
                          topic: "Work Equipment & Vehicles",
                          iso9001: "",
                          iso14001: "",
                          iso45001: "7.1.3, 8.1",
                          iso27001: "",
                        },
                        {
                          section: "15",
                          topic: "Key Performance Indicators",
                          iso9001: "",
                          iso14001: "9.1",
                          iso45001: "9.1",
                          iso27001: "",
                        },
                      ].map((row, i) => (
                        <tr key={i} className="hover:bg-slate-700/50">
                          <td className="px-4 py-3 font-medium text-white">
                            {row.section}
                          </td>
                          <td className="px-4 py-3 text-gray-300">
                            {row.topic}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {row.iso9001 && (
                              <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                                {row.iso9001}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {row.iso14001 && (
                              <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                                {row.iso14001}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {row.iso45001 && (
                              <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-xs">
                                {row.iso45001}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {row.iso27001 && (
                              <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                                {row.iso27001}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
    </div>
  );
}
