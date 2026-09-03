/**
 * AUD-P3 — a field technician must be able to run an audit on the phone they
 * actually carry, without a second execute shell.
 *
 * `MobileAuditExecution` was deleted by AUD-F1 and the live route is
 * `AuditExecution`, so the fix has to be in this page or it does not exist.
 * The last case in this file fails if a second execute page reappears.
 *
 * What jsdom can and cannot prove, stated plainly because it decides what
 * these tests are worth:
 *
 * - It *can* prove there is no width-conditional branch that drops a control.
 *   That is the regression these cases guard: a `{!isMobile && <Next/>}` or a
 *   camera-only capture row would fail here.
 * - It *can* prove the keyboard-inset contract end to end — that this page
 *   measures the overlap, and that `index.css` actually consumes what it
 *   publishes. Both halves are asserted; the hook's arithmetic is pinned in
 *   `hooks/__tests__/useKeyboardInset.test.ts`.
 * - It *cannot* prove the absence of visual overflow or clipping. jsdom runs
 *   no layout and compiles no Tailwind, so `toBeVisible()` here means "not
 *   hidden in the DOM", not "on screen at 390 px". Real clipping needs a
 *   browser at a real viewport.
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AuditExecution from '../AuditExecution'
import { KEYBOARD_INSET_VAR } from '../../hooks/useKeyboardInset'
import {
  ensureDeviceLedgerDurability,
  putCaptureBlob,
  saveAuditDraft,
  type DeviceLedgerStatus,
} from '../../services/auditDraftStore'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    startRun: vi.fn().mockResolvedValue({ data: {} }),
    acknowledgeRun: vi.fn().mockResolvedValue({ data: {} }),
    createResponse: vi.fn(),
    updateResponse: vi.fn(),
    upsertByQuestion: vi.fn().mockResolvedValue({ data: { id: 7 } }),
    completeRun: vi.fn(),
    uploadQuestionEvidence: vi.fn().mockResolvedValue({
      data: { evidence_asset_id: 501, response_id: 7, evidence_asset_ids: [501] },
    }),
  },
  evidenceAssetsApi: {
    upload: vi.fn(),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    getSignedUrl: vi.fn(),
    getContent: vi.fn().mockResolvedValue({ data: new Blob(['photo-bytes']) }),
    delete: vi.fn().mockResolvedValue({}),
  },
  getApiErrorMessage: (error: unknown, fallback?: string) =>
    error instanceof Error ? error.message : (fallback ?? 'Request failed'),
}))

const DURABLE: DeviceLedgerStatus = {
  durable: true,
  reason: 'ok',
  writeFailed: false,
  usageBytes: null,
  quotaBytes: null,
}

vi.mock('../../services/auditDraftStore', () => ({
  registerDraftSnapshot: vi.fn(() => () => {}),
  getAuditDraft: vi.fn().mockResolvedValue(null),
  deleteAuditDraft: vi.fn(),
  saveAuditDraft: vi.fn().mockResolvedValue({ ok: true }),
  putCaptureBlob: vi.fn().mockResolvedValue({ ok: true }),
  deleteCaptureBlob: vi.fn().mockResolvedValue(undefined),
  listCaptureBlobs: vi.fn().mockResolvedValue([]),
  ensureDeviceLedgerDurability: vi.fn(),
  subscribeDeviceLedgerStatus: vi.fn(() => () => {}),
  getDeviceLedgerStatus: vi.fn(() => DURABLE),
}))

vi.mock('../../services/deviceLedgerIdentity', () => ({
  primeDeviceLedgerIdentity: vi.fn().mockResolvedValue({ tenantId: 7, userId: 5 }),
}))

const RUN_ID = 42

type FixtureQuestion = {
  id: number
  text: string
  /** Backend `question_type`, mapped by `mapBackendQuestionType`. */
  type: string
  required?: boolean
}

