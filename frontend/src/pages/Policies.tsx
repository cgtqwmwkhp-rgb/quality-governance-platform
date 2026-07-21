import { useEffect, useState, useDeferredValue } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import { FileText, Search } from 'lucide-react'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { EmptyState } from '../components/ui/EmptyState'
import { policiesApi, Policy, getApiErrorMessage } from '../api/client'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Link } from 'react-router-dom'
import { LibraryShell } from './LibraryShell'

export default function Policies() {
  const { t } = useTranslation()
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await policiesApi.list(1, 50)
        if (!cancelled) setPolicies(response.data.items ?? [])
      } catch (err) {
        if (!cancelled) {
          trackError(err, { component: 'Policies', action: 'load' })
          setLoadError(getApiErrorMessage(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'policy':
        return '📜'
      case 'procedure':
        return '📋'
      case 'work_instruction':
        return '📝'
      case 'sop':
        return '📘'
      case 'form':
        return '📄'
      case 'template':
        return '📑'
      case 'guideline':
        return '📖'
      case 'manual':
        return '📚'
      case 'record':
        return '🗂️'
      default:
        return '📎'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'published':
        return 'resolved'
      case 'approved':
        return 'success'
      case 'under_review':
        return 'in-progress'
      case 'draft':
        return 'submitted'
      case 'superseded':
        return 'closed'
      case 'retired':
        return 'destructive'
      default:
        return 'secondary'
    }
  }

  const deferredSearch = useDeferredValue(searchTerm)
  const filteredPolicies = policies.filter(
    (p) =>
      p.title.toLowerCase().includes(deferredSearch.toLowerCase()) ||
      p.reference_number.toLowerCase().includes(deferredSearch.toLowerCase()) ||
      (p.category || '').toLowerCase().includes(deferredSearch.toLowerCase()),
  )

  if (loading) {
    return <TableSkeleton rows={8} columns={4} />
  }

  return (
    <LibraryShell
      activeView="policies"
      actions={
        <div className="flex flex-wrap gap-2 text-sm">
          <Link className="text-primary hover:underline" to="/documents">
            Governance Library
          </Link>
          <Link className="text-primary hover:underline" to="/document-control">
            Document Control
          </Link>
          <Link className="text-primary hover:underline" to="/documents/campaigns">
            HSEQ Campaigns
          </Link>
        </div>
      }
    >
      {loadError && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{loadError}</div>
      )}
      <div className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm text-foreground">
        New Policy CRUD is frozen. Use Governance Library for controlled files, Document Control for governance,
        and HSEQ Campaigns for acknowledgements.
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('policies.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPolicies.length === 0 ? (
          <div className="col-span-full">
            <EmptyState
              icon={<FileText className="w-8 h-8 text-muted-foreground" />}
              title={t('policies.empty.title')}
              description={t('policies.empty.subtitle')}
            />
          </div>
        ) : (
          filteredPolicies.map((policy) => (
            <Card key={policy.id} hoverable className="p-5 cursor-pointer">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-2xl">
                  {getTypeIcon(policy.document_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-xs text-primary mb-1">{policy.reference_number}</p>
                  <h2 className="font-semibold text-foreground truncate text-base">{policy.title}</h2>
                  {policy.description && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                      {policy.description}
                    </p>
                  )}
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <Badge variant={getStatusVariant(policy.status) as any}>
                  {policy.status.replace('_', ' ')}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {policy.document_type.replace('_', ' ')}
                </span>
              </div>
              {policy.next_review_date && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-muted-foreground">
                    {t('policies.review_due')}{' '}
                    {new Date(policy.next_review_date).toLocaleDateString()}
                  </p>
                </div>
              )}
            </Card>
          ))
        )}
      </div>

    </LibraryShell>
  )
}
