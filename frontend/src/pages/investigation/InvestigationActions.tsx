import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Loader2, ListTodo } from 'lucide-react'
import { type Action, getApiErrorMessage } from '../../api/client'
import { trackError } from '../../utils/errorTracker'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../../components/ui/Dialog'
import { cn } from '../../helpers/utils'
import { EngineerPeoplePicker } from '../../components/EngineerPeoplePicker'

const ACTION_STATUS_OPTIONS = [
  { value: 'open', label: 'Open', className: 'bg-warning/10 text-warning' },
  {
    value: 'in_progress',
    label: 'In Progress',
    className: 'bg-info/10 text-info',
  },
  {
    value: 'pending_verification',
    label: 'Pending Verification',
    className: 'bg-purple-100 text-purple-800',
  },
  {
    value: 'completed',
    label: 'Completed',
    className: 'bg-success/10 text-success',
  },
  {
    value: 'cancelled',
    label: 'Cancelled',
    className: 'bg-muted text-muted-foreground',
  },
]

export interface ActionFormData {
  title: string
  description: string
  priority: string
  due_date: string
  assigned_to: string
}

interface InvestigationActionsProps {
  actions: Action[]
  actionsLoading: boolean
  actionStatusFilter: string
  onActionStatusFilterChange: (value: string) => void
  onCreateAction: (form: ActionFormData) => Promise<void>
  onUpdateActionStatus: (action: Action, newStatus: string, completionNotes?: string) => void
  /** Increment to open the create dialog (handoff CTA → Actions tab). */
  openCreateToken?: number
  /** Prefill create dialog (e.g. RCA → Create CAPA from root cause). */
  createPrefill?: Partial<ActionFormData> | null
  /** Highlight / scroll to a blocking CAPA by action_key. */
  focusActionKey?: string | null
  /** Investigation reference shown as locked parent in the create dialog. */
  parentLabel?: string
}

/** Prefer normalized display_status (CAPA closed → completed) for honest status UI. */
function actionStatusKey(action: Action): string {
  return (action.display_status || action.status || 'open').toLowerCase()
}

const INITIAL_FORM: ActionFormData = {
  title: '',
  description: '',
  priority: 'medium',
  due_date: '',
  assigned_to: '',
}

