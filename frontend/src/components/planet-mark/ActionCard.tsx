import { useState, useEffect } from 'react'
import { Clock, User, AlertTriangle, CheckCircle2, Loader2, ChevronDown } from 'lucide-react'
import { planetMarkApi } from '../../api/client'

export interface ActionItem {
  id: number
  action_id: string
  action_title: string
  owner: string
  deadline: string
  status: string
  progress_percent: number
  target_scope?: string
  expected_reduction_pct: number
  is_overdue: boolean
  notes?: string | null
}

interface ActionCardProps {
  yearId: number
  action: ActionItem
  onUpdated: () => void
  selected?: boolean
  onSelect?: (id: number, checked: boolean) => void
}

const STATUS_STYLES: Record<string, string> = {
  planned: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-600',
  on_hold: 'bg-amber-100 text-amber-700',
}

export function ActionCard({ yearId, action, onUpdated, selected, onSelect }: ActionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [notes, setNotes] = useState(action.notes || '')
  const [progress, setProgress] = useState(action.progress_percent)
  const [status, setStatus] = useState(action.status)
  const [error, setError] = useState<string | null>(null)

  // Sync local editing state when server data changes (e.g. after parent refresh)
  useEffect(() => {
    if (!isExpanded) {
      setNotes(action.notes || '')
      setProgress(action.progress_percent)
      setStatus(action.status)
    }
  }, [action.notes, action.progress_percent, action.status, isExpanded])

  const isOverdue = action.is_overdue && action.status !== 'completed'

  const handleSave = async () => {
    setLoading(true)
    setError(null)
    try {
      await planetMarkApi.updateAction(yearId, action.id, {
        status,
        progress_percent: progress,
        notes,
      })
      onUpdated()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setLoading(false)
    }
  }

  const deadlineFormatted = action.deadline
    ? new Date(action.deadline).toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : '—'

  return (
    <div
      className={`border rounded-lg bg-white overflow-hidden transition-shadow hover:shadow-sm
        ${isOverdue ? 'border-l-4 border-l-red-400' : 'border-l-4 border-l-transparent'}
        ${selected ? 'ring-2 ring-blue-400' : ''}`}
    >
      <div className="flex items-start gap-3 p-4">
        {onSelect && (
          <input
            type="checkbox"
            checked={selected ?? false}
            onChange={(e) => onSelect(action.id, e.target.checked)}
            className="mt-1 w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            aria-label={`Select action ${action.action_title}`}
          />
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="text-xs font-mono text-gray-400">{action.action_id}</span>
              <h3 className="font-medium text-gray-900 text-sm leading-snug">{action.action_title}</h3>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {isOverdue && (
                <span className="flex items-center gap-1 text-xs text-red-600 font-medium">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Overdue
                </span>
              )}
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[action.status] ?? STATUS_STYLES.planned}`}
              >
                {action.status.replace('_', ' ')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <User className="w-3.5 h-3.5" />
              {action.owner || 'Unassigned'}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {deadlineFormatted}
            </span>
            {action.expected_reduction_pct > 0 && (
              <span className="text-green-700">
                -{action.expected_reduction_pct}% CO₂e
              </span>
            )}
          </div>

          {/* Progress bar */}
          <div className="mt-2">
            <div className="flex justify-between text-xs text-gray-400 mb-0.5">
              <span>Progress</span>
              <span>{action.progress_percent}%</span>
            </div>
            <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  action.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
                }`}
                style={{ width: `${action.progress_percent}%` }}
                role="progressbar"
                aria-valuenow={action.progress_percent}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
          </div>
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
          aria-label={isExpanded ? 'Collapse action details' : 'Expand action details'}
        >
          <ChevronDown className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isExpanded && (
        <div className="border-t px-4 pb-4 pt-3 bg-gray-50">
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label htmlFor={`status-${action.id}`} className="block text-xs font-medium text-gray-600 mb-1">Status</label>
              <select
                id={`status-${action.id}`}
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-green-500 outline-none"
              >
                <option value="planned">Planned</option>
                <option value="in_progress">In Progress</option>
                <option value="on_hold">On Hold</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div>
              <label htmlFor={`progress-${action.id}`} className="block text-xs font-medium text-gray-600 mb-1">
                Progress ({progress}%)
              </label>
              <input
                id={`progress-${action.id}`}
                type="range"
                min={0}
                max={100}
                step={5}
                value={progress}
                onChange={(e) => setProgress(Number(e.target.value))}
                className="w-full accent-green-600 mt-1"
                aria-label="Progress percentage"
              />
            </div>
          </div>

          <div>
            <label htmlFor={`notes-${action.id}`} className="block text-xs font-medium text-gray-600 mb-1">Notes</label>
            <textarea
              id={`notes-${action.id}`}
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add progress notes, blockers, or context…"
              className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:ring-1 focus:ring-green-500 outline-none resize-none"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 mt-2" role="alert">{error}</p>
          )}

          <button
            onClick={handleSave}
            disabled={loading}
            className="mt-3 flex items-center gap-1.5 px-4 py-1.5 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
            Save Changes
          </button>
        </div>
      )}
    </div>
  )
}
