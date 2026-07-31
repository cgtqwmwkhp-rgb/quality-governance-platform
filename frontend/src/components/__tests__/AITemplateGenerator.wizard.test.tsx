import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AITemplateGenerator, {
  generateErrorDetail,
  isGenerateTimeoutError,
} from '../AITemplateGenerator'

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

const briefPayload = {
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
}

async function advanceToGenerate() {
  render(<AITemplateGenerator onApply={vi.fn()} onClose={vi.fn()} />)
  fireEvent.click(screen.getByText('auditBuilder.actions.gather'))
  await waitFor(() => {
    expect(screen.getByText('auditBuilder.briefThemes')).toBeInTheDocument()
  })
  fireEvent.click(screen.getByText('auditBuilder.actions.continueQa'))
  await waitFor(() => {
    expect(screen.getByText('auditBuilder.qaIntro')).toBeInTheDocument()
  })
  fireEvent.click(screen.getByText('auditBuilder.actions.checkSimilar'))
  await waitFor(() => {
    expect(screen.getByText('auditBuilder.actions.generate')).toBeInTheDocument()
  })
}

describe('isGenerateTimeoutError / generateErrorDetail', () => {
  it('treats ECONNABORTED and message timeouts as timeouts', () => {
    expect(isGenerateTimeoutError({ code: 'ECONNABORTED', message: 'timeout of 210000ms exceeded' })).toBe(
      true,
    )
    expect(isGenerateTimeoutError({ message: 'Request timeout' })).toBe(true)
  })

  it('treats network-without-response as timeout, not bodyful 503', () => {
    expect(isGenerateTimeoutError({ message: 'Network Error' })).toBe(true)
    expect(
      isGenerateTimeoutError({
        message: 'Request failed with status code 503',
        response: { status: 503, data: { detail: 'AI template generation is currently unavailable. Please try again later.' } },
      }),
    ).toBe(false)
  })

  it('prefers response.data.detail text', () => {
    expect(
      generateErrorDetail({
        response: { data: { detail: 'AI template generation is currently unavailable. Please try again later.' } },
      }),
    ).toBe('AI template generation is currently unavailable. Please try again later.')
    expect(generateErrorDetail({ response: { data: {} } })).toBeNull()
  })
})

describe('AITemplateGenerator wizard', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
    get.mockResolvedValue({ data: { results: [] } })
    post.mockImplementation(async (url: string) => {
      if (String(url).includes('/gather-brief')) {
        return { data: briefPayload }
      }
      if (String(url).includes('/apply-qa')) {
        return { data: briefPayload }
      }
      if (String(url).includes('/similar-templates')) {
        return { data: { matches: [], count: 0 } }
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
      expect.any(Object),
    )
    expect(screen.getByText(/Recent incident: cable/)).toBeInTheDocument()
  })

  it('shows backend 503 detail inline and does not claim a browser timeout', async () => {
    const detail = 'AI template generation is currently unavailable. Please try again later.'
    post.mockImplementation(async (url: string) => {
      if (String(url).includes('/gather-brief')) return { data: briefPayload }
      if (String(url).includes('/apply-qa')) return { data: briefPayload }
      if (String(url).includes('/similar-templates')) return { data: { matches: [], count: 0 } }
      if (String(url).includes('/generate-from-brief')) {
        const err = Object.assign(new Error('Request failed with status code 503'), {
          response: { status: 503, data: { detail } },
        })
        throw err
      }
      return { data: {} }
    })

    await advanceToGenerate()
    fireEvent.click(screen.getByText('auditBuilder.actions.generate'))

    await waitFor(() => {
      expect(screen.getByText(detail)).toBeInTheDocument()
    })
    expect(screen.queryByText(/browser timed out/i)).not.toBeInTheDocument()
    expect(post).toHaveBeenCalledWith(
      '/api/v1/ai-templates/generate-from-brief',
      expect.any(Object),
      expect.objectContaining({ timeout: 210000, suppressErrorToast: true }),
    )
  })

  it('shows timeout copy for ECONNABORTED without a response body', async () => {
    post.mockImplementation(async (url: string) => {
      if (String(url).includes('/gather-brief')) return { data: briefPayload }
      if (String(url).includes('/apply-qa')) return { data: briefPayload }
      if (String(url).includes('/similar-templates')) return { data: { matches: [], count: 0 } }
      if (String(url).includes('/generate-from-brief')) {
        const err = Object.assign(new Error('timeout of 210000ms exceeded'), {
          code: 'ECONNABORTED',
        })
        throw err
      }
      return { data: {} }
    })

    await advanceToGenerate()
    fireEvent.click(screen.getByText('auditBuilder.actions.generate'))

    await waitFor(() => {
      expect(screen.getByText(/browser timed out/i)).toBeInTheDocument()
    })
  })
})
