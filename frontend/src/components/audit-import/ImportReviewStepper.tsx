type StepId = 'upload' | 'processing' | 'review' | 'promote'

type ImportReviewStepperProps = {
  jobStatus?: string | null
  isProcessing?: boolean
  promoteableCount?: number
  hasJob?: boolean
}

const STEPS: { id: StepId; label: string }[] = [
  { id: 'upload', label: 'Upload' },
  { id: 'processing', label: 'Processing' },
  { id: 'review', label: 'Review' },
  { id: 'promote', label: 'Promote' },
]

function resolveActiveStep({
  jobStatus,
  isProcessing,
  promoteableCount,
  hasJob,
}: ImportReviewStepperProps): StepId {
  const status = (jobStatus || '').toLowerCase()
  if (!hasJob) return 'upload'
  if (isProcessing || status === 'processing' || status === 'queued' || status === 'running') {
    return 'processing'
  }
  if ((promoteableCount ?? 0) > 0 || status === 'ready_to_promote' || status === 'reviewed') {
    return 'promote'
  }
  if (status === 'completed' || status === 'promoted') return 'promote'
  return 'review'
}

export function ImportReviewStepper(props: ImportReviewStepperProps) {
  const active = resolveActiveStep(props)
  const activeIndex = STEPS.findIndex((s) => s.id === active)

  return (
    <nav aria-label="Import review steps" className="mt-4">
      <ol className="flex flex-wrap items-center gap-2 text-sm">
        {STEPS.map((step, index) => {
          const state =
            index < activeIndex ? 'done' : index === activeIndex ? 'current' : 'upcoming'
          return (
            <li key={step.id} className="flex items-center gap-2">
              {index > 0 ? (
                <span aria-hidden className="text-muted-foreground">
                  →
                </span>
              ) : null}
              <span
                data-state={state}
                aria-current={state === 'current' ? 'step' : undefined}
                className={
                  state === 'current'
                    ? 'rounded-md bg-primary px-2.5 py-1 font-medium text-primary-foreground'
                    : state === 'done'
                      ? 'rounded-md bg-muted px-2.5 py-1 font-medium text-foreground'
                      : 'rounded-md px-2.5 py-1 text-muted-foreground'
                }
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export { resolveActiveStep }
export type { ImportReviewStepperProps, StepId }
