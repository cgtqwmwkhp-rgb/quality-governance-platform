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

const post = vi.fn()
const get = vi.fn()

vi.mock('../../api/client', () => ({
  default: {
    post: (...args: unknown[]) => post(...args),
    get: (...args: unknown[]) => get(...args),
  },
}))

describe('AITemplateGenerator wizard', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
    get.mockResolvedValue({ data: { results: [] } })
    post.mockImplementation(async (url: string) => {
      if (String(url).includes('/gather-brief')) {
        return {
          data: {
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
          },
        }
      }
      return { data: {} }
    })
  })

  it('gathers a brief via shared api client (not SWA-relative fetch)', async () => {
    render(<AITemplateGenerator onApply={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText('auditBuilder.title')).toBeInTheDocument()
    fireEvent.click(screen.getByText('auditBuilder.actions.gather'))
    await waitFor(() => {
      expect(screen.getByText('auditBuilder.briefThemes')).toBeInTheDocument()
    })
    expect(post).toHaveBeenCalledWith(
      '/api/v1/ai-templates/gather-brief',
      expect.objectContaining({ purpose: 'risk_audit' }),
    )
    expect(screen.getByText(/Recent incident: cable/)).toBeInTheDocument()
  })
})
