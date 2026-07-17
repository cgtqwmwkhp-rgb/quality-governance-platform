import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Users, MapPin, Building2, ChevronRight, RefreshCw } from 'lucide-react'
import { CardSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import { workforceApi, type EngineerProfile } from '../../api/client'
import { getApiErrorMessage } from '../../api/client'
import { Input } from '../../components/ui/Input'
import { Card, CardContent } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { cn } from '../../helpers/utils'

function engineerLabel(eng: EngineerProfile): string {
  return (
    eng.display_name?.trim() ||
    eng.employee_number?.trim() ||
    eng.job_title?.trim() ||
    `Employee #${eng.id}`
  )
}

export default function Engineers() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [engineers, setEngineers] = useState<EngineerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  const loadEngineers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = { page: '1', page_size: '50' }
      if (debouncedSearch) params.search = debouncedSearch
      const res = await workforceApi.listEngineers(params)
      setEngineers(res.data.items || [])
    } catch (err) {
      setEngineers([])
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch])

  useEffect(() => {
    void loadEngineers()
  }, [loadEngineers])

  const handleSyncFromPams = async () => {
    setSyncing(true)
    setSyncMessage(null)
    setError(null)
    try {
      const res = await workforceApi.syncFromPams()
      setSyncMessage(
        t('workforce.engineers.sync_from_pams_success', {
          created: res.data.created,
          updated: res.data.updated,
          deactivated: res.data.deactivated,
        }),
      )
      await loadEngineers()
    } catch (err) {
      setError(getApiErrorMessage(err) || t('workforce.engineers.sync_from_pams_error'))
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('workforce.engineers.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('workforce.engineers.subtitle')}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => void handleSyncFromPams()}
          disabled={syncing || loading}
          className="shrink-0"
        >
          <RefreshCw className={cn('w-4 h-4 mr-2', syncing && 'animate-spin')} />
          {syncing ? t('workforce.engineers.syncing') : t('workforce.engineers.sync_from_pams')}
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}
          {syncMessage && (
            <div className="mb-4 p-3 rounded-lg bg-primary/10 text-primary text-sm">
              {syncMessage}
            </div>
          )}
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder={t('workforce.engineers.search_placeholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <CardSkeleton count={6} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {engineers.length === 0 ? (
            <Card className="col-span-full">
              <CardContent className="py-12 text-center text-muted-foreground space-y-4">
                <p>{t('workforce.engineers.empty')}</p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleSyncFromPams()}
                  disabled={syncing}
                >
                  <RefreshCw className={cn('w-4 h-4 mr-2', syncing && 'animate-spin')} />
                  {syncing ? t('workforce.engineers.syncing') : t('workforce.engineers.sync_from_pams')}
                </Button>
              </CardContent>
            </Card>
          ) : (
            engineers.map((eng) => (
              <Card
                key={eng.id}
                hoverable
                className={cn(
                  'cursor-pointer transition-all',
                  'hover:shadow-md hover:border-border-strong',
                )}
                onClick={() => navigate(`/workforce/engineers/${eng.id}`)}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                          <Users className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-foreground truncate">
                            {engineerLabel(eng)}
                          </h3>
                          <p className="text-sm text-muted-foreground truncate">
                            {eng.job_title ?? eng.department ?? eng.site ?? '—'}
                          </p>
                        </div>
                      </div>
                      <div className="mt-4 space-y-1.5 text-sm">
                        {eng.department && (
                          <div className="flex items-center gap-2 text-muted-foreground">
                            <Building2 className="w-3.5 h-3.5 shrink-0" />
                            <span className="truncate">{eng.department}</span>
                          </div>
                        )}
                        {eng.site && (
                          <div className="flex items-center gap-2 text-muted-foreground">
                            <MapPin className="w-3.5 h-3.5 shrink-0" />
                            <span className="truncate">{eng.site}</span>
                          </div>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge variant={eng.is_active ? 'success' : 'secondary'}>
                          {eng.is_active ? t('common.active') : t('common.inactive')}
                        </Badge>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0" />
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  )
}