function mockRun(questions: FixtureQuestion[]) {
  mockGetRunDetail.mockResolvedValue({
    data: {
      id: RUN_ID,
      reference_number: 'AUD-2026-0091',
      template_id: 12,
      template_version: 1,
      title: 'Depot walk',
      status: 'in_progress',
      responses: [],
      findings: [],
      completion_percentage: 0,
      created_at: '2026-09-03T09:00:00Z',
    },
  })
  mockGetTemplate.mockResolvedValue({
    data: {
      id: 12,
      name: 'Depot walk',
      audit_type: 'internal',
      version: 1,
      scoring_method: 'percentage',
      allow_offline: false,
      require_gps: false,
      require_signature: false,
      require_approval: false,
      is_active: true,
      is_published: true,
      sections: [
        {
          id: 6,
          title: 'Guarding',
          is_active: true,
          sort_order: 1,
          questions: questions.map((question, index) => ({
            id: question.id,
            question_text: question.text,
            question_type: question.type,
            is_required: question.required ?? false,
            is_active: true,
            sort_order: index + 1,
            weight: 1,
          })),
        },
      ],
    },
  })
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={[`/audits/${RUN_ID}/execute`]}>
      <Routes>
        <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
      </Routes>
    </MemoryRouter>,
  )
}

type FakeViewport = {
  height: number
  offsetTop: number
  addEventListener: (type: string, fn: () => void) => void
  removeEventListener: (type: string, fn: () => void) => void
  emit: (type: string) => void
}

/**
 * Put the window at a device size and give it a visual viewport, which jsdom
 * does not implement. Height is the layout viewport; the fake starts with the
 * keyboard closed.
 */
function setViewport(width: number, height: number): FakeViewport {
  const listeners = new Map<string, Set<() => void>>()
  const viewport: FakeViewport = {
    height,
    offsetTop: 0,
    addEventListener(type, fn) {
      const set = listeners.get(type) ?? new Set()
      set.add(fn)
      listeners.set(type, set)
    },
    removeEventListener(type, fn) {
      listeners.get(type)?.delete(fn)
    },
    emit(type) {
      for (const fn of listeners.get(type) ?? []) fn()
    },
  }
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: height })
  Object.defineProperty(window, 'visualViewport', { configurable: true, value: viewport })
  return viewport
}

function insetVar(): string {
  return document.documentElement.style.getPropertyValue(KEYBOARD_INSET_VAR)
}

/** In the document, not `display: none`, and not hidden by an ancestor. */
function expectUsable(element: HTMLElement) {
  expect(element).toBeInTheDocument()
  expect(window.getComputedStyle(element).display).not.toBe('none')
  expect(element).toBeVisible()
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(ensureDeviceLedgerDurability).mockResolvedValue(DURABLE)
  vi.mocked(saveAuditDraft).mockResolvedValue({ ok: true })
  vi.mocked(putCaptureBlob).mockResolvedValue({ ok: true })
})

afterEach(() => {
  Object.defineProperty(window, 'visualViewport', { configurable: true, value: undefined })
  document.documentElement.style.removeProperty(KEYBOARD_INSET_VAR)
})

describe.each([
  ['iPhone 12/13/14 at 390x844', 390, 844],
  ['small tablet at 768x1024', 768, 1024],
])('AuditExecution at %s (AUD-P3)', (_label, width, height) => {
  it('keeps the answer control, both capture routes and the action row reachable', async () => {
    setViewport(width, height)
    mockRun([
      { id: 151, text: 'Photograph the guarding', type: 'photo' },
      { id: 152, text: 'Is the guarding in place?', type: 'yes_no', required: true },
    ])
    renderPage()

    expect(await screen.findByText('Photograph the guarding')).toBeInTheDocument()

    // Next, not an auto-advance type, so the action row carries the advance.
    expectUsable(screen.getByRole('button', { name: /^Next$/ }))
    expectUsable(screen.getByRole('button', { name: 'Previous question' }))
    // AUD-F5: both capture routes survive at phone width. A camera-only row is
    // useless to an auditor photographing evidence before they reach the site.
    expectUsable(screen.getByRole('button', { name: 'Take photo' }))
    expectUsable(screen.getByRole('button', { name: 'Choose photo from library' }))
    // Progress has to stay legible, not just present.
    expectUsable(screen.getByText(/Progress: 0\/2 questions/))
    expectUsable(within(screen.getByRole('navigation', { name: 'Question progress' })).getByText('1 / 2'))
    // AUD-F6 banners share the pane; a durable device says nothing.
    expect(screen.queryByTestId('device-ledger-write-failed')).not.toBeInTheDocument()
  })

  it('lifts the fixed action row when the virtual keyboard opens', async () => {
    const viewport = setViewport(width, height)
    mockRun([{ id: 153, text: 'Describe the defect', type: 'text', required: true }])
    renderPage()

    expect(await screen.findByText('Describe the defect')).toBeInTheDocument()
    await waitFor(() => expect(insetVar()).toBe('0px'))

    // iOS keeps the layout viewport at full height and shrinks only this, which
    // is what leaves a `bottom: 0` action row behind the keyboard.
    viewport.height = height - 336
    viewport.emit('resize')

    await waitFor(() => expect(insetVar()).toBe('336px'))

    viewport.height = height
    viewport.emit('resize')
    await waitFor(() => expect(insetVar()).toBe('0px'))
  })
})

