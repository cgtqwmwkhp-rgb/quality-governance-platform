import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Users, MapPin, Building2, ChevronRight } from 'lucide-react'
import { CardSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import { workforceApi, type EngineerProfile } from '../../api/client'
import { getApiErrorMessage } from '../../api/client'
import { Input } from '../../components/ui/Input'
import { Card, CardContent } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'

export default function Engineers() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [engineers, setEngineers] = useState<EngineerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Search debounce (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  useEffect(() => {
    const load = async () => {
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
    }
    load()
  }, [debouncedSearch])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t('workforce.engineers.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('workforce.engineers.subtitle')}</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
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
              <CardContent className="py-12 text-center text-muted-foreground">
                {t('workforce.engineers.empty')}
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
                            {eng.employee_number || eng.job_title || `Engineer #${eng.id}`}
                          </h3>
                          <p className="text-sm text-muted-foreground truncate">
                            {eng.department ?? eng.site ?? '—'}
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
