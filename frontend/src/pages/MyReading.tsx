import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, CheckCircle2, ExternalLink, Loader2, Search } from 'lucide-react'
import {
  getApiErrorMessage,
  policyAcknowledgmentsApi,
  type PolicyAcknowledgment,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

export default function MyReading() {
  const [items, setItems] = useState<PolicyAcknowledgment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const loadPending = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await policyAcknowledgmentsApi.listMyPending()
      setItems(response.data.items ?? [])
    } catch (err) {
      setError(reportFailure(err))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadPending()
  }, [loadPending])

  const handleOpen = async (item: PolicyAcknowledgment) => {
    try {
      await policyAcknowledgmentsApi.recordOpen(item.id)
      window.open(`/documents/${item.policy_id}?tab=qa`, '_blank', 'noopener,noreferrer')
    } catch (err) {
      reportFailure(err)
    }
  }

  const handleAcknowledge = async (item: PolicyAcknowledgment) => {
    setAcknowledgingId(item.id)
    try {
      await policyAcknowledgmentsApi.acknowledge(item.id, {
        acceptance_statement: 'I have read and understood this document.',
      })
      toast.success('Acknowledgment recorded')
      setItems((prev) => prev.filter((i) => i.id !== item.id))
    } catch (err) {
      reportFailure(err)
    } finally {
      setAcknowledgingId(null)
    }
  }

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase()
    return items.filter((item) => {
      if (statusFilter !== 'all' && item.status !== statusFilter) return false
      if (!q) return true
      return (
        String(item.policy_id).includes(q) ||
        (item.policy_version ?? '').toLowerCase().includes(q) ||
        (item.status ?? '').toLowerCase().includes(q)
      )
    })
  }, [items, search, statusFilter])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="my-reading-page">
      <div>
        <h1 className="text-2xl font-bold text-foreground">My Reading</h1>
        <p className="text-muted-foreground mt-1">
          Pending document reads and acknowledgments assigned to you
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3" data-testid="my-reading-filters">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search pending reads"
            aria-label="Search pending reads"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
            data-testid="my-reading-search"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger
            className="w-full sm:w-48"
            aria-label="Filter by status"
            data-testid="my-reading-status-filter"
          >
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="opened">Opened</SelectItem>
            <SelectItem value="overdue">Overdue</SelectItem>
          </SelectContent>
        </Select>
        <Button type="button" variant="outline" data-testid="my-reading-filter-apply">
          Filter
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {filteredItems.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="w-8 h-8 text-muted-foreground" />}
          title={items.length === 0 ? 'All caught up' : 'No matching reads'}
          description={
            items.length === 0
              ? 'You have no pending reads at the moment.'
              : 'Clear or change the filters to see pending acknowledgments.'
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => (
            <Card key={item.id} className="p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="submitted">{item.status}</Badge>
                    {item.policy_version && (
                      <span className="text-xs text-muted-foreground">v{item.policy_version}</span>
                    )}
                  </div>
                  <p className="font-medium text-foreground">Policy #{item.policy_id}</p>
                  <p className="text-sm text-muted-foreground">
                    Due {new Date(item.due_date).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => void handleOpen(item)}>
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Open / Read
                  </Button>
                  <Button variant="outline" size="sm" asChild>
                    <Link to={`/documents/${item.policy_id}?tab=qa`}>
                      Q&A
                    </Link>
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => void handleAcknowledge(item)}
                    disabled={acknowledgingId === item.id}
                    data-testid={`my-reading-acknowledge-${item.id}`}
                    aria-label={`Acknowledge policy ${item.policy_id}`}
                  >
                    {acknowledgingId === item.id ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                    )}
                    Acknowledge
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
