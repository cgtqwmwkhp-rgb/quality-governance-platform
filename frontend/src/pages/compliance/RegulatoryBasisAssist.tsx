import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/Label'
import { complianceScheduleApi, getApiErrorMessage } from '../../api/client'
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { regulatoryBasisAssistCopy as copy } from './regulatoryBasisAssistI18n'
import {
  initialAssistState,
  reduce,
  type AssistState,
  type RegulatoryBasisCandidate,
  type RegulatoryBasisSuggestResponse,
} from './regulatoryBasisAssistMachine'

export interface RegulatoryBasisAssistProps {
  title: string
  taxonomyId: string
  description: string
  statutory: boolean
  requirementId?: number | null
  onAccept: (candidate: RegulatoryBasisCandidate) => void
}

/**
 * Propose → confirm UI for regulatory basis. Mounted beside the free-text field.
 * Gated by both the CS module flag and the regulatory-AI sub-flag.
 */
export function RegulatoryBasisAssist({
  title,
  taxonomyId,
  description,
  statutory,
  requirementId,
  onAccept,
}: RegulatoryBasisAssistProps) {
  const { t } = useTranslation()
  const csOpen = useFeatureFlag('compliance_schedule')
  const aiOpen = useFeatureFlag('compliance_schedule_regulatory_ai')
  const [state, setState] = useState<AssistState>(initialAssistState)
  const requestSeq = useRef(0)

  const dispatch = useCallback(
    (event: Parameters<typeof reduce>[1]) => {
      setState((prev) => {
        const next = reduce(prev, event)
        if (next.effect?.kind === 'accepted') {
          // Defer parent update so we never setState on the parent during our own render.
          const candidate = next.effect.candidate
          queueMicrotask(() => onAccept(candidate))
        }
        if (next.effect?.kind === 'fetchSuggest' || next.effect?.kind === 'fetchClarify') {
          const seq = ++requestSeq.current
          const payload = {
            title: title.trim(),
            taxonomy_id: taxonomyId,
            description: description.trim() || null,
            statutory,
            requirement_id: requirementId ?? undefined,
          }
          const run =
            next.effect.kind === 'fetchClarify'
              ? complianceScheduleApi.clarifyRegulatoryBasis({
                  ...payload,
                  answers: Object.entries(next.effect.answers).map(([question_id, answer]) => ({
                    question_id,
                    answer,
                  })),
                })
              : complianceScheduleApi.suggestRegulatoryBasis(payload)

          void run
            .then((res) => {
              if (seq !== requestSeq.current) return
              const body = res.data as RegulatoryBasisSuggestResponse
              setState((current) => reduce(current, { type: 'RESULT', payload: body }).state)
            })
            .catch((err) => {
              if (seq !== requestSeq.current) return
              setState(
                reduce(
                  { kind: 'suggesting', carried: [] },
                  { type: 'FAIL', message: getApiErrorMessage(err) },
                ).state,
              )
            })
        }
        return next.state
      })
    },
    [onAccept, title, taxonomyId, description, statutory, requirementId],
  )

  useEffect(() => {
    if (!csOpen || !aiOpen) {
      setState(initialAssistState())
    }
  }, [csOpen, aiOpen])

  if (!csOpen || !aiOpen) return null

  const canSuggest = title.trim().length > 0 && taxonomyId.trim().length > 0

  return (
    <div className="space-y-3" data-testid="regulatory-basis-assist">
      {(state.kind === 'idle' || state.kind === 'error' || state.kind === 'empty') && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canSuggest}
          onClick={() => dispatch({ type: 'SUGGEST' })}
          data-testid="regulatory-basis-suggest-button"
        >
          {t('compliance.schedule.regulatory_ai.suggest', copy.suggestButton)}
        </Button>
      )}

      {state.kind === 'suggesting' && (
        <p className="text-sm text-muted-foreground" data-testid="regulatory-basis-suggesting">
          {t('compliance.schedule.regulatory_ai.suggesting', copy.suggesting)}
        </p>
      )}

      {state.kind === 'error' && (
        <p className="text-sm text-destructive" role="alert" data-testid="regulatory-basis-error">
          {state.message}
        </p>
      )}

      {state.kind === 'empty' && (
        <p className="text-sm text-muted-foreground" data-testid="regulatory-basis-empty">
          {state.notice}
        </p>
      )}

      {state.kind === 'clarifying' && (
        <div
          className="space-y-3 rounded-md border border-border p-3"
          data-testid="regulatory-basis-clarify"
        >
          <p className="text-sm font-medium">
            {t('compliance.schedule.regulatory_ai.clarify_heading', copy.clarifyingHeading)}
          </p>
          {state.notice ? (
            <p className="text-xs text-muted-foreground" data-testid="regulatory-basis-notice">
              {state.notice}
            </p>
          ) : null}
          {state.questions.map((q) => (
            <div key={q.id} className="space-y-1">
              <Label htmlFor={`reg-ai-q-${q.id}`} className="text-sm">
                {q.question}
              </Label>
              {q.options.length > 0 ? (
                <select
                  id={`reg-ai-q-${q.id}`}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={state.answers[q.id] ?? ''}
                  onChange={(e) => dispatch({ type: 'ANSWER', id: q.id, value: e.target.value })}
                  data-testid={`regulatory-basis-question-${q.id}`}
                >
                  <option value="">Choose…</option>
                  {q.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`reg-ai-q-${q.id}`}
                  value={state.answers[q.id] ?? ''}
                  onChange={(e) => dispatch({ type: 'ANSWER', id: q.id, value: e.target.value })}
                  data-testid={`regulatory-basis-question-${q.id}`}
                />
              )}
              {q.why ? <p className="text-xs text-muted-foreground">{q.why}</p> : null}
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => dispatch({ type: 'RESUBMIT' })}
              data-testid="regulatory-basis-resubmit"
            >
              {t('compliance.schedule.regulatory_ai.resubmit', copy.resubmit)}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => dispatch({ type: 'SKIP_QUESTIONS' })}
              data-testid="regulatory-basis-skip"
            >
              {t('compliance.schedule.regulatory_ai.skip', copy.skipQuestions)}
            </Button>
          </div>
        </div>
      )}

      {state.kind === 'proposing' && (
        <div
          className="space-y-3 rounded-md border border-border p-3"
          data-testid="regulatory-basis-proposals"
        >
          <p className="text-sm font-medium">
            {t('compliance.schedule.regulatory_ai.candidates_heading', copy.candidatesHeading)}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('compliance.schedule.regulatory_ai.select_hint', copy.selectHint)}
          </p>
          {state.notice ? (
            <p className="text-xs text-muted-foreground" data-testid="regulatory-basis-notice">
              {state.notice}
            </p>
          ) : null}
          <ul className="space-y-2">
            {state.candidates.map((c) => {
              const selected = c.regulation_or_standard_code === state.selectedCode
              return (
                <li key={c.regulation_or_standard_code}>
                  <button
                    type="button"
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                      selected ? 'border-primary bg-primary/5' : 'border-border'
                    }`}
                    onClick={() =>
                      dispatch({ type: 'SELECT', code: c.regulation_or_standard_code })
                    }
                    data-testid={`regulatory-basis-candidate-${c.regulation_or_standard_code}`}
                  >
                    <div className="font-medium">{c.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {c.regulation_or_standard_code} · {Math.round(c.confidence * 100)}% ·{' '}
                      {c.source}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{c.rationale}</div>
                  </button>
                </li>
              )
            })}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => dispatch({ type: 'ACCEPT' })}
              data-testid="regulatory-basis-accept"
            >
              {t('compliance.schedule.regulatory_ai.accept', copy.accept)}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => dispatch({ type: 'DISCARD' })}
              data-testid="regulatory-basis-discard"
            >
              {t('compliance.schedule.regulatory_ai.discard', copy.discard)}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
