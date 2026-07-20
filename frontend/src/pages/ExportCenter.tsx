import { Download } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'

/**
 * Honest unavailable state — no fabricated counts or demo export history (PX-011).
 * Route kept so deep links and future wiring do not break.
 */
export default function ExportCenter() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-primary to-primary-hover rounded-xl">
            <Download className="w-8 h-8 text-primary-foreground" />
          </div>
          {t('exports.title')}
        </h1>
        <p className="text-muted-foreground mt-1">{t('exports.subtitle')}</p>
      </div>

      <Card data-testid="export-center-unavailable">
        <CardHeader>
          <CardTitle className="text-base">
            {t('exports.unavailable.title', 'Export Center not available yet')}
          </CardTitle>
          <CardDescription>
            {t(
              'exports.unavailable.description',
              'Bulk exports, job history, and scheduled templates are not wired to live APIs yet. No sample counts or demo history are shown here.',
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link to="/documents">{t('exports.unavailable.documents', 'Open Documents')}</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/dashboard">{t('exports.unavailable.dashboard', 'Back to Dashboard')}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
