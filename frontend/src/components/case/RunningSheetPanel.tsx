import { ClipboardList, Loader2, MessageSquare, Plus, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Textarea } from '../ui/Textarea'
import { RunningSheetEntry } from '../../api/client'

export type RunningSheetActionSource = 'incident' | 'near_miss'

export interface RunningSheetCreateActionOptions {
  sourceType: RunningSheetActionSource
  sourceId: number
  referenceNumber: string
  /** Optional chronology snippet to prefill the action description. */
  entrySnippet?: string
}

/** Build Actions create deep-link with context + returnTo the case. */
export function buildRunningSheetCreateActionHref(
  opts: RunningSheetCreateActionOptions,
): string {
  const sp = new URLSearchParams()
  sp.set('create', '1')
  sp.set('title', `Follow-up from ${opts.referenceNumber}`)
  const snippet = (opts.entrySnippet || '').trim()
  const description =
    snippet.length > 0
      ? `From ${opts.sourceType.replace('_', ' ')} ${opts.referenceNumber} running sheet:\n\n${snippet}`
      : `Follow-up action from ${opts.sourceType.replace('_', ' ')} ${opts.referenceNumber} running sheet.`
  sp.set('description', description)
  // Incident is a first-class Actions source. Near miss is not — still prefill
  // title/description/returnTo so the operator can attach a valid source.
  if (opts.sourceType === 'incident') {
    sp.set('sourceType', 'incident')
    sp.set('sourceId', String(opts.sourceId))
  }
  const returnPath =
    opts.sourceType === 'incident'
      ? `/incidents/${opts.sourceId}`
      : `/near-misses/${opts.sourceId}`
  sp.set('returnTo', returnPath)
  return `/actions?${sp.toString()}`
}

interface RunningSheetPanelProps {
  entries: RunningSheetEntry[]
  newEntry: string
  addingEntry: boolean
  title: string
  placeholder: string
  emptyTitle: string
  emptyDescription: string
  canDeleteEntry?: (entry: RunningSheetEntry) => boolean
  onNewEntryChange: (value: string) => void
  onAddEntry: () => void
  onDeleteEntry: (entryId: number) => void
  /** Optional “Create Action” bridge — typically incident / near_miss. */
  createActionHref?: string
  createActionLabel?: string
}

export function RunningSheetPanel({
  entries,
  newEntry,
  addingEntry,
  title,
  placeholder,
  emptyTitle,
  emptyDescription,
  canDeleteEntry,
  onNewEntryChange,
  onAddEntry,
  onDeleteEntry,
  createActionHref,
  createActionLabel = 'Create Action',
}: RunningSheetPanelProps) {
  const { t } = useTranslation()
  const composerId = 'running-sheet-entry'

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary" />
          {title}
        </CardTitle>
        {createActionHref ? (
          <Button type="button" variant="outline" size="sm" asChild>
            <Link
              to={createActionHref}
              data-testid="running-sheet-create-action"
              title="Create an action prefilled from this case"
            >
              <ClipboardList className="w-4 h-4" />
              {createActionLabel}
            </Link>
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-3">
          <label htmlFor={composerId} className="sr-only">
            {title}
          </label>
          <Textarea
            id={composerId}
            value={newEntry}
            onChange={(e) => onNewEntryChange(e.target.value)}
            placeholder={placeholder}
            rows={2}
            className="flex-1"
          />
          <Button onClick={onAddEntry} disabled={addingEntry || !newEntry.trim()} className="self-end">
            {addingEntry ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-1" />
            )}
            {t('common.add')}
          </Button>
        </div>

        {entries.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>{emptyTitle}</p>
            <p className="text-sm mt-1">{emptyDescription}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map((entry) => {
              const allowDelete = canDeleteEntry ? canDeleteEntry(entry) : true
              return (
                <div key={entry.id} className="group border rounded-lg p-4 bg-muted/30 relative">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-mono font-semibold text-primary">
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                    {entry.author_email && (
                      <span className="text-xs text-muted-foreground">- {entry.author_email}</span>
                    )}
                  </div>
                  <p className="text-sm text-foreground whitespace-pre-wrap">{entry.content}</p>
                  {allowDelete && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 h-6 w-6 p-0 text-destructive"
                      onClick={() => onDeleteEntry(entry.id)}
                      aria-label="Delete running sheet entry"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
