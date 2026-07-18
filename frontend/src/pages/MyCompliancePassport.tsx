import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Award, BookOpen, Loader2 } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type CompliancePassportAssignment,
  type CompliancePassportResponse,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'

function PassportSection({
  title,
  items,
  emptyTitle,
}: {
  title: string
  items: CompliancePassportAssignment[]
  emptyTitle: string
}) {
  if (items.length === 0) {
    return (
      <Card className="p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">{title}</h2>
        <p className="text-sm text-muted-foreground">{emptyTitle}</p>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <h2 className="text-lg font-semibold text-foreground mb-4">{title}</h2>
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex flex-col gap-2 border-b border-border pb-3 last:border-b-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <Badge variant="submitted">{item.status}</Badge>
                {item.quiz_passed != null && (
                  <Badge variant={item.quiz_passed ? 'default' : 'destructive'}>
                    Quiz {item.quiz_passed ? 'passed' : 'failed'}
                  </Badge>
                )}
              </div>
              <p className="font-medium text-foreground">{item.document_title}</p>
              {item.campaign_title && (
                <p className="text-sm text-muted-foreground">{item.campaign_title}</p>
              )}
              <p className="text-sm text-muted-foreground">
                Due {item.due_at ? new Date(item.due_at).toLocaleDateString() : '—'}
              </p>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link to={`/documents/${item.document_id}`}>Open document</Link>
            </Button>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default function MyCompliancePassport() {
  const [passport, setPassport] = useState<CompliancePassportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadPassport = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentCampaignApi.getMyPassport()
      setPassport(response.data)
    } catch (err) {
      const message = getApiErrorMessage(err)
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadPassport()
  }, [loadPassport])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  const stats = passport?.stats

  return (
    <div className="space-y-6 animate-fade-in" data-testid="my-compliance-passport-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">My Compliance Passport</h1>
          <p className="text-muted-foreground mt-1">
            Your document campaign completion record and outstanding reads.
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/my-reading">
            <BookOpen className="w-4 h-4 mr-2" />
            Go to My Reading
          </Link>
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Assigned</p>
          <p className="text-2xl font-bold text-foreground">{stats?.total_assigned ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Completion rate</p>
          <p className="text-2xl font-bold text-foreground">{stats?.completion_rate ?? 0}%</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Quiz pass rate</p>
          <p className="text-2xl font-bold text-foreground">{stats?.quiz_pass_rate ?? 0}%</p>
        </Card>
      </div>

      {!passport || passport.stats.total_assigned === 0 ? (
        <EmptyState
          icon={<Award className="w-8 h-8 text-muted-foreground" />}
          title="No campaign assignments yet"
          description="When you are assigned document campaigns, they will appear here."
        />
      ) : (
        <>
          <PassportSection
            title="Outstanding"
            items={passport.outstanding}
            emptyTitle="Nothing outstanding — you're up to date."
          />
          <PassportSection
            title="Completed"
            items={passport.completed}
            emptyTitle="No completed campaigns yet."
          />
        </>
      )}
    </div>
  )
}
