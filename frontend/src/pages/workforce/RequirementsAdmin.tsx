import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, ClipboardList, Loader2 } from 'lucide-react'
import { getApiErrorMessage, workforceApi, type CompetencyRequirement } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'

/**
 * Supervisor-facing read-only foundation for competency-requirements administration.
 * Route and create/edit controls are deliberately deferred to the next workforce-admin slice.
 */
export default function RequirementsAdmin() {
  const { t } = useTranslation()
  const [requirements, setRequirements] = useState<CompetencyRequirement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await workforceApi.competencyRequirements.list({ page_size: 100 })
      setRequirements(response.data.items ?? [])
    } catch (err) {
      setRequirements([])
      setError(getApiErrorMessage(err, t('workforce.requirements.load_error_body')))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return (
      <div
        className="flex h-64 items-center justify-center"
        data-testid="requirements-admin-loading"
      >
        <Loader2 className="h-8 w-8 animate-spin text-primary" aria-label={t('workforce.requirements.loading')} />
      </div>
    )
  }

  return (
    <div className="space-y-6" data-testid="requirements-admin">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t('workforce.requirements.title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('workforce.requirements.subtitle')}</p>
      </div>

      {error ? (
        <div
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
          data-testid="requirements-admin-error"
        >
          <p className="font-medium">{t('workforce.requirements.load_error')}</p>
          <p className="mt-1">{error}</p>
          <Button
            size="sm"
            variant="secondary"
            className="mt-3"
            onClick={() => void load()}
            data-testid="requirements-admin-retry"
          >
            {t('common.retry')}
          </Button>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">
              {t('workforce.requirements.configured_title')}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t('workforce.requirements.configured_subtitle', { count: requirements.length })}
            </p>
          </CardHeader>
          <CardContent>
            {requirements.length === 0 ? (
              <div
                className="flex h-40 flex-col items-center justify-center gap-2 text-center text-muted-foreground"
                data-testid="requirements-admin-empty"
              >
                <ClipboardList className="h-10 w-10" />
                <p className="text-sm">{t('workforce.requirements.empty')}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="requirements-admin-table">
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th className="p-3 font-medium">{t('workforce.requirements.name')}</th>
                      <th className="p-3 font-medium">{t('workforce.requirements.scope')}</th>
                      <th className="p-3 font-medium">{t('workforce.requirements.mandatory')}</th>
                      <th className="p-3 font-medium">{t('workforce.requirements.reassessment')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requirements.map((requirement) => (
                      <tr key={requirement.id} className="border-b border-border last:border-0">
                        <td className="p-3 font-medium text-foreground">{requirement.name}</td>
                        <td className="p-3 text-muted-foreground">
                          {requirement.site || requirement.role_key || '—'}
                        </td>
                        <td className="p-3">
                          {requirement.is_mandatory
                            ? t('workforce.requirements.yes')
                            : t('workforce.requirements.no')}
                        </td>
                        <td className="p-3">{requirement.reassessment_interval_days}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div
        className="flex gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground"
        data-testid="requirements-admin-next-step"
      >
        <AlertTriangle className="h-5 w-5 shrink-0 text-warning" />
        <p>{t('workforce.requirements.next_step')}</p>
      </div>
    </div>
  )
}
