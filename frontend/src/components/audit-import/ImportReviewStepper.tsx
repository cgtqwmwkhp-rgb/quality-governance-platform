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

/** User-facing guidance for what comes after the active step. */
const NEXT_STEP_COPY: Record<StepId, string> = {
  upload: 'Next: Processing — OCR extracts draft findings from your upload.',
  processing: 'Next: Review — check draft findings when extraction finishes.',
  review: 'Next: Promote — accept drafts, then promote into governance outcomes.',
  promote: 'Next: Promote Now, then Confirm — two clicks to attest accepted drafts.',
}

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

function resolveNextStepCopy(
  active: StepId,
  { jobStatus, promoteableCount }: Pick<ImportReviewStepperProps, 'jobStatus' | 'promoteableCount'>,
): string | null {
  const status = (jobStatus || '').toLowerCase()
  if (active === 'promote' && (status === 'completed' || status === 'promoted')) {
    return 'Import complete — accepted drafts have been promoted.'
  }
  if (active === 'promote' && (promoteableCount ?? 0) > 0) {
    return 'Next: Promote Now, then Confirm — two clicks to attest accepted drafts.'
  }
  return NEXT_STEP_COPY[active]
}

export function ImportReviewStepper(props: ImportReviewStepperProps) {
  const active = resolveActiveStep(props)
  const activeIndex = STEPS.findIndex((s) => s.id === active)
  const nextCopy = resolveNextStepCopy(active, props)

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
      {nextCopy ? (
        <p
          className="mt-2 text-sm text-muted-foreground"
          data-testid="import-review-stepper-next"
          role="status"
        >
          {nextCopy}
        </p>
      ) : null}
    </nav>
  )
}

export { resolveActiveStep, resolveNextStepCopy }
export type { ImportReviewStepperProps, StepId }
