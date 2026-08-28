/**
 * PX-242: after auto-advance the pointer stays over the same screen position,
 * so the *next* question's button was under the cursor. Its hover style used
 * the same colour family as the selected style (and at a higher opacity), so an
 * unanswered question looked answered.
 *
 * The fix is a selected state that hover cannot imitate, plus `aria-pressed` so
 * the answer is exposed programmatically rather than by colour alone.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuditExecution from '../AuditExecution'

const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    startRun: vi.fn().mockResolvedValue({ data: {} }),
    completeRun: vi.fn(),
    createResponse: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    updateResponse: vi.fn().mockResolvedValue({ data: { id: 1 } }),
  },
  evidenceAssetsApi: {
    upload: vi.fn(),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    getSignedUrl: vi.fn(),
    getContent: vi.fn().mockResolvedValue({ data: new Blob(['photo-bytes']) }),
    delete: vi.fn(),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Request failed',
}))

const run = {
  id: 41,
  reference_number: 'AUD-00041',
  template_id: 11,
  template_version: 1,
  title: 'Warehouse inspection',
  location: 'London',
  status: 'in_progress',
  responses: [],
  findings: [],
  completion_percentage: 0,
  created_at: '2026-03-24T10:05:00Z',
}

const template = {
  id: 11,
  name: 'Warehouse inspection',
  audit_type: 'internal',
  version: 1,
  scoring_method: 'percentage',
  allow_offline: false,
  require_gps: false,
  require_signature: false,
  require_approval: false,
  auto_create_findings: true,
  is_active: true,
  is_published: true,
  sections: [
    {
      id: 5,
      title: 'Section A',
      is_active: true,
      sort_order: 1,
      questions: [
        {
          id: 1,
          question_text: 'Are fire exits clear?',
          question_type: 'yes_no',
          is_required: true,
          is_active: true,
          sort_order: 1,
          weight: 1,
          failure_triggers_action: false,
        },
        {
          id: 2,
          question_text: 'Is PPE available?',
          question_type: 'yes_no',
          is_required: true,
          is_active: true,
          sort_order: 2,
          weight: 1,
          failure_triggers_action: false,
        },
      ],
    },
  ],
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/audits/41/execute']}>
      <Routes>
        <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuditExecution answer highlight (PX-242)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetRunDetail.mockResolvedValue({ data: run })
    mockGetTemplate.mockResolvedValue({ data: template })
  })

  it('exposes the selected answer programmatically, not by colour alone', async () => {
    renderPage()

    const yes = await screen.findByRole('button', { name: 'YES' })
    expect(yes).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'NO' })).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(yes)
    expect(yes).toHaveAttribute('aria-pressed', 'true')
  })

  it('carries no selection into the next question after auto-advance', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'YES' }))

    await screen.findByText('Is PPE available?', {}, { timeout: 2000 })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'YES' })).toHaveAttribute('aria-pressed', 'false')
    })
    expect(screen.getByRole('button', { name: 'NO' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'YES' })).toHaveAttribute('data-selected', 'false')
  })

  it('hover styling cannot imitate the selected styling', async () => {
    renderPage()

    const yes = await screen.findByRole('button', { name: 'YES' })
    const unselectedClasses = yes.className

    // Hover on an unanswered button must stay colour-neutral: no success/danger
    // tint that could read as "already answered".
    expect(unselectedClasses).toContain('hover:bg-muted')
    expect(unselectedClasses).not.toMatch(/hover:bg-(success|destructive|warning)/)

    fireEvent.click(yes)

    const selectedClasses = screen.getByRole('button', { name: 'YES' }).className
    // Selected is a solid fill plus a ring — not a translucent tint that a hover
    // could reproduce.
    expect(selectedClasses).toContain('bg-success')
    expect(selectedClasses).not.toContain('bg-success/20')
    expect(selectedClasses).toContain('ring-2')
  })
})
