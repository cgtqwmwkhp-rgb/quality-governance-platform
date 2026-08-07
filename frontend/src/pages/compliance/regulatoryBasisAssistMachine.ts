/**
 * Pure state machine for Regulatory basis AI assist (propose → confirm).
 *
 * The only event that may fill the form is ACCEPT. Every other transition is
 * display / fetch side-effects so auto-apply is structurally impossible.
 */

export interface RegulatoryBasisCandidate {
  label: string
  regulation_or_standard_code: string
  standard_id?: number | null
  clause_ids: number[]
  confidence: number
  rationale: string
  source: string
}

export interface RegulatoryBasisQuestion {
  id: string
  question: string
  options: string[]
  why: string
}

export interface RegulatoryBasisSuggestResponse {
  candidates: RegulatoryBasisCandidate[]
  needs_clarification: boolean
  clarifying_questions: RegulatoryBasisQuestion[]
  confidence_threshold: number
  ai_available: boolean
  notice?: string | null
}

export type AssistState =
  | { kind: 'idle' }
  | { kind: 'suggesting'; carried: RegulatoryBasisCandidate[] }
  | {
      kind: 'proposing'
      candidates: RegulatoryBasisCandidate[]
      selectedCode: string
      threshold: number
      notice?: string
    }
  | {
      kind: 'clarifying'
      questions: RegulatoryBasisQuestion[]
      answers: Record<string, string>
      carried: RegulatoryBasisCandidate[]
      notice?: string
    }
  | { kind: 'empty'; notice: string }
  | { kind: 'error'; message: string }

export type AssistEvent =
  | { type: 'SUGGEST' }
  | { type: 'RESULT'; payload: RegulatoryBasisSuggestResponse }
  | { type: 'FAIL'; message: string }
  | { type: 'ANSWER'; id: string; value: string }
  | { type: 'RESUBMIT' }
  | { type: 'SKIP_QUESTIONS' }
  | { type: 'SELECT'; code: string }
  | { type: 'ACCEPT' }
  | { type: 'DISCARD' }
  | { type: 'RESET' }

export type AssistEffect =
  | { kind: 'fetchSuggest' }
  | { kind: 'fetchClarify'; answers: Record<string, string> }
  | { kind: 'accepted'; candidate: RegulatoryBasisCandidate }

export type AssistReduceResult = { state: AssistState; effect?: AssistEffect }

export function initialAssistState(): AssistState {
  return { kind: 'idle' }
}

export function reduce(state: AssistState, event: AssistEvent): AssistReduceResult {
  switch (event.type) {
    case 'RESET':
    case 'DISCARD':
      return { state: { kind: 'idle' } }

    case 'SUGGEST':
      if (state.kind !== 'idle' && state.kind !== 'error' && state.kind !== 'empty') {
        return { state }
      }
      return { state: { kind: 'suggesting', carried: [] }, effect: { kind: 'fetchSuggest' } }

    case 'FAIL':
      return { state: { kind: 'error', message: event.message } }

    case 'RESULT':
      return reduceResult(state, event.payload)

    case 'ANSWER':
      if (state.kind !== 'clarifying') return { state }
      return {
        state: {
          ...state,
          answers: { ...state.answers, [event.id]: event.value },
        },
      }

    case 'RESUBMIT': {
      if (state.kind !== 'clarifying') return { state }
      const hasAnswer = Object.values(state.answers).some((v) => v.trim() !== '')
      if (!hasAnswer) return { state }
      return {
        state: { kind: 'suggesting', carried: state.carried },
        effect: { kind: 'fetchClarify', answers: state.answers },
      }
    }

    case 'SKIP_QUESTIONS': {
      if (state.kind !== 'clarifying') return { state }
      if (state.carried.length === 0) {
        return {
          state: {
            kind: 'empty',
            notice: state.notice ?? 'No regulation or standard could be matched.',
          },
        }
      }
      return {
        state: {
          kind: 'proposing',
          candidates: state.carried,
          selectedCode: state.carried[0].regulation_or_standard_code,
          threshold: 0.7,
          notice: state.notice,
        },
      }
    }

    case 'SELECT':
      if (state.kind !== 'proposing') return { state }
      return { state: { ...state, selectedCode: event.code } }

    case 'ACCEPT': {
      if (state.kind !== 'proposing') return { state }
      const candidate = state.candidates.find(
        (c) => c.regulation_or_standard_code === state.selectedCode,
      )
      if (!candidate) return { state }
      return { state: { kind: 'idle' }, effect: { kind: 'accepted', candidate } }
    }

    default:
      return { state }
  }
}

function reduceResult(
  state: AssistState,
  payload: RegulatoryBasisSuggestResponse,
): AssistReduceResult {
  if (state.kind !== 'suggesting') return { state }

  const candidates = payload.candidates ?? []
  const questions = payload.clarifying_questions ?? []
  const notice = payload.notice ?? undefined

  if (payload.needs_clarification && questions.length >= 2) {
    return {
      state: {
        kind: 'clarifying',
        questions,
        answers: {},
        carried: candidates,
        notice,
      },
    }
  }

  if (candidates.length === 0) {
    return {
      state: {
        kind: 'empty',
        notice: notice ?? 'No regulation or standard could be matched.',
      },
    }
  }

  return {
    state: {
      kind: 'proposing',
      candidates,
      selectedCode: candidates[0].regulation_or_standard_code,
      threshold: payload.confidence_threshold,
      notice,
    },
  }
}
