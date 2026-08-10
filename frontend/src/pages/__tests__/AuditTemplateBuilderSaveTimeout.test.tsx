import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { BUILDER_SAVE_TIMEOUT_MS } from '../audit-builder/saveConcurrency'

const mockGetTemplate = vi.fn()
const mockUpdateTemplate = vi.fn()
const mockUpdateSection = vi.fn()
const mockUpdateQuestion = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    // Second arg is either a string fallback or an interpolation object; only a
    // string fallback is safe to render.
    t: (key: string, fallback?: unknown) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  auditsApi: {
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    updateTemplate: (...args: unknown[]) => mockUpdateTemplate(...args),
    createTemplate: vi.fn(),
    updateSection: (...args: unknown[]) => mockUpdateSection(...args),
    createSection: vi.fn(),
    updateQuestion: (...args: unknown[]) => mockUpdateQuestion(...args),
    createQuestion: vi.fn(),
    deleteQuestion: vi.fn(),
    deleteSection: vi.fn(),
    publishTemplate: vi.fn(),
  },
  safetyInsightsApi: { themeCases: vi.fn() },
  auditChallengeApi: {},
  lookupsApi: {},
  usersApi: {},
  getApiErrorMessage: () => 'Request failed',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const QUESTION_IDS = [101, 102, 103, 201, 202, 203]

function apiTemplate() {
  const question = (id: number) => ({
    id,
    question_text: `Question ${id}`,
    question_type: 'yes_no',
    is_required: true,
    weight: 1,
    sort_order: id,
  })
  return {
    id: 7,
    name: 'Depot audit',
    version: 3,
    is_published: false,
    category: 'quality',
    scoring_method: 'weighted',
    passing_score: 80,
    created_at: '2026-01-01T00:00:00Z',
    sections: [
      { id: 11, title: 'Vehicle', weight: 1, sort_order: 1, questions: QUESTION_IDS.slice(0, 3).map(question) },
      { id: 12, title: 'Depot', weight: 1, sort_order: 2, questions: QUESTION_IDS.slice(3).map(question) },
    ],
  }
}

/** Axios error as the response interceptor stamps it for a timed-out write. */
function writeTimeoutError() {
  return Object.assign(new Error('timeout of 45000ms exceeded'), {
    code: 'ECONNABORTED',
    isTimeout: true,
    maybeCommitted: true,
    config: { method: 'patch' },
  })
}

async function renderBuilder() {
  const { default: AuditTemplateBuilder } = await import('../AuditTemplateBuilder')
  render(
    <MemoryRouter initialEntries={['/audit-templates/7/edit']}>
      <Routes>
        <Route path="/audit-templates/:templateId/edit" element={<AuditTemplateBuilder />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByDisplayValue('Depot audit')).toBeInTheDocument())
}

function clickSave() {
  fireEvent.click(screen.getByRole('button', { name: 'audit_builder.save' }))
}

describe('AuditTemplateBuilder save timeout handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetTemplate.mockResolvedValue({ data: apiTemplate() })
    mockUpdateTemplate.mockResolvedValue({ data: { id: 7 } })
    mockUpdateSection.mockImplementation(async (id: number) => ({ data: { id } }))
    mockUpdateQuestion.mockImplementation(async (id: number) => ({ data: { id } }))
  })

  it('stops cleanly on a mid-save timeout and says changes may already be saved', async () => {
    mockUpdateQuestion.mockImplementation(async (id: number) => {
      if (id === 102) throw writeTimeoutError()
      return { data: { id } }
    })

    await renderBuilder()
    clickSave()

    const summary = await screen.findByTestId('save-issue-summary')
    await waitFor(() => expect(summary).toHaveTextContent(/Save timed out/i))
    expect(summary).toHaveTextContent(/may already have been saved/i)
    expect(summary).toHaveTextContent(/reload this template/i)
    // The old model shaped a timeout like a validation failure.
    expect(summary).not.toHaveTextContent(/Review the highlighted details/i)
    expect(screen.getByTestId('save-issue-action-0')).not.toHaveTextContent(
      /Review the highlighted details/i,
    )
    // A timeout is not a bad question, so no "Show question" jump is offered.
    expect(screen.queryByTestId('save-issue-show-0')).toBeNull()

    // Save stopped inside the first section: the second section is never touched.
    expect(mockUpdateSection).toHaveBeenCalledTimes(1)
    expect(mockUpdateSection).toHaveBeenCalledWith(11, expect.anything(), {
      timeout: BUILDER_SAVE_TIMEOUT_MS,
    })
    const attempted = mockUpdateQuestion.mock.calls.map((call) => call[0])
    expect(attempted).not.toContain(201)
    expect(attempted.length).toBeLessThanOrEqual(3)

    // Not stuck in a saving state.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'audit_builder.save' })).not.toBeDisabled(),
    )
    expect(screen.queryByTestId('save-progress')).toBeNull()
  })

  it('reports how far the save got so the user knows what to reconcile', async () => {
    // Fail the last question of the second section: everything before it saved.
    mockUpdateQuestion.mockImplementation(async (id: number) => {
      if (id === 203) throw writeTimeoutError()
      return { data: { id } }
    })

    await renderBuilder()
    clickSave()

    const summary = await screen.findByTestId('save-issue-summary')
    await waitFor(() => expect(summary).toHaveTextContent(/Save timed out/i))
    expect(summary).toHaveTextContent(/5 of 6 questions saved/)
  })

  it('sends builder writes with the raised save timeout and a few questions at a time', async () => {
    let inFlight = 0
    let peakInFlight = 0
    const release: Array<() => void> = []
    mockUpdateQuestion.mockImplementation(async (id: number) => {
      inFlight += 1
      peakInFlight = Math.max(peakInFlight, inFlight)
      await new Promise<void>((resolve) => release.push(resolve))
      inFlight -= 1
      return { data: { id } }
    })

    await renderBuilder()
    clickSave()

    // Three question writes are open at once while the save is in flight.
    await waitFor(() => expect(release).toHaveLength(3))
    expect(peakInFlight).toBe(3)
    expect(await screen.findByTestId('save-progress')).toHaveTextContent(/Saving/)

    while (release.length > 0) {
      release.shift()?.()
      await waitFor(() => expect(mockUpdateQuestion).toHaveBeenCalled())
    }

    await waitFor(() => expect(mockUpdateQuestion).toHaveBeenCalledTimes(QUESTION_IDS.length))
    for (const id of QUESTION_IDS) {
      expect(mockUpdateQuestion).toHaveBeenCalledWith(id, expect.anything(), {
        timeout: BUILDER_SAVE_TIMEOUT_MS,
      })
    }
    expect(mockUpdateTemplate).toHaveBeenCalledWith(7, expect.anything(), {
      timeout: BUILDER_SAVE_TIMEOUT_MS,
    })
    expect(screen.queryByTestId('save-issue-banner')).toBeNull()
  })
})
