import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react'
import {
  getApiErrorMessage,
  knowledgeBankApi,
  type KnowledgeEvidenceLink,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { cn } from '../helpers/utils'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

const statusBadge = (status: string) => {
  if (status === 'proposed') return <Badge variant="submitted">Proposed</Badge>
  if (status === 'needs_review') return <Badge variant="warning">Needs review</Badge>
  return <Badge variant="outline">{status}</Badge>
}

export default function KnowledgeExceptions() {
  const [items, setItems] = useState<KnowledgeEvidenceLink[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [acting, setActing] = useState(false)

  const loadExceptions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await knowledgeBankApi.listExceptions()
      setItems(response.data)
    } catch (err) {
      setError(reportFailure(err))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadExceptions()
  }, [loadExceptions])

  const allSelected = useMemo(
    () => items.length > 0 && selectedIds.length === items.length,
    [items.length, selectedIds.length],
  )

  const toggleAll = () => {
    setSelectedIds(allSelected ? [] : items.map((i) => i.id))
  }

  const toggleOne = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  const handleBulkConfirm = async () => {
    if (selectedIds.length === 0) return
    setActing(true)
    try {
      const response = await knowledgeBankApi.bulkConfirm(selectedIds)
      toast.success(`Confirmed ${response.data.count} item(s)`)
      setSelectedIds([])
      await loadExceptions()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActing(false)
    }
  }

  const handleBulkReject = async () => {
    if (selectedIds.length === 0) return
    setActing(true)
    try {
      await Promise.all(selectedIds.map((id) => knowledgeBankApi.rejectLink(id)))
      toast.success(`Rejected ${selectedIds.length} item(s)`)
      setSelectedIds([])
      await loadExceptions()
    } catch (err) {
      reportFailure(err)
    } finally {
      setActing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Knowledge Exceptions</h1>
          <p className="text-muted-foreground mt-1">
            Low-confidence AI evidence links requiring operator review
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={selectedIds.length === 0 || acting}
            onClick={() => void handleBulkConfirm()}
          >
            <CheckCircle2 className="w-4 h-4 mr-2" />
            Bulk confirm ({selectedIds.length})
          </Button>
          <Button
            variant="outline"
            disabled={selectedIds.length === 0 || acting}
            onClick={() => void handleBulkReject()}
          >
            <XCircle className="w-4 h-4 mr-2" />
            Bulk reject
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="w-8 h-8 text-success" />}
          title="Inbox clear"
          description="No proposed or needs-review evidence links at this time."
        />
      ) : (
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground px-1">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="rounded border-border"
            />
            Select all
          </label>
          {items.map((item) => (
            <Card
              key={item.id}
              className={cn('p-4', selectedIds.includes(item.id) && 'border-primary/50')}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={selectedIds.includes(item.id)}
                  onChange={() => toggleOne(item.id)}
                  aria-label={`Select exception ${item.id}`}
                  className="mt-1 rounded border-border"
                />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    {statusBadge(item.status)}
                    {item.scheme && <Badge variant="outline">{item.scheme}</Badge>}
                    <span className="font-mono text-xs text-muted-foreground">{item.clause_id}</span>
                  </div>
                  {item.title && <p className="font-medium text-foreground">{item.title}</p>}
                  {item.rationale && (
                    <p className="text-sm text-muted-foreground">{item.rationale}</p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {item.entity_type === 'document' && (
                      <Link
                        to={`/documents/${item.entity_id}`}
                        className="text-primary hover:underline"
                      >
                        Document #{item.entity_id}
                      </Link>
                    )}
                    {item.confidence != null && (
                      <span className="flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        {(item.confidence * 100).toFixed(0)}% confidence
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
