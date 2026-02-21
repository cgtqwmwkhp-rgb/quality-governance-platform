import { useState } from "react";
import {
  Search,
  ListTodo,
  Plus,
  Calendar,
  User,
  Flag,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowUpRight,
  Filter,
  Loader2,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { Card, CardContent } from "../components/ui/Card";
import { Badge, type BadgeVariant } from "../components/ui/Badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/Dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/Select";
import { cn } from "../helpers/utils";
import { LoadingSkeleton } from "../components/ui/LoadingSkeleton";
import { ErrorState } from "../components/ui/ErrorState";
import type { Action as ApiAction, ActionCreate } from "../api/client";
import { useActions, useCreateAction } from "../hooks/queries/useActions";

// Bounded error taxonomy for deterministic error handling
type ErrorClass =
  | "VALIDATION_ERROR"
  | "AUTH_ERROR"
  | "NOT_FOUND"
  | "NETWORK_ERROR"
  | "SERVER_ERROR"
  | "UNKNOWN";

interface ApiError {
  error_class: ErrorClass;
  message: string;
}

function classifyError(error: unknown): ApiError {
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    if (message.includes("401") || message.includes("unauthorized")) {
      return {
        error_class: "AUTH_ERROR",
        message: "Authentication required. Please log in.",
      };
    }
    if (message.includes("404") || message.includes("not found")) {
      return { error_class: "NOT_FOUND", message: "Action not found." };
    }
    if (message.includes("400") || message.includes("validation")) {
      return {
        error_class: "VALIDATION_ERROR",
        message: "Invalid data provided.",
      };
    }
    if (message.includes("network") || message.includes("fetch")) {
      return {
        error_class: "NETWORK_ERROR",
        message: "Network error. Please check your connection.",
      };
    }
    if (message.includes("500") || message.includes("server")) {
      return {
        error_class: "SERVER_ERROR",
        message: "Server error. Please try again later.",
      };
    }
  }
  return { error_class: "UNKNOWN", message: "An unexpected error occurred." };
}

// Local UI type extending API type with computed fields
interface Action extends Omit<
  ApiAction,
  "source_id" | "owner_id" | "owner_email"
> {
  source_ref: string;
  owner?: string;
}

type ViewMode = "all" | "my" | "overdue";
type FilterStatus =
  | "all"
  | "open"
  | "in_progress"
  | "pending_verification"
  | "completed";

// Form state type for creating actions
interface CreateActionForm {
  title: string;
  description: string;
  priority: string;
  action_type: string;
  due_date: string;
  source_type: string;
  source_id: string;
}

const INITIAL_FORM: CreateActionForm = {
  title: "",
  description: "",
  priority: "medium",
  action_type: "corrective",
  due_date: "",
  source_type: "incident",
  source_id: "",
};