describe('AuditExecution keyboard advance (AUD-P3)', () => {
  it('advances from an auto-advance answer on Enter and keeps the answer on the way back', async () => {
    const user = userEvent.setup()
    setViewport(390, 844)
    mockRun([
      { id: 161, text: 'Is the guarding in place?', type: 'yes_no', required: true },
      { id: 162, text: 'Describe the defect', type: 'text', required: true },
    ])
    renderPage()

    expect(await screen.findByText('Is the guarding in place?')).toBeInTheDocument()

    const yes = screen.getByRole('button', { name: 'YES' })
    yes.focus()
    await user.keyboard('{Enter}')

    // AUTO_ADVANCE_TYPES still advance, and still on their own 600ms timer.
    expect(await screen.findByText('Describe the defect')).toBeInTheDocument()

    // Advancing must not be a remount: the answer behind us is still answered.
    await user.click(screen.getByRole('button', { name: 'Previous question' }))
    expect(await screen.findByText('Is the guarding in place?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'YES' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'NO' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText(/Progress: 1\/2 questions/)).toBeInTheDocument()
  })

  it('advances a typed answer on Enter, so the keyboard need not be dismissed to find Next', async () => {
    const user = userEvent.setup()
    setViewport(390, 844)
    mockRun([
      { id: 171, text: 'First note', type: 'text', required: true },
      { id: 172, text: 'Second note', type: 'text', required: true },
    ])
    renderPage()

    expect(await screen.findByText('First note')).toBeInTheDocument()

    const field = screen.getByPlaceholderText('Enter your response...')
    await user.click(field)
    await user.type(field, 'guard plate missing{Enter}')

    expect(await screen.findByText('Second note')).toBeInTheDocument()
  })

  it('refuses to advance a typed answer that has not been given', async () => {
    const user = userEvent.setup()
    setViewport(390, 844)
    mockRun([
      { id: 181, text: 'First note', type: 'text', required: true },
      { id: 182, text: 'Second note', type: 'text', required: true },
    ])
    renderPage()

    expect(await screen.findByText('First note')).toBeInTheDocument()

    // Enter is exactly the Next button, which is disabled here, so it must not
    // become a way past a required question.
    expect(screen.getByRole('button', { name: /^Next$/ })).toBeDisabled()
    const field = screen.getByPlaceholderText('Enter your response...')
    await user.click(field)
    await user.keyboard('{Enter}')

    expect(screen.getByText('First note')).toBeInTheDocument()
    expect(screen.queryByText('Second note')).not.toBeInTheDocument()
  })

  it('never enters the completion flow from the keyboard', async () => {
    const user = userEvent.setup()
    setViewport(390, 844)
    mockRun([{ id: 191, text: 'Only note', type: 'text', required: true }])
    renderPage()

    expect(await screen.findByText('Only note')).toBeInTheDocument()
    // Last visible question, so the action row offers Finish rather than Next.
    expect(screen.getByRole('button', { name: /^Finish$/ })).toBeInTheDocument()

    const field = screen.getByPlaceholderText('Enter your response...')
    await user.click(field)
    await user.type(field, 'all clear{Enter}')

    // Enter drops the keyboard instead, which is what puts Finish back on
    // screen. Completing stays a deliberate tap.
    expect(field).not.toHaveFocus()
    expect(screen.getByText('Only note')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Back to Audits' })).not.toBeInTheDocument()
    const { auditsApi } = await import('../../api/client')
    expect(auditsApi.completeRun).not.toHaveBeenCalled()
  })

  it('leaves Enter alone in a long-text answer, where it is a newline', async () => {
    const user = userEvent.setup()
    setViewport(390, 844)
    mockRun([
      { id: 201, text: 'Describe in detail', type: 'textarea' },
      { id: 202, text: 'Second note', type: 'text', required: true },
    ])
    renderPage()

    expect(await screen.findByText('Describe in detail')).toBeInTheDocument()

    const field = screen.getByPlaceholderText('Enter detailed response...')
    await user.click(field)
    await user.type(field, 'first line{Enter}second line')

    expect(screen.getByText('Describe in detail')).toBeInTheDocument()
    expect(screen.queryByText('Second note')).not.toBeInTheDocument()
    expect(field).toHaveValue('first line\nsecond line')
  })
})

describe('AUD-P3 structural guards', () => {
  /**
   * Vitest serves this module over http, so `import.meta.url` is not a file
   * URL and cannot locate the tree. Resolve from the working directory
   * instead, and prove the resolution before trusting an assertion made from
   * it — a wrong root would make both cases below pass vacuously.
   */
  const srcDir = [
    resolve(process.cwd(), 'src'),
    resolve(process.cwd(), 'frontend/src'),
  ].find((candidate) => existsSync(join(candidate, 'pages/AuditExecution.tsx')))

  it('resolved the source tree it is about to assert over', () => {
    expect(srcDir).toBeTruthy()
  })

  function walk(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) return walk(path)
      return /\.(ts|tsx)$/.test(entry.name) ? [path] : []
    })
  }

  const sourceFiles = srcDir ? walk(srcDir) : []

  it('has no second execute shell', () => {
    // AUD-F1 deleted MobileAuditExecution. Fixing the phone by reviving it is
    // the named kill condition for this slice: two execute shells is how the
    // fail-evidence gate and the device ledger drift apart again.
    expect(sourceFiles.length).toBeGreaterThan(100)
    expect(sourceFiles.filter((path) => /MobileAuditExecution/.test(path))).toEqual([])

    const importers = sourceFiles.filter((path) =>
      /from\s+['"][^'"]*MobileAuditExecution['"]|import\(\s*['"][^'"]*MobileAuditExecution['"]/.test(
        readFileSync(path, 'utf8'),
      ),
    )
    expect(importers).toEqual([])
  })

  it('consumes the published keyboard inset in the fixed field chrome', () => {
    // The other half of the contract the hook test pins. jsdom compiles no
    // Tailwind, so without this the page could publish an inset that nothing
    // reads and every case above would still pass.
    const css = readFileSync(join(srcDir as string, 'index.css'), 'utf8')
    const rule = (selector: string) =>
      css.slice(css.indexOf(selector), css.indexOf('}', css.indexOf(selector)))

    const actionBar = rule('.mobile-action-bar')
    expect(actionBar).toContain(`bottom: var(${KEYBOARD_INSET_VAR}, 0px)`)
    expect(rule('.field-answer-pane')).toContain(`var(${KEYBOARD_INSET_VAR}, 0px)`)
    // A `bottom-0` utility on the same rule would win or lose on source order
    // against the declaration above, so the @apply list must not carry one.
    const applied = actionBar.slice(actionBar.indexOf('@apply'), actionBar.indexOf(';'))
    expect(applied).toContain('fixed')
    expect(applied).not.toMatch(/\bbottom-0\b/)
    // The shell tracks the dynamic viewport, with a `vh` fallback kept first.
    expect(rule('.field-shell')).toContain('min-height: 100dvh')
    expect(rule('.field-shell')).toContain('min-height: 100vh')
  })
})