export default function InvestigationActions({
  actions,
  actionsLoading,
  actionStatusFilter,
  onActionStatusFilterChange,
  onCreateAction,
  onUpdateActionStatus,
  openCreateToken = 0,
  createPrefill = null,
  focusActionKey = null,
  parentLabel,
}: InvestigationActionsProps) {
  const { t } = useTranslation()

  const [showActionModal, setShowActionModal] = useState(false)
  const [creatingAction, setCreatingAction] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionForm, setActionForm] = useState<ActionFormData>(INITIAL_FORM)

  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completionNotes, setCompletionNotes] = useState('')
  const [completionAction, setCompletionAction] = useState<Action | null>(null)

  useEffect(() => {
    if (openCreateToken > 0) {
      setShowActionModal(true)
      setActionError(null)
      if (createPrefill) {
        setActionForm((prev) => ({ ...prev, ...INITIAL_FORM, ...createPrefill }))
      }
    }
  }, [openCreateToken, createPrefill])

  useEffect(() => {
    if (!focusActionKey) return
    const el = document.querySelector(`[data-action-key="${CSS.escape(focusActionKey)}"]`)
    if (el instanceof HTMLElement) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.focus({ preventScroll: true })
    }
  }, [focusActionKey, actions])

  const handleCreateAction = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreatingAction(true)
    setActionError(null)
    try {
      await onCreateAction(actionForm)
      setShowActionModal(false)
      setActionForm(INITIAL_FORM)
    } catch (err) {
      trackError(err, {
        component: 'InvestigationActions',
        action: 'createAction',
      })
      setActionError(getApiErrorMessage(err))
    } finally {
      setCreatingAction(false)
    }
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Select value={actionStatusFilter} onValueChange={onActionStatusFilterChange}>
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
            {t('investigations.add_action')}
          </Button>
        </div>

        {actionsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : actions.length === 0 ? (
          <Card className="p-12 text-center">
            <ListTodo className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">No Actions</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Corrective actions for this investigation will appear here.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {actions.map((action) => {
              const statusKey = actionStatusKey(action)
              const isFocused = Boolean(focusActionKey && action.action_key === focusActionKey)
              return (
              <Card
                key={action.action_key || action.id}
                tabIndex={-1}
                data-action-key={action.action_key || undefined}
                className={cn(
                  'p-4 outline-none',
                  isFocused && 'ring-2 ring-primary border-primary/40',
                )}
                data-testid={`investigation-action-${action.action_key || action.id}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-foreground">{action.title}</h4>
                      <Badge
                        className={
                          ACTION_STATUS_OPTIONS.find((o) => o.value === statusKey)?.className
                        }
                        data-testid={`investigation-action-status-${action.action_key || action.id}`}
                      >
                        {statusKey.replace(/_/g, ' ')}
                      </Badge>
                      {action.action_key ? (
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {action.action_key}
                        </span>
                      ) : null}
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
                        action.priority === 'critical' && 'border-destructive text-destructive',
                        action.priority === 'high' && 'border-warning text-warning',
                        action.priority === 'medium' && 'border-info text-info',
                      )}
                    >
                      {action.priority}
                    </Badge>
                    {action.due_date && (
                      <span className="text-xs text-muted-foreground">
                        Due: {new Date(action.due_date).toLocaleDateString()}
                      </span>
                    )}
                    <Select
                      value={statusKey}
                      onValueChange={(newStatus) => {
                        if (newStatus === 'completed') {
                          setCompletionAction(action)
                          setCompletionNotes('')
                          setShowCompletionDialog(true)
                        } else {
                          onUpdateActionStatus(action, newStatus)
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
              )
            })}
          </div>
        )}
      </div>

      {/* Add Action Modal */}
      <Dialog open={showActionModal} onOpenChange={setShowActionModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Corrective Action</DialogTitle>
            <DialogDescription>
              Create a CAPA linked to this investigation. The parent is set automatically.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateAction} className="space-y-4">
            {parentLabel && (
              <div
                className="rounded-lg border border-primary/20 bg-primary/5 p-3"
                data-testid="investigation-action-locked-parent"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Parent investigation
                </p>
                <p className="mt-1 text-sm font-semibold text-foreground">{parentLabel}</p>
              </div>
            )}
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
                onChange={(e) => setActionForm({ ...actionForm, title: e.target.value })}
                placeholder="e.g., Implement additional safety controls"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-foreground">Assign To</label>
              <EngineerPeoplePicker
                valueLabel={actionForm.assigned_to}
                requireLogin
                onChange={(selection) =>
                  setActionForm({
                    ...actionForm,
                    assigned_to: selection?.user?.email || selection?.label || '',
                  })
                }
                placeholder="Search active employees…"
                testId="investigation-action-assignee-picker"
              />
            </div>
            <div>
              <span className="block text-sm font-medium text-foreground mb-1">Priority</span>
              <Select
                value={actionForm.priority}
                onValueChange={(value) => setActionForm({ ...actionForm, priority: value })}
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
                onChange={(e) => setActionForm({ ...actionForm, due_date: e.target.value })}
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
                onChange={(e) => setActionForm({ ...actionForm, description: e.target.value })}
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
                  setShowActionModal(false)
                  setActionError(null)
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={creatingAction || !actionForm.title}>
                {creatingAction ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Action'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Completion Notes Dialog */}
      <Dialog open={showCompletionDialog} onOpenChange={setShowCompletionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete Action</DialogTitle>
            <DialogDescription>
              Enter completion notes (optional) before marking this action as completed.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={completionNotes}
            onChange={(e) => setCompletionNotes(e.target.value)}
            placeholder="Enter completion notes..."
            rows={3}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCompletionDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (completionAction) {
                  onUpdateActionStatus(
                    completionAction,
                    'completed',
                    completionNotes || undefined,
                  )
                }
                setCompletionAction(null)
                setShowCompletionDialog(false)
              }}
            >
              Complete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