export default function Actions() {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [showModal, setShowModal] = useState(false);

  const statusFilter = filterStatus !== "all" ? filterStatus : undefined;
  const {
    data: actionsData,
    isLoading,
    isError,
    error: queryError,
    refetch,
  } = useActions({ page: 1, size: 100, status: statusFilter });
  const createAction = useCreateAction();

  const transformAction = (apiAction: ApiAction): Action => ({
    ...apiAction,
    source_ref: `${apiAction.source_type.toUpperCase()}-${apiAction.source_id}`,
    owner: apiAction.owner_email || undefined,
  });

  const actions = (actionsData?.items ?? []).map(transformAction);

  const [formData, setFormData] = useState<CreateActionForm>(INITIAL_FORM);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    try {
      const payload: ActionCreate = {
        title: formData.title,
        description: formData.description,
        action_type: formData.action_type,
        priority: formData.priority,
        source_type: formData.source_type,
        source_id: parseInt(formData.source_id, 10),
        due_date: formData.due_date || undefined,
      };

      await createAction.mutateAsync(payload);
      setSubmitSuccess(true);

      // STATIC_UI_CONFIG_OK - UX delay to show success state before closing modal
      setTimeout(() => {
        setShowModal(false);
        setFormData(INITIAL_FORM);
        setSubmitSuccess(false);
      }, 1500);
    } catch (err) {
      console.error("Failed to create action:", err);
      setSubmitError(classifyError(err));
    }
  };

  const getPriorityVariant = (priority: string) => {
    switch (priority) {
      case "critical":
        return "critical";
      case "high":
        return "high";
      case "medium":
        return "medium";
      case "low":
        return "low";
      default:
        return "secondary";
    }
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "completed":
        return "resolved";
      case "open":
        return "submitted";
      case "in_progress":
        return "in-progress";
      case "pending_verification":
        return "acknowledged";
      case "cancelled":
        return "closed";
      default:
        return "secondary";
    }
  };

  const getSourceIcon = (type: string) => {
    switch (type) {
      case "incident":
        return "🔥";
      case "audit":
        return "📋";
      case "rta":
        return "🚗";
      case "complaint":
        return "💬";
      case "risk":
        return "⚠️";
      default:
        return "📌";
    }
  };

  const isOverdue = (dueDate?: string, status?: string) => {
    if (!dueDate || status === "completed" || status === "cancelled")
      return false;
    return new Date(dueDate) < new Date();
  };

  const filteredActions = actions.filter((action) => {
    if (
      searchTerm &&
      !action.title.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !action.reference_number?.toLowerCase().includes(searchTerm.toLowerCase())
    ) {
      return false;
    }
    if (filterStatus !== "all" && action.status !== filterStatus) {
      return false;
    }
    if (viewMode === "overdue" && !isOverdue(action.due_date, action.status)) {
      return false;
    }
    return true;
  });

  const stats = {
    total: actions.length,
    open: actions.filter((a) => a.status === "open").length,
    inProgress: actions.filter((a) => a.status === "in_progress").length,
    overdue: actions.filter((a) => isOverdue(a.due_date, a.status)).length,
    completed: actions.filter((a) => a.status === "completed").length,
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <LoadingSkeleton variant="table" rows={5} columns={5} />
      </div>
    );
  }

  if (isError) {
    const apiError = queryError ? classifyError(queryError) : null;
    return (
      <div className="p-6">
        <ErrorState
          title={apiError?.error_class ?? "Failed to load actions"}
          message={
            apiError?.message ?? "Could not fetch actions. Please try again."
          }
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Action Center</h1>
          <p className="text-muted-foreground mt-1">
            Cross-module corrective & preventive actions
          </p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Action
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          {
            label: "Total Actions",
            value: stats.total,
            icon: ListTodo,
            variant: "primary" as const,
          },
          {
            label: "Open",
            value: stats.open,
            icon: AlertCircle,
            variant: "info" as const,
          },
          {
            label: "In Progress",
            value: stats.inProgress,
            icon: Clock,
            variant: "warning" as const,
          },
          {
            label: "Overdue",
            value: stats.overdue,
            icon: Flag,
            variant: "destructive" as const,
          },
          {
            label: "Completed",
            value: stats.completed,
            icon: CheckCircle2,
            variant: "success" as const,
          },
        ].map((stat) => (
          <Card
            key={stat.label}
            hoverable
            className={cn(
              "p-5",
              stat.label === "Overdue" &&
                stats.overdue > 0 &&
                "border-destructive/30",
            )}
          >
            <div
              className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center mb-3",
                stat.variant === "primary" && "bg-primary/10 text-primary",
                stat.variant === "info" && "bg-info/10 text-info",
                stat.variant === "warning" && "bg-warning/10 text-warning",
                stat.variant === "destructive" &&
                  "bg-destructive/10 text-destructive",
                stat.variant === "success" && "bg-success/10 text-success",
              )}
            >
              <stat.icon className="w-5 h-5" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
            {stat.label === "Overdue" && stats.overdue > 0 && (
              <div className="absolute top-3 right-3 w-3 h-3 bg-destructive rounded-full animate-pulse" />
            )}
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search actions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        <div className="flex bg-surface rounded-xl p-1 border border-border">
          {(["all", "my", "overdue"] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                viewMode === mode
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {mode === "my"
                ? "My Actions"
                : mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>

        <Select
          value={filterStatus}
          onValueChange={(value) => setFilterStatus(value as FilterStatus)}
        >
          <SelectTrigger className="w-[180px]">
            <Filter className="w-4 h-4 mr-2" />
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="pending_verification">
              Pending Verification
            </SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Actions List */}
      <div className="space-y-4">
        {filteredActions.length === 0 ? (
          <Card className="p-12 text-center">
            <ListTodo className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">
              No Actions Found
            </h3>
            <p className="text-muted-foreground">
              {filterStatus !== "all" || viewMode !== "all"
                ? "Try adjusting your filters"
                : "Actions from incidents, audits, and investigations will appear here"}
            </p>
          </Card>
        ) : (
          filteredActions.map((action) => {
            const overdue = isOverdue(action.due_date, action.status);

            return (
              <Card
                key={action.id}
                hoverable
                className={cn(
                  "overflow-hidden",
                  overdue && "border-destructive/30",
                )}
              >
                <div className="flex items-stretch">
                  <div
                    className={cn(
                      "w-1.5",
                      action.priority === "critical" && "bg-destructive",
                      action.priority === "high" && "bg-warning",
                      action.priority === "medium" && "bg-warning/70",
                      action.priority === "low" && "bg-success",
                    )}
                  />

                  <CardContent className="flex-1 p-5">
                    <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                          <span className="font-mono text-sm text-primary">
                            {action.reference_number || `ACT-${action.id}`}
                          </span>
                          <Badge
                            variant={
                              getPriorityVariant(
                                action.priority,
                              ) as BadgeVariant
                            }
                          >
                            {action.priority}
                          </Badge>
                          <Badge
                            variant={
                              getStatusVariant(action.status) as BadgeVariant
                            }
                          >
                            {action.status.replace("_", " ")}
                          </Badge>
                          {overdue && (
                            <Badge
                              variant="destructive"
                              className="animate-pulse"
                            >
                              OVERDUE
                            </Badge>
                          )}
                        </div>
                        <h3 className="text-lg font-semibold text-foreground mb-1">
                          {action.title}
                        </h3>
                        <p className="text-sm text-muted-foreground line-clamp-1">
                          {action.description}
                        </p>
                      </div>

                      <div className="flex flex-wrap lg:flex-col items-start lg:items-end gap-2 lg:gap-1 lg:w-48 flex-shrink-0">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface rounded-lg">
                          <span className="text-lg">
                            {getSourceIcon(action.source_type)}
                          </span>
                          <span className="text-xs font-mono text-muted-foreground">
                            {action.source_ref}
                          </span>
                          <ArrowUpRight className="w-3 h-3 text-muted-foreground" />
                        </div>

                        {action.due_date && (
                          <div
                            className={cn(
                              "flex items-center gap-2 text-sm",
                              overdue
                                ? "text-destructive"
                                : "text-muted-foreground",
                            )}
                          >
                            <Calendar className="w-4 h-4" />
                            <span>
                              Due{" "}
                              {new Date(action.due_date).toLocaleDateString()}
                            </span>
                          </div>
                        )}

                        {action.owner && (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <User className="w-4 h-4" />
                            <span>{action.owner}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </div>
              </Card>
            );
          })
        )}
      </div>

      {/* Create Modal */}
      <Dialog
        open={showModal}
        onOpenChange={(open) => {
          setShowModal(open);
          if (!open) {
            setFormData(INITIAL_FORM);
            setSubmitError(null);
            setSubmitSuccess(false);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Action</DialogTitle>
          </DialogHeader>

          {submitSuccess ? (
            <div className="py-8 text-center">
              <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-success" />
              </div>
              <p className="text-lg font-semibold text-foreground mb-2">
                Action Created!
              </p>
              <p className="text-muted-foreground">
                The action has been added to the list.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Title <span className="text-destructive">*</span>
                </label>
                <Input
                  placeholder="Action title..."
                  value={formData.title}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, title: e.target.value }))
                  }
                  required
                  maxLength={300}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Description <span className="text-destructive">*</span>
                </label>
                <Textarea
                  rows={3}
                  placeholder="Describe the action required..."
                  value={formData.description}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Source Type
                  </label>
                  <Select
                    value={formData.source_type}
                    onValueChange={(value) =>
                      setFormData((prev) => ({ ...prev, source_type: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select source" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="incident">Incident</SelectItem>
                      <SelectItem value="rta">RTA</SelectItem>
                      <SelectItem value="complaint">Complaint</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Source ID <span className="text-destructive">*</span>
                  </label>
                  <Input
                    type="number"
                    placeholder="e.g., 42"
                    value={formData.source_id}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        source_id: e.target.value,
                      }))
                    }
                    required
                    min={1}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Priority
                  </label>
                  <Select
                    value={formData.priority}
                    onValueChange={(value) =>
                      setFormData((prev) => ({ ...prev, priority: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select priority" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Due Date
                  </label>
                  <Input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        due_date: e.target.value,
                      }))
                    }
                    min={new Date().toISOString().split("T")[0]}
                  />
                </div>
              </div>

              {/* Error Message */}
              {submitError && (
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-destructive">
                      {submitError.error_class}
                    </p>
                    <p className="text-sm text-destructive/80">
                      {submitError.message}
                    </p>
                  </div>
                </div>
              )}

              <DialogFooter className="gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowModal(false)}
                  disabled={createAction.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createAction.isPending}>
                  {createAction.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Create Action"
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
