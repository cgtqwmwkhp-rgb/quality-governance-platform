import { describe, expect, it } from 'vitest'
import {
  initialAssistState,
  reduce,
  type AssistEvent,
  type AssistState,
  type RegulatoryBasisCandidate,
  type RegulatoryBasisSuggestResponse,
} from '../regulatoryBasisAssistMachine'

const CANDIDATE: RegulatoryBasisCandidate = {
  label: 'Regulatory Reform (Fire Safety) Order 2005',
  regulation_or_standard_code: 'FSO2005',
  standard_id: null,
  clause_ids: [],
  confidence: 0.92,
  rationale: 'Matched curated UK regulation map',
  source: 'curated_uk_map',
}

const LOW: RegulatoryBasisCandidate = {
  ...CANDIDATE,
  confidence: 0.55,
  regulation_or_standard_code: 'HASAWA1974',
  label: 'Health and Safety at Work etc. Act 1974',
}

function highResult(overrides: Partial<RegulatoryBasisSuggestResponse> = {}): RegulatoryBasisSuggestResponse {
  return {
    candidates: [CANDIDATE],
    needs_clarification: false,
    clarifying_questions: [],
    confidence_threshold: 0.7,
    ai_available: false,
    notice: 'AI suggestions are not configured',
    ...overrides,
  }
}

function lowResult(): RegulatoryBasisSuggestResponse {
  return {
    candidates: [LOW],
    needs_clarification: true,
    clarifying_questions: [
      { id: 'topic_domain', question: 'Which area?', options: ['Fire'], why: 'x' },
      { id: 'statutory_nature', question: 'Statutory?', options: ['Yes'], why: 'y' },
    ],
    confidence_threshold: 0.7,
    ai_available: true,
    notice: null,
  }
}

describe('regulatoryBasisAssistMachine', () => {
  it('moves idle → suggesting → proposing on high confidence', () => {
    let state = initialAssistState()
    let next = reduce(state, { type: 'SUGGEST' })
    expect(next.state.kind).toBe('suggesting')
    expect(next.effect?.kind).toBe('fetchSuggest')
    next = reduce(next.state, { type: 'RESULT', payload: highResult() })
    expect(next.state.kind).toBe('proposing')
    if (next.state.kind === 'proposing') {
      expect(next.state.selectedCode).toBe('FSO2005')
    }
  })

  it('moves to clarifying when needs_clarification and ≥2 questions', () => {
    let state: AssistState = { kind: 'suggesting', carried: [] }
    const next = reduce(state, { type: 'RESULT', payload: lowResult() })
    expect(next.state.kind).toBe('clarifying')
  })

  it('RESUBMIT is inert with no answers', () => {
    const state: AssistState = {
      kind: 'clarifying',
      questions: lowResult().clarifying_questions,
      answers: {},
      carried: [LOW],
    }
    const next = reduce(state, { type: 'RESUBMIT' })
    expect(next.state).toEqual(state)
    expect(next.effect).toBeUndefined()
  })

  it('SKIP_QUESTIONS keeps carried candidates', () => {
    const state: AssistState = {
      kind: 'clarifying',
      questions: lowResult().clarifying_questions,
      answers: {},
      carried: [LOW],
    }
    const next = reduce(state, { type: 'SKIP_QUESTIONS' })
    expect(next.state.kind).toBe('proposing')
    if (next.state.kind === 'proposing') {
      expect(next.state.candidates).toEqual([LOW])
    }
  })

  it('zero candidates with no questions → empty', () => {
    const next = reduce(
      { kind: 'suggesting', carried: [] },
      {
        type: 'RESULT',
        payload: highResult({ candidates: [], needs_clarification: false }),
      },
    )
    expect(next.state.kind).toBe('empty')
  })

  it('RESET from every state returns idle', () => {
    const states: AssistState[] = [
      { kind: 'idle' },
      { kind: 'suggesting', carried: [] },
      {
        kind: 'proposing',
        candidates: [CANDIDATE],
        selectedCode: 'FSO2005',
        threshold: 0.7,
      },
      {
        kind: 'clarifying',
        questions: [],
        answers: {},
        carried: [],
      },
      { kind: 'empty', notice: 'x' },
      { kind: 'error', message: 'y' },
    ]
    for (const state of states) {
      expect(reduce(state, { type: 'RESET' }).state.kind).toBe('idle')
    }
  })

  it('only ACCEPT yields the accepted effect', () => {
    const proposing: AssistState = {
      kind: 'proposing',
      candidates: [CANDIDATE],
      selectedCode: 'FSO2005',
      threshold: 0.7,
    }
    const events: AssistEvent[] = [
      { type: 'SUGGEST' },
      { type: 'RESULT', payload: highResult() },
      { type: 'FAIL', message: 'x' },
      { type: 'ANSWER', id: 'a', value: 'b' },
      { type: 'RESUBMIT' },
      { type: 'SKIP_QUESTIONS' },
      { type: 'SELECT', code: 'FSO2005' },
      { type: 'DISCARD' },
      { type: 'RESET' },
      { type: 'ACCEPT' },
    ]
    for (const event of events) {
      const next = reduce(proposing, event)
      if (event.type === 'ACCEPT') {
        expect(next.effect?.kind).toBe('accepted')
      } else {
        expect(next.effect?.kind === 'accepted').toBe(false)
      }
    }
  })
})
