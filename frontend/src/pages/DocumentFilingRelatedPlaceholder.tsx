/**
 * L-18b Related placeholder when `document_graph` is off (WD-1 scaffold).
 *
 * Honest: relationships are not recorded in this environment. Does not call
 * Doc Graph APIs. When the flag is on, Documents mounts the real
 * DocumentCreateRelationshipsStep instead.
 */
import { Link2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/ui/Button'

export interface DocumentFilingRelatedPlaceholderProps {
  documentTitle: string
  onContinue: () => void
}

export function DocumentFilingRelatedPlaceholder({
  documentTitle,
  onContinue,
}: DocumentFilingRelatedPlaceholderProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4" data-testid="documents-filing-related-placeholder">
      <div className="flex items-start gap-3 rounded-lg border border-border bg-surface/40 px-3 py-3">
        <Link2 className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">
            {t('documents.filing.related_off.title')}
          </p>
          <p className="text-sm text-muted-foreground">
            {t('documents.filing.related_off.body', { title: documentTitle })}
          </p>
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={onContinue} data-testid="documents-filing-related-continue">
          {t('documents.filing.related_off.continue')}
        </Button>
      </div>
    </div>
  )
}

export default DocumentFilingRelatedPlaceholder
