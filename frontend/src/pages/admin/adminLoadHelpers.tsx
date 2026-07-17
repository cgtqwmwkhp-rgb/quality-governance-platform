import { AlertTriangle, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getApiErrorMessage } from '../../api/client'
import { trackError } from '../../utils/errorTracker'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'

export function captureAdminLoadError(
  err: unknown,
  context: { component: string; action: string },
  fallback: string,
): string {
  trackError(err, { ...context, extra: { surface: 'admin' } })
  return getApiErrorMessage(err, fallback)
}

interface AdminLoadUnavailableProps {
  title: string
  description?: string
  message?: string
  onRetry?: () => void
  testId?: string
}

export function AdminLoadUnavailable({
  title,
  description,
  message,
  onRetry,
  testId = 'admin-load-unavailable',
}: AdminLoadUnavailableProps) {
  const { t } = useTranslation()

  return (
    <Card className="p-6 border-warning/30 bg-warning/5" data-testid={testId}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" aria-hidden />
          <div>
            <p className="font-medium text-foreground">{title}</p>
            {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
            {message && (
              <p className="mt-2 text-sm text-warning" data-testid={`${testId}-message`}>
                {message}
              </p>
            )}
          </div>
        </div>
        {onRetry && (
          <Button variant="outline" onClick={onRetry} data-testid={`${testId}-retry`}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {t('common.retry', 'Retry')}
          </Button>
        )}
      </div>
    </Card>
  )
}
