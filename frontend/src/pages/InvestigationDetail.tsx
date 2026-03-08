import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate } from "react-router-dom";
import { trackError } from "../utils/errorTracker";
import {
  AlertTriangle,
  Car,
  MessageSquare,
  Loader2,
  RefreshCw,
  ArrowLeft,
  User,
  Calendar,
  FileText,
  ListTodo,
  History,
  Package,
  CheckCircle,
  CheckCircle2,
  XCircle,
  Download,
  FileQuestion,
  GitBranch,
  AlertCircle,
  Save,
} from "lucide-react";
import {
  investigationsApi,
  actionsApi,
  evidenceAssetsApi,
  checkPackCapability,
  type Investigation,
  type TimelineEvent,
  type InvestigationComment,
  type CustomerPackSummary,
  type ClosureValidation,
  type Action,
  type EvidenceAsset,
  type PackCapability,
  getApiErrorMessage,
} from "../api/client";
import { Button } from "../components/ui/Button";
import { Textarea } from "../components/ui/Textarea";
import { Card } from "../components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/Dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../components/ui/Tooltip";
import { cn } from "../helpers/utils";
import { getStatusDisplay } from "../utils/investigationStatusFilter";
import { CardSkeleton } from "../components/ui/SkeletonLoader";

import InvestigationHeader from "./investigation/InvestigationHeader";
import InvestigationTimeline from "./investigation/InvestigationTimeline";
import InvestigationComments from "./investigation/InvestigationComments";
import InvestigationActions from "./investigation/InvestigationActions";
import type { ActionFormData } from "./investigation/InvestigationActions";
import InvestigationEvidence from "./investigation/InvestigationEvidence";

const TABS = [
  { id: "summary", label: "Summary", icon: FileText },
  { id: "timeline", label: "Timeline", icon: History },
  { id: "evidence", label: "Evidence", icon: FileQuestion },
  { id: "rca", label: "RCA", icon: GitBranch },
  { id: "actions", label: "Actions", icon: ListTodo },
  { id: "report", label: "Report", icon: Package },
] as const;

type TabId = (typeof TABS)[number]["id"];

const ENTITY_ICONS: Record<string, typeof AlertTriangle> = {
  road_traffic_collision: Car,
  reporting_incident: AlertTriangle,
  complaint: MessageSquare,
};

