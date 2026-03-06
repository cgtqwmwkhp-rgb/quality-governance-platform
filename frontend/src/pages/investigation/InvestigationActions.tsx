import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Loader2, ListTodo } from "lucide-react";
import { type Action, getApiErrorMessage } from "../../api/client";
import { trackError } from "../../utils/errorTracker";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Textarea } from "../../components/ui/Textarea";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/Select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "../../components/ui/Dialog";
import { cn } from "../../helpers/utils";
import { UserEmailSearch } from "../../components/UserEmailSearch";

const ACTION_STATUS_OPTIONS = [
  { value: "open", label: "Open", className: "bg-warning/10 text-warning" },
  {
    value: "in_progress",
    label: "In Progress",
    className: "bg-info/10 text-info",
  },
  {
    value: "pending_verification",
    label: "Pending Verification",
    className: "bg-purple-100 text-purple-800",
  },
  {
    value: "completed",
    label: "Completed",
    className: "bg-success/10 text-success",
  },
  {
    value: "cancelled",
    label: "Cancelled",
    className: "bg-muted text-muted-foreground",
  },
];

export interface ActionFormData {
  title: string;
  description: string;
  priority: string;
  due_date: string;
  assigned_to: string;
}

interface InvestigationActionsProps {
  actions: Action[];
  actionsLoading: boolean;
  actionStatusFilter: string;
  onActionStatusFilterChange: (value: string) => void;
  onCreateAction: (form: ActionFormData) => Promise<void>;
  onUpdateActionStatus: (
    actionId: number,
    newStatus: string,
    completionNotes?: string,
  ) => void;
}

const INITIAL_FORM: ActionFormData = {
  title: "",
  description: "",
  priority: "medium",
  due_date: "",
  assigned_to: "",
};

export default function InvestigationActions({
  actions,
  actionsLoading,
  actionStatusFilter,
  onActionStatusFilterChange,
  onCreateAction,
  onUpdateActionStatus,
}: InvestigationActionsProps) {
  const { t } = useTranslation();

  const [showActionModal, setShowActionModal] = useState(false);
  const [creatingAction, setCreatingAction] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionForm, setActionForm] = useState<ActionFormData>(INITIAL_FORM);

  const [showCompletionDialog, setShowCompletionDialog] = useState(false);
  const [completionNotes, setCompletionNotes] = useState("");
  const [completionActionId, setCompletionActionId] = useState<number | null>(
    null,
  );

  const handleCreateAction = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingAction(true);
    setActionError(null);
    try {
      await onCreateAction(actionForm);
      setShowActionModal(false);
      setActionForm(INITIAL_FORM);
    } catch (err) {
      trackError(err, {
        component: "InvestigationActions",
        action: "createAction",
      });
      setActionError(getApiErrorMessage(err));
    } finally {
      setCreatingAction(false);
    }
  };

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Select
              value={actionStatusFilter}
              onValueChange={onActionStatusFilterChange}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                {ACTION_STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => setShowActionModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            {t("investigations.add_action")}
          </Button>
        </div>

        {actionsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : actions.length === 0 ? (
          <Card className="p-12 text-center">
            <ListTodo className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">
              No Actions
            </h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Corrective actions for this investigation will appear here.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {actions.map((action) => (
              <Card key={action.id} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-foreground">
                        {action.title}
                      </h4>
                      <Badge
                        className={
                          ACTION_STATUS_OPTIONS.find(
                            (o) => o.value === action.status,
                          )?.className
                        }
                      >
                        {action.status.replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {action.description}
                    </p>
                    {action.owner_email && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Assigned to: {action.owner_email}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Badge
                      variant="outline"
                      className={cn(
                        action.priority === "critical" &&
                          "border-destructive text-destructive",
                        action.priority === "high" &&
                          "border-warning text-warning",
                        action.priority === "medium" &&
                          "border-info text-info",
                      )}
                    >
                      {action.priority}
                    </Badge>
                    {action.due_date && (
                      <span className="text-xs text-muted-foreground">
                        Due:{" "}
                        {new Date(action.due_date).toLocaleDateString()}
                      </span>
                    )}
                    <Select
                      value={action.status}
                      onValueChange={(newStatus) => {
                        if (newStatus === "completed") {
                          setCompletionActionId(action.id);
                          setCompletionNotes("");
                          setShowCompletionDialog(true);
                        } else {
                          onUpdateActionStatus(action.id, newStatus);
                        }
                      }}
                    >
                      <SelectTrigger className="w-36 h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ACTION_STATUS_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Add Action Modal */}
      <Dialog open={showActionModal} onOpenChange={setShowActionModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Corrective Action</DialogTitle>
            <DialogDescription>
              Create a corrective action for this investigation
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            <div>
              <label
                htmlFor="action-title"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Action Title *
              </label>
              <Input
                id="action-title"
                value={actionForm.title}
                onChange={(e) =>
                  setActionForm({ ...actionForm, title: e.target.value })
                }
                placeholder="e.g., Implement additional safety controls"
                required
              />
            </div>
            <UserEmailSearch
              label="Assign To"
              value={actionForm.assigned_to}
              onChange={(email) =>
                setActionForm({ ...actionForm, assigned_to: email })
              }
              placeholder="Search by email..."
            />
            <div>
              <span className="block text-sm font-medium text-foreground mb-1">
                Priority
              </span>
              <Select
                value={actionForm.priority}
                onValueChange={(value) =>
                  setActionForm({ ...actionForm, priority: value })
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
              <label
                htmlFor="action-due-date"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Due Date
              </label>
              <Input
                id="action-due-date"
                type="date"
                value={actionForm.due_date}
                onChange={(e) =>
                  setActionForm({ ...actionForm, due_date: e.target.value })
                }
              />
            </div>
            <div>
              <label
                htmlFor="action-description"
                className="block text-sm font-medium text-foreground mb-1"
              >
                Description
              </label>
              <Textarea
                id="action-description"
                value={actionForm.description}
                onChange={(e) =>
                  setActionForm({ ...actionForm, description: e.target.value })
                }
                placeholder="Describe the corrective action to be taken..."
                rows={3}
              />
            </div>
            {actionError && (
              <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-md text-sm text-destructive">
                <strong>Error:</strong> {actionError}
              </div>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowActionModal(false);
                  setActionError(null);
                }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={creatingAction || !actionForm.title}
              >
                {creatingAction ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  "Create Action"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Completion Notes Dialog */}
      <Dialog
        open={showCompletionDialog}
        onOpenChange={setShowCompletionDialog}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete Action</DialogTitle>
            <DialogDescription>
              Enter completion notes (optional) before marking this action as
              completed.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={completionNotes}
            onChange={(e) => setCompletionNotes(e.target.value)}
            placeholder="Enter completion notes..."
            rows={3}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCompletionDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (completionActionId !== null) {
                  onUpdateActionStatus(
                    completionActionId,
                    "completed",
                    completionNotes || undefined,
                  );
                }
                setShowCompletionDialog(false);
              }}
            >
              Complete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
