import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RegulatoryBasisAssist } from '../RegulatoryBasisAssist'

const { mockSuggest, mockClarify, flagValues } = vi.hoisted(() => ({
  mockSuggest: vi.fn(),
  mockClarify: vi.fn(),
  flagValues: {
    compliance_schedule: true,
    compliance_schedule_regulatory_ai: true,
  } as Record<string, boolean>,
}))

vi.mock('../../../api/client', () => ({
  complianceScheduleApi: {
    suggestRegulatoryBasis: mockSuggest,
    clarifyRegulatoryBasis: mockClarify,
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (name: string) => flagValues[name] ?? false,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: unknown) => (typeof fallback === 'string' ? fallback : _key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const CANDIDATE = {
  label: 'Regulatory Reform (Fire Safety) Order 2005',
  regulation_or_standard_code: 'FSO2005',
  standard_id: 12,
  clause_ids: [3],
  confidence: 0.93,
  rationale: 'Matched curated UK regulation map (FSO2005).',
  source: 'curated_uk_map',
}

describe('RegulatoryBasisAssist', () => {
  beforeEach(() => {
    mockSuggest.mockReset()
    mockClarify.mockReset()
    flagValues.compliance_schedule = true
    flagValues.compliance_schedule_regulatory_ai = true
  })

  it('hides the button when either flag is off', () => {
    flagValues.compliance_schedule_regulatory_ai = false
    const { rerender } = render(
      <RegulatoryBasisAssist
        title="Fire Risk Assessment"
        taxonomyId="03.01"
        description=""
        statutory
        onAccept={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('regulatory-basis-suggest-button')).toBeNull()

    flagValues.compliance_schedule = false
    flagValues.compliance_schedule_regulatory_ai = true
    rerender(
      <RegulatoryBasisAssist
        title="Fire Risk Assessment"
        taxonomyId="03.01"
        description=""
        statutory
        onAccept={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('regulatory-basis-suggest-button')).toBeNull()
  })

  it('lists candidates without touching form until Accept', async () => {
    const onAccept = vi.fn()
    mockSuggest.mockResolvedValue({
      data: {
        candidates: [CANDIDATE],
        needs_clarification: false,
        clarifying_questions: [],
        confidence_threshold: 0.7,
        ai_available: false,
        notice: 'AI suggestions are not configured in this environment.',
      },
    })

    const user = userEvent.setup()
    render(
      <RegulatoryBasisAssist
        title="Fire Risk Assessment"
        taxonomyId="03.01"
        description=""
        statutory
        onAccept={onAccept}
      />,
    )

    await user.click(screen.getByTestId('regulatory-basis-suggest-button'))
    await waitFor(() => {
      expect(screen.getByTestId('regulatory-basis-candidate-FSO2005')).toBeInTheDocument()
    })
    expect(screen.getByTestId('regulatory-basis-notice')).toHaveTextContent('not configured')
    expect(onAccept).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('regulatory-basis-accept'))
    await waitFor(() => {
      expect(onAccept).toHaveBeenCalledWith(
        expect.objectContaining({
          regulation_or_standard_code: 'FSO2005',
          standard_id: 12,
          label: CANDIDATE.label,
        }),
      )
    })
  })

  it('clarify questions re-submit hits /clarify', async () => {
    mockSuggest.mockResolvedValue({
      data: {
        candidates: [{ ...CANDIDATE, confidence: 0.5 }],
        needs_clarification: true,
        clarifying_questions: [
          { id: 'topic_domain', question: 'Which area?', options: ['Fire safety'], why: 'x' },
          { id: 'statutory_nature', question: 'Statutory?', options: ['Yes'], why: 'y' },
        ],
        confidence_threshold: 0.7,
        ai_available: true,
        notice: null,
      },
    })
    mockClarify.mockResolvedValue({
      data: {
        candidates: [CANDIDATE],
        needs_clarification: false,
        clarifying_questions: [],
        confidence_threshold: 0.7,
        ai_available: true,
        notice: null,
      },
    })

    const user = userEvent.setup()
    render(
      <RegulatoryBasisAssist
        title="Annual review"
        taxonomyId="03.01"
        description=""
        statutory
        onAccept={vi.fn()}
      />,
    )

    await user.click(screen.getByTestId('regulatory-basis-suggest-button'))
    await waitFor(() => {
      expect(screen.getByTestId('regulatory-basis-clarify')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByTestId('regulatory-basis-question-topic_domain'), 'Fire safety')
    await user.click(screen.getByTestId('regulatory-basis-resubmit'))

    await waitFor(() => {
      expect(mockClarify).toHaveBeenCalled()
    })
    expect(mockClarify.mock.calls[0][0].answers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ question_id: 'topic_domain', answer: 'Fire safety' }),
      ]),
    )
  })

  it('API failure shows error and does not call onAccept', async () => {
    const onAccept = vi.fn()
    mockSuggest.mockRejectedValue(new Error('upstream unavailable'))

    const user = userEvent.setup()
    render(
      <RegulatoryBasisAssist
        title="Fire Risk Assessment"
        taxonomyId="03.01"
        description=""
        statutory
        onAccept={onAccept}
      />,
    )

    await user.click(screen.getByTestId('regulatory-basis-suggest-button'))
    await waitFor(() => {
      expect(screen.getByTestId('regulatory-basis-error')).toHaveTextContent('upstream unavailable')
    })
    expect(onAccept).not.toHaveBeenCalled()
  })
})
