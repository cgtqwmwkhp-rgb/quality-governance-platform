import { Loader2, MessageSquare, Plus, Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Textarea } from '../ui/Textarea'
import { RunningSheetEntry } from '../../api/client'

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
}: RunningSheetPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-3">
          <Textarea
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
            Add
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
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6 p-0 text-destructive"
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
