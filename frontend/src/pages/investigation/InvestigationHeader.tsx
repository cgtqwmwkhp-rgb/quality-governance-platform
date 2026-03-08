import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ArrowLeft, FlaskConical, FileQuestion, Clock, GitBranch, CheckCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Investigation } from '../../api/client'
import { Badge } from '../../components/ui/Badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../components/ui/Tooltip'
import { cn } from '../../helpers/utils'

const STATUS_STEPS = [
  { id: 'draft', label: 'Draft', icon: FileQuestion },
  { id: 'in_progress', label: 'In Progress', icon: Clock },
  { id: 'under_review', label: 'Under Review', icon: GitBranch },
  { id: 'completed', label: 'Completed', icon: CheckCircle },
]

interface InvestigationHeaderProps {
  investigation: Investigation
  statusDisplay: { label: string; className: string }
  EntityIcon: LucideIcon
}

export default function InvestigationHeader({
  investigation,
  statusDisplay,
  EntityIcon,
}: InvestigationHeaderProps) {
  const { t } = useTranslation()
  const statusIndex = STATUS_STEPS.findIndex((s) => s.id === investigation.status)

  return (
    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
      <div className="flex-1">
        <Link
          to="/investigations"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('investigations.back')}
        </Link>

        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center flex-shrink-0">
            <FlaskConical className="w-8 h-8 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <span className="font-mono text-sm text-primary">
                {investigation.reference_number}
              </span>
              <Badge className={statusDisplay.className}>{statusDisplay.label}</Badge>
              <span className="px-2 py-0.5 text-xs font-medium rounded bg-surface text-muted-foreground capitalize flex items-center gap-1">
                <EntityIcon className="w-3 h-3" />
                {investigation.assigned_entity_type.replace(/_/g, ' ')}
              </span>
            </div>
            <h1 className="text-2xl font-bold text-foreground">{investigation.title}</h1>
            {investigation.description && (
              <p className="text-muted-foreground mt-2 line-clamp-2">{investigation.description}</p>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 lg:w-80">
        {STATUS_STEPS.map((step, stepIndex) => {
          const isActive = stepIndex <= statusIndex
          const isCurrent = stepIndex === statusIndex
          return (
            <div key={step.id} className="flex items-center">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={cn(
                        'relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-300',
                        isCurrent
                          ? 'bg-primary shadow-lg'
                          : isActive
                            ? 'bg-primary/20'
                            : 'bg-surface',
                      )}
                    >
                      <step.icon
                        className={cn(
                          'w-5 h-5',
                          isActive ? 'text-primary-foreground' : 'text-muted-foreground',
                        )}
                      />
                      {isCurrent && (
                        <div className="absolute inset-0 rounded-xl animate-pulse bg-primary/30" />
                      )}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>{step.label}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              {stepIndex < STATUS_STEPS.length - 1 && (
                <div className={cn('w-4 h-0.5 mx-1', isActive ? 'bg-primary' : 'bg-muted')} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
