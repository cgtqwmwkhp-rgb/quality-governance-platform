import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { cn } from '../../helpers/utils'
import TrainingInductionsPanel from './TrainingInductionsPanel'
import {
  TrainingMatrixAdminPanel,
  TrainingMatrixGapBoard,
  TrainingMatrixMyTraining,
} from './trainingMatrix/TrainingMatrixPanels'

type TabId = 'gaps' | 'mine' | 'inductions' | 'admin'

export default function Training() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as TabId) || 'gaps'

  const tabs = useMemo(
    () =>
      [
        {
          id: 'gaps' as const,
          label: t('workforce.training_matrix.tab_gaps', 'Compliance gaps'),
        },
        {
          id: 'mine' as const,
          label: t('workforce.training_matrix.tab_mine', 'My training'),
        },
        {
          id: 'inductions' as const,
          label: t('workforce.training_matrix.tab_inductions', 'Inductions'),
        },
        {
          id: 'admin' as const,
          label: t('workforce.training_matrix.tab_admin', 'Admin'),
        },
      ] as const,
    [t],
  )

  return (
    <div className="space-y-6" data-testid="training-shell">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          {t('workforce.training.title', 'Training')}
        </h1>
        <p className="text-muted-foreground mt-1">
          {t(
            'workforce.training_matrix.shell_subtitle',
            'Atlas completions + Plantexpand frequency rules. Not an LMS — complete modules in Atlas.',
          )}
        </p>
      </div>

      <div
        className="inline-flex rounded-md border border-border p-0.5 gap-0.5"
        role="tablist"
        aria-label={t('workforce.training_matrix.tabs', 'Training sections')}
      >
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            data-testid={`training-tab-${item.id}`}
            className={cn(
              'px-3 py-1.5 text-sm rounded-sm',
              tab === item.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
            onClick={() => setParams(item.id === 'gaps' ? {} : { tab: item.id })}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'gaps' ? <TrainingMatrixGapBoard /> : null}
      {tab === 'mine' ? <TrainingMatrixMyTraining /> : null}
      {tab === 'inductions' ? <TrainingInductionsPanel /> : null}
      {tab === 'admin' ? <TrainingMatrixAdminPanel /> : null}
    </div>
  )
}
