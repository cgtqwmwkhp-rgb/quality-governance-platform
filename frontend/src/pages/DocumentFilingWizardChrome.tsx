/**
 * Compact step chrome for the Documents upload / filing wizard.
 */
import { useTranslation } from 'react-i18next'
import { cn } from '../helpers/utils'
import {
  DOCUMENT_FILING_WIZARD_STEPS,
  filingWizardStepIndex,
  type DocumentFilingWizardStep,
} from './documentFilingWizard'

export interface DocumentFilingWizardChromeProps {
  step: DocumentFilingWizardStep
}

export function DocumentFilingWizardChrome({ step }: DocumentFilingWizardChromeProps) {
  const { t } = useTranslation()
  const activeIndex = filingWizardStepIndex(step)

  return (
    <ol
      className="mb-2 flex flex-wrap gap-2"
      data-testid="documents-filing-wizard-chrome"
      aria-label={t('documents.filing.chrome.label')}
    >
      {DOCUMENT_FILING_WIZARD_STEPS.map((id, index) => {
        const isActive = index === activeIndex
        const isDone = index < activeIndex
        return (
          <li
            key={id}
            className={cn(
              'rounded-full border px-2.5 py-0.5 text-xs',
              isActive && 'border-primary bg-primary/10 text-primary',
              isDone && 'border-border bg-surface text-muted-foreground',
              !isActive && !isDone && 'border-border/60 text-muted-foreground/70',
            )}
            data-testid={`documents-filing-chrome-${id}`}
            aria-current={isActive ? 'step' : undefined}
          >
            <span className="font-medium">{index + 1}. </span>
            {t(`documents.filing.chrome.${id}`)}
          </li>
        )
      })}
    </ol>
  )
}

export default DocumentFilingWizardChrome