export default function InvestigationDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const investigationId = parseInt(id || "0", 10);

  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("summary");

  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineFilter, setTimelineFilter] = useState<string>("all");

  const [comments, setComments] = useState<InvestigationComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [addingComment, setAddingComment] = useState(false);

  const [packs, setPacks] = useState<CustomerPackSummary[]>([]);
  const [packsLoading, setPacksLoading] = useState(false);
  const [generatingPack, setGeneratingPack] = useState(false);
  const [packCapability, setPackCapability] = useState<PackCapability>({ canGenerate: true });
  const [packError, setPackError] = useState<string | null>(null);

  const [evidenceAssets, setEvidenceAssets] = useState<EvidenceAsset[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [uploadingEvidence, setUploadingEvidence] = useState(false);
  const [deletingEvidenceId, setDeletingEvidenceId] = useState<number | null>(null);
  const [deleteEvidenceTarget, setDeleteEvidenceTarget] = useState<number | null>(null);

  const [rcaData, setRcaData] = useState<Record<string, string>>({});
  const [rcaUnsaved, setRcaUnsaved] = useState(false);
  const [savingRca, setSavingRca] = useState(false);
  const [rcaSaveError, setRcaSaveError] = useState<string | null>(null);
  const [rcaSaveSuccess, setRcaSaveSuccess] = useState(false);

  const [closureValidation, setClosureValidation] = useState<ClosureValidation | null>(null);
  const [closureLoading, setClosureLoading] = useState(false);

  const [actions, setActions] = useState<Action[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);
  const [actionStatusFilter, setActionStatusFilter] = useState<string>("all");

  // ── Loaders ──────────────────────────────────────────────

  const loadInvestigation = useCallback(async () => {
    if (!investigationId || investigationId === 0) {
      setError("Invalid investigation ID");
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const response = await investigationsApi.get(investigationId);
      setInvestigation(response.data);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "load" });
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const loadTimeline = useCallback(async () => {
    if (!investigationId) return;
    setTimelineLoading(true);
    try {
      const response = await investigationsApi.getTimeline(investigationId, {
        page: 1,
        page_size: 50,
        type: timelineFilter !== "all" ? timelineFilter : undefined,
      });
      setTimeline(response.data.items);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "loadTimeline" });
    } finally {
      setTimelineLoading(false);
    }
  }, [investigationId, timelineFilter]);

  const loadComments = useCallback(async () => {
    if (!investigationId) return;
    setCommentsLoading(true);
    try {
      const response = await investigationsApi.getComments(investigationId, { page: 1, page_size: 50 });
      setComments(response.data.items);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "loadComments" });
    } finally {
      setCommentsLoading(false);
    }
  }, [investigationId]);

  const loadPacks = useCallback(async () => {
    if (!investigationId) return;
    setPacksLoading(true);
    try {
      const response = await investigationsApi.getPacks(investigationId, { page: 1, page_size: 50 });
      setPacks(response.data.items);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "loadPacks" });
    } finally {
      setPacksLoading(false);
    }
  }, [investigationId]);

  const loadClosureValidation = useCallback(async () => {
    if (!investigationId) return;
    setClosureLoading(true);
    try {
      const response = await investigationsApi.getClosureValidation(investigationId);
      setClosureValidation(response.data);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "loadClosureValidation" });
    } finally {
      setClosureLoading(false);
    }
  }, [investigationId]);

  const loadActions = useCallback(async () => {
    if (!investigationId) return;
    setActionsLoading(true);
    try {
      const response = await actionsApi.list(
        1, 50,
        actionStatusFilter !== "all" ? actionStatusFilter : undefined,
        "investigation",
        investigationId,
      );
      setActions(response.data.items || []);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "loadActions" });
    } finally {
      setActionsLoading(false);
    }
  }, [investigationId, actionStatusFilter]);

  const loadEvidence = useCallback(async () => {
    if (!investigationId) return;
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      const response = await evidenceAssetsApi.list({
        source_module: "investigation",
        source_id: investigationId,
        page: 1,
        page_size: 50,
      });
      setEvidenceAssets(response.data.items);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "loadEvidence" });
      setEvidenceError(getApiErrorMessage(err));
    } finally {
      setEvidenceLoading(false);
    }
  }, [investigationId]);

  const loadPackCapability = useCallback(async () => {
    if (!investigationId) return;
    const capability = await checkPackCapability(investigationId);
    setPackCapability(capability);
  }, [investigationId]);

  const initializeRcaData = useCallback(() => {
    if (!investigation) return;
    const data = (investigation.data as Record<string, unknown>) || {};
    const rcaFields: Record<string, string> = {};
    for (let i = 1; i <= 5; i++) {
      rcaFields[`why_${i}`] = String(data[`why_${i}`] || "");
    }
    rcaFields["root_cause"] = String(data["root_cause"] || "");
    rcaFields["problem_statement"] = String(data["problem_statement"] || "");
    rcaFields["contributing_factors"] = String(data["contributing_factors"] || "");
    setRcaData(rcaFields);
    setRcaUnsaved(false);
  }, [investigation]);

  // ── Handlers ─────────────────────────────────────────────

  const handleUploadEvidence = async (file: File) => {
    if (!investigationId) return;
    setUploadingEvidence(true);
    setEvidenceError(null);
    try {
      await evidenceAssetsApi.upload(file, {
        source_module: "investigation",
        source_id: investigationId,
        title: file.name,
        visibility: "internal_customer",
      });
      await loadEvidence();
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "uploadEvidence" });
      setEvidenceError(getApiErrorMessage(err));
    } finally {
      setUploadingEvidence(false);
    }
  };

  const handleDeleteEvidence = async (assetId: number) => {
    setDeleteEvidenceTarget(assetId);
  };

  const confirmDeleteEvidence = async () => {
    const assetId = deleteEvidenceTarget;
    if (assetId === null) return;
    setDeleteEvidenceTarget(null);
    setDeletingEvidenceId(assetId);
    try {
      await evidenceAssetsApi.delete(assetId);
      await loadEvidence();
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "deleteEvidence" });
      setEvidenceError(getApiErrorMessage(err));
    } finally {
      setDeletingEvidenceId(null);
    }
  };

  const handleRcaFieldChange = (field: string, value: string) => {
    setRcaData((prev) => ({ ...prev, [field]: value }));
    setRcaUnsaved(true);
    setRcaSaveSuccess(false);
  };

  const handleSaveRca = async () => {
    if (!investigationId || !investigation) return;
    setSavingRca(true);
    setRcaSaveError(null);
    setRcaSaveSuccess(false);
    try {
      const existingData = (investigation.data as Record<string, unknown>) || {};
      await investigationsApi.update(investigationId, { data: { ...existingData, ...rcaData } });
      await loadInvestigation();
      setRcaUnsaved(false);
      setRcaSaveSuccess(true);
      setTimeout(() => setRcaSaveSuccess(false), 3000);
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "saveRCA" });
      setRcaSaveError(getApiErrorMessage(err));
    } finally {
      setSavingRca(false);
    }
  };

  const handleAddComment = async () => {
    if (!newComment.trim() || !investigationId) return;
    setAddingComment(true);
    try {
      await investigationsApi.addComment(investigationId, newComment.trim());
      setNewComment("");
      await loadComments();
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "addComment" });
    } finally {
      setAddingComment(false);
    }
  };

  const handleGeneratePack = async (audience: string) => {
    if (!investigationId) return;
    setGeneratingPack(true);
    setPackError(null);
    try {
      await investigationsApi.generatePack(investigationId, audience);
      await loadPacks();
    } catch (err: unknown) {
      trackError(err, { component: "InvestigationDetail", action: "generatePack" });
      const apiErr = err as { response?: { status?: number } };
      if (apiErr.response?.status === 404) {
        setPackError("Pack generation endpoint not available in this environment");
        setPackCapability({ canGenerate: false, reason: "Not available", lastError: "Endpoint returned 404" });
      } else if (apiErr.response?.status === 501) {
        setPackError("Pack generation is not implemented");
        setPackCapability({ canGenerate: false, reason: "Not implemented", lastError: "Endpoint returned 501" });
      } else if (apiErr.response?.status === 403) {
        setPackError("You do not have permission to generate packs");
      } else {
        setPackError(getApiErrorMessage(err));
      }
    } finally {
      setGeneratingPack(false);
    }
  };

  const handleCreateAction = async (form: ActionFormData) => {
    if (!investigationId) return;
    await actionsApi.create({
      title: form.title,
      description: form.description || "Action from investigation",
      priority: form.priority,
      due_date: form.due_date || undefined,
      action_type: "corrective",
      source_type: "investigation",
      source_id: investigationId,
      assigned_to_email: form.assigned_to || undefined,
    });
    await loadActions();
  };

  const handleUpdateActionStatus = async (
    actionId: number,
    newStatus: string,
    completionNotes?: string,
  ) => {
    try {
      await actionsApi.update(actionId, "investigation", {
        status: newStatus,
        completion_notes: newStatus === "completed" ? completionNotes : undefined,
      });
      await loadActions();
    } catch (err) {
      trackError(err, { component: "InvestigationDetail", action: "updateAction" });
    }
  };

  // ── Effects ──────────────────────────────────────────────

  useEffect(() => { loadInvestigation(); }, [loadInvestigation]);
  useEffect(() => { initializeRcaData(); }, [investigation, initializeRcaData]);

  useEffect(() => {
    if (!investigationId) return;
    switch (activeTab) {
      case "timeline": loadTimeline(); break;
      case "summary": loadComments(); loadClosureValidation(); break;
      case "actions": loadActions(); break;
      case "report": loadPacks(); loadPackCapability(); break;
      case "evidence": loadEvidence(); break;
      case "rca": initializeRcaData(); break;
    }
  }, [activeTab, investigationId, loadTimeline, loadComments, loadClosureValidation, loadActions, loadPacks, loadPackCapability, loadEvidence, initializeRcaData]);

  useEffect(() => { if (activeTab === "timeline") loadTimeline(); }, [timelineFilter, activeTab, loadTimeline]);
  useEffect(() => { if (activeTab === "actions") loadActions(); }, [actionStatusFilter, activeTab, loadActions]);

  // ── Render ───────────────────────────────────────────────

  if (loading) {
    return <div className="p-6"><CardSkeleton count={2} /></div>;
  }

  if (error || !investigation) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-16 h-16 text-destructive" />
        <h2 className="text-xl font-semibold text-foreground">{error || "Investigation not found"}</h2>
        <p className="text-muted-foreground">HTTP Status: {error?.includes("404") ? "404" : "Error"}</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/investigations")}>
            <ArrowLeft className="w-4 h-4 mr-2" />{t("investigations.back")}
          </Button>
          <Button onClick={loadInvestigation}>
            <RefreshCw className="w-4 h-4 mr-2" />{t("retry")}
          </Button>
        </div>
      </div>
    );
  }

  const EntityIcon = ENTITY_ICONS[investigation.assigned_entity_type] || AlertTriangle;
  const statusDisplay = getStatusDisplay(investigation.status);

  return (
    <div className="space-y-6 animate-fade-in">
      <InvestigationHeader
        investigation={investigation}
        statusDisplay={statusDisplay}
        EntityIcon={EntityIcon}
      />

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="flex gap-1 overflow-x-auto pb-px">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors",
                "border-b-2 -mb-px",
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeTab === "summary" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">{t("common.description")}</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">
                  {investigation.description || "No description provided."}
                </p>
              </Card>
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">{t("investigations.findings_conclusion")}</h3>
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-1">Findings</h4>
                    <p className="text-foreground">
                      {String((investigation.data as Record<string, unknown>)?.["findings"] || "") || "Not yet documented."}
                    </p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-1">Conclusion</h4>
                    <p className="text-foreground">
                      {String((investigation.data as Record<string, unknown>)?.["conclusion"] || "") || "Not yet documented."}
                    </p>
                  </div>
                </div>
              </Card>
              <InvestigationComments
                comments={comments}
                commentsLoading={commentsLoading}
                newComment={newComment}
                onNewCommentChange={setNewComment}
                addingComment={addingComment}
                onAddComment={handleAddComment}
              />
            </div>
            <div className="space-y-6">
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">{t("common.details")}</h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <User className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">{t("investigations.lead_investigator")}</p>
                      <p className="text-sm text-foreground">
                        {String((investigation.data as Record<string, unknown>)?.["lead_investigator"] || "") || "Not assigned"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Calendar className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Started</p>
                      <p className="text-sm text-foreground">
                        {investigation.started_at ? new Date(investigation.started_at).toLocaleDateString() : "Not started"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Completed</p>
                      <p className="text-sm text-foreground">
                        {investigation.completed_at ? new Date(investigation.completed_at).toLocaleDateString() : "In progress"}
                      </p>
                    </div>
                  </div>
                </div>
              </Card>
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">{t("investigations.closure_checklist")}</h3>
                {closureLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                  </div>
                ) : closureValidation ? (
                  <div className="space-y-3">
                    <div className={cn("flex items-center gap-2 p-3 rounded-lg", closureValidation.status === "OK" ? "bg-success/10 text-success" : "bg-warning/10 text-warning")}>
                      {closureValidation.status === "OK" ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                      <span className="font-medium">{closureValidation.status === "OK" ? "Ready for Closure" : "Cannot Close Yet"}</span>
                    </div>
                    {closureValidation.reason_codes.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">Issues:</p>
                        {closureValidation.reason_codes.map((code, i) => (
                          <p key={i} className="text-xs text-destructive">• {code.replace(/_/g, " ")}</p>
                        ))}
                      </div>
                    )}
                    {closureValidation.missing_fields.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">Missing Fields:</p>
                        {closureValidation.missing_fields.map((field, i) => (
                          <p key={i} className="text-xs text-muted-foreground">• {field}</p>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">Unable to load closure validation.</p>
                )}
              </Card>
            </div>
          </div>
        )}

        {activeTab === "timeline" && (
          <InvestigationTimeline
            timeline={timeline}
            timelineLoading={timelineLoading}
            timelineFilter={timelineFilter}
            onTimelineFilterChange={setTimelineFilter}
            onRefresh={loadTimeline}
          />
        )}

        {activeTab === "evidence" && (
          <InvestigationEvidence
            evidenceAssets={evidenceAssets}
            evidenceLoading={evidenceLoading}
            evidenceError={evidenceError}
            uploadingEvidence={uploadingEvidence}
            deletingEvidenceId={deletingEvidenceId}
            onUploadEvidence={handleUploadEvidence}
            onDeleteEvidence={handleDeleteEvidence}
            onRefresh={loadEvidence}
            onSetEvidenceError={setEvidenceError}
          />
        )}

        {activeTab === "rca" && (
          <div className="space-y-6">
            {rcaUnsaved && (
              <Card className="p-4 bg-warning/10 border-warning/30">
                <div className="flex items-center gap-2 text-warning">
                  <AlertCircle className="w-5 h-5" />
                  <span className="font-medium">You have unsaved changes</span>
                </div>
              </Card>
            )}
            {rcaSaveSuccess && (
              <Card className="p-4 bg-success/10 border-success/30">
                <div className="flex items-center gap-2 text-success">
                  <CheckCircle2 className="w-5 h-5" />
                  <span className="font-medium">RCA saved successfully</span>
                </div>
              </Card>
            )}
            {rcaSaveError && (
              <Card className="p-4 bg-destructive/10 border-destructive/30">
                <div className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="w-5 h-5" />
                  <span className="font-medium">Error saving RCA:</span>
                  <span>{rcaSaveError}</span>
                </div>
              </Card>
            )}
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">{t("investigations.problem_statement")}</h3>
              <Textarea
                rows={3}
                placeholder="Describe the problem or incident being investigated..."
                value={rcaData["problem_statement"] || ""}
                onChange={(e) => handleRcaFieldChange("problem_statement", e.target.value)}
              />
            </Card>
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-primary" />{t("investigations.five_whys")}
              </h3>
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={num} className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0 font-bold text-primary-foreground">
                      {num}
                    </div>
                    <div className="flex-1">
                      <label htmlFor={`rca-why-${num}`} className="block text-sm font-medium text-foreground mb-2">
                        Why {num}?
                      </label>
                      <Textarea
                        id={`rca-why-${num}`}
                        rows={2}
                        placeholder={`Enter the ${num === 1 ? "initial" : "deeper"} cause...`}
                        value={rcaData[`why_${num}`] || ""}
                        onChange={(e) => handleRcaFieldChange(`why_${num}`, e.target.value)}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
            <Card className="p-6 border-primary/20 bg-primary/5">
              <h3 className="text-lg font-semibold text-foreground mb-4">{t("investigations.root_cause")}</h3>
              <Textarea
                rows={3}
                placeholder="Document the root cause based on your 5 Whys analysis..."
                value={rcaData["root_cause"] || ""}
                onChange={(e) => handleRcaFieldChange("root_cause", e.target.value)}
              />
            </Card>
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">{t("investigations.contributing_factors")}</h3>
              <Textarea
                rows={3}
                placeholder="List any contributing factors that led to the issue..."
                value={rcaData["contributing_factors"] || ""}
                onChange={(e) => handleRcaFieldChange("contributing_factors", e.target.value)}
              />
            </Card>
            <div className="flex items-center justify-between">
              <div>{rcaUnsaved && <span className="text-sm text-muted-foreground">Changes not saved</span>}</div>
              <Button onClick={handleSaveRca} disabled={savingRca || !rcaUnsaved} className={cn(!rcaUnsaved && "opacity-50")}>
                {savingRca ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</>) : (<><Save className="w-4 h-4 mr-2" />{t("investigations.save_rca")}</>)}
              </Button>
            </div>
          </div>
        )}

        {activeTab === "actions" && (
          <InvestigationActions
            actions={actions}
            actionsLoading={actionsLoading}
            actionStatusFilter={actionStatusFilter}
            onActionStatusFilterChange={setActionStatusFilter}
            onCreateAction={handleCreateAction}
            onUpdateActionStatus={handleUpdateActionStatus}
          />
        )}

        {activeTab === "report" && (
          <div className="space-y-6">
            {packError && (
              <Card className="p-4 bg-destructive/10 border-destructive/30">
                <div className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="w-5 h-5" />
                  <span className="font-medium">Error:</span>
                  <span>{packError}</span>
                </div>
              </Card>
            )}
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">{t("investigations.generate_report")}</h3>
              {!packCapability.canGenerate && (
                <div className="mb-4 p-3 bg-warning/10 border border-warning/30 rounded-lg">
                  <div className="flex items-center gap-2 text-warning">
                    <AlertCircle className="w-5 h-5" />
                    <span className="font-medium">Report generation not available</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {packCapability.reason || "Pack generation is not available in this environment."}
                  </p>
                </div>
              )}
              <div className="flex items-center gap-4">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Button onClick={() => handleGeneratePack("internal_customer")} disabled={generatingPack || !packCapability.canGenerate}>
                          {generatingPack ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                          Internal Report
                        </Button>
                      </span>
                    </TooltipTrigger>
                    {!packCapability.canGenerate && <TooltipContent>{packCapability.reason || "Not available"}</TooltipContent>}
                  </Tooltip>
                </TooltipProvider>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Button variant="outline" onClick={() => handleGeneratePack("external_customer")} disabled={generatingPack || !packCapability.canGenerate}>
                          {generatingPack ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                          External Report
                        </Button>
                      </span>
                    </TooltipTrigger>
                    {!packCapability.canGenerate && <TooltipContent>{packCapability.reason || "Not available"}</TooltipContent>}
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                Generate customer-facing reports for internal review or external distribution. Reports include a secure checksum for verification.
              </p>
            </Card>
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-foreground">{t("investigations.report_history")}</h3>
                <Button variant="outline" size="sm" onClick={loadPacks} disabled={packsLoading}>
                  <RefreshCw className={cn("w-4 h-4", packsLoading && "animate-spin")} />
                </Button>
              </div>
              {packsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : packs.length === 0 ? (
                <div className="text-center py-8">
                  <Package className="w-12 h-12 mx-auto mb-3 text-muted-foreground/50" />
                  <p className="text-muted-foreground">No reports generated yet.</p>
                  {packCapability.canGenerate && <p className="text-sm text-muted-foreground mt-1">Use the buttons above to generate a report.</p>}
                </div>
              ) : (
                <div className="space-y-3">
                  {packs.map((pack) => (
                    <div key={pack.id} className="flex items-center justify-between p-4 bg-surface rounded-lg border border-border">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <Package className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground capitalize">{pack.audience.replace(/_/g, " ")} Report</p>
                          <p className="text-xs text-muted-foreground">Generated: {new Date(pack.created_at).toLocaleString()}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p className="text-xs font-mono text-muted-foreground">UUID: {pack.pack_uuid.slice(0, 8)}...</p>
                          {pack.checksum_sha256 && <p className="text-xs font-mono text-muted-foreground">SHA256: {pack.checksum_sha256.slice(0, 12)}...</p>}
                        </div>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="outline" size="sm"><Download className="w-4 h-4" /></Button>
                            </TooltipTrigger>
                            <TooltipContent>Download Report</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}
      </div>

      <Dialog open={deleteEvidenceTarget !== null} onOpenChange={() => setDeleteEvidenceTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Evidence</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this evidence? This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteEvidenceTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDeleteEvidence}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
