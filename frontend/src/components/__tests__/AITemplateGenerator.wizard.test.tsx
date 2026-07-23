import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AITemplateGenerator from '../AITemplateGenerator'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { defaultValue?: string; count?: number }) =>
      opts?.defaultValue || key,
  }),
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

describe('AITemplateGenerator wizard', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/gather-brief')) {
          return {
            ok: true,
            json: async () => ({
              brief_id: 'b1',
              purpose: 'risk_audit',
              scopes: ['incidents'],
              case_refs: [],
              asset_hint: '',
              standards: ['ISO 45001'],
              themes: ['Recent incident: cable'],
              upload_summaries: [],
              research_findings: [],
              research_available: false,
              proposed_sections: [{ title: 'Critical controls', rationale: 'risk first' }],
              open_questions: [{ id: 'depth', prompt: 'How deep?' }],
              freeform_notes: '',
              qa_answers: {},
            }),
          }
        }
        return { ok: true, json: async () => ({ results: [] }) }
      }),
    )
  })

  it('gathers a brief from the intent step', async () => {
    render(<AITemplateGenerator onApply={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText('auditBuilder.title')).toBeInTheDocument()
    fireEvent.click(screen.getByText('auditBuilder.actions.gather'))
    await waitFor(() => {
      expect(screen.getByText('auditBuilder.briefThemes')).toBeInTheDocument()
    })
    expect(screen.getByText(/Recent incident: cable/)).toBeInTheDocument()
  })
})
