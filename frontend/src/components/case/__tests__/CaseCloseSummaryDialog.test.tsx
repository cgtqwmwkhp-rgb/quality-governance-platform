import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { CaseCloseSummaryDialog } from '../CaseCloseSummaryDialog'
import { CaseLifecycleControls } from '../CaseLifecycleControls'
import type { CaseClosureValidation } from '../../../api/caseClosureClient'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: string | { defaultValue?: string; [k: string]: unknown }) => {
      if (typeof opts === 'string') return opts
      if (opts?.defaultValue) {
        return String(opts.defaultValue).replace(
          /\{\{(\w+)\}\}/g,
          (_m, name: string) => String(opts[name] ?? ''),
        )
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const getValidation = vi.fn()

vi.mock('../../../api/client', () => ({
  caseClosureApi: {
    getValidation: (...args: unknown[]) => getValidation(...args),
  },
  getApiErrorMessage: (_err: unknown, fallback?: string) => fallback ?? 'Request failed',
}))

function validation(overrides: Partial<CaseClosureValidation> = {}): CaseClosureValidation {
  return {
    can_close: true,
    reasons: [],
    open_work: [],
    open_work_count: 0,
    lessons_present: true,
    summary: {
      case_type: 'incident',
      case_label: 'incident',
      id: 5,
      reference_number: 'INC-5',
      title: 'Struck by load',
      status: 'pending_review',
      target_status: 'closed',
      lessons_learnt: 'Toolbox talk delivered',
      lessons_present: true,
      actions_total: 2,
      actions_complete: 2,
      actions_incomplete: 0,
    },
    ...overrides,
  }
}

describe('CaseCloseSummaryDialog', () => {
  beforeEach(() => {
    getValidation.mockReset()
  })

  it('shows the case summary and confirms with the lessons on screen', async () => {
    getValidation.mockResolvedValue({ data: validation() })
    const onConfirm = vi.fn().mockResolvedValue(undefined)

    render(
      <CaseCloseSummaryDialog
        open
        caseType="incident"
        caseId={5}
        onConfirm={onConfirm}
        onOpenChange={vi.fn()}
        testIdPrefix="incident"
      />,
    )

    await screen.findByText('INC-5')
    expect(screen.getByText('2 of 2 actions complete')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('incident-close-summary-confirm'))

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith({ lessons_learnt: 'Toolbox talk delivered' })
    })
  })

  it('blocks confirm until lessons are typed', async () => {
    getValidation.mockResolvedValue({
      data: validation({
        can_close: false,
        reasons: ['MISSING_LESSONS_LEARNT'],
        lessons_present: false,
        summary: { ...validation().summary, lessons_learnt: null, lessons_present: false },
      }),
    })
    const onConfirm = vi.fn().mockResolvedValue(undefined)

    render(
      <CaseCloseSummaryDialog
        open
        caseType="incident"
        caseId={5}
        onConfirm={onConfirm}
        onOpenChange={vi.fn()}
        testIdPrefix="incident"
      />,
    )

    const confirm = await screen.findByTestId('incident-close-summary-confirm')
    expect(confirm).toBeDisabled()

    fireEvent.change(screen.getByTestId('incident-close-lessons'), {
      target: { value: 'We changed the lift plan' },
    })

    await waitFor(() => expect(confirm).toBeEnabled())
    fireEvent.click(confirm)
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith({ lessons_learnt: 'We changed the lift plan' })
    })
  })

  it('keeps confirm disabled while open actions remain, and names them', async () => {
    getValidation.mockResolvedValue({
      data: validation({
        can_close: false,
        reasons: ['OPEN_ACTIONS_REMAIN'],
        open_work: [
          {
            kind: 'incident_action',
            id: 3,
            reference_number: 'INC-ACT-3',
            title: 'Fit guard',
            status: 'in_progress',
            action_key: 'incident_action:3',
          },
        ],
        open_work_count: 1,
        summary: { ...validation().summary, actions_complete: 1, actions_incomplete: 1 },
      }),
    })

    render(
      <CaseCloseSummaryDialog
        open
        caseType="incident"
        caseId={5}
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
        testIdPrefix="incident"
      />,
    )

    expect(await screen.findByText('INC-ACT-3')).toBeInTheDocument()
    expect(screen.getByTestId('incident-close-summary-confirm')).toBeDisabled()
  })

  it('keeps confirm disabled when the status cannot move to closed, and names the next step', async () => {
    getValidation.mockResolvedValue({
      data: validation({
        can_close: false,
        reasons: ['INVALID_STATE_TRANSITION'],
        transition_allowed: false,
        allowed_next_statuses: ['acknowledged', 'escalated'],
        summary: { ...validation().summary, status: 'received' },
      }),
    })

    render(
      <CaseCloseSummaryDialog
        open
        caseType="complaint"
        caseId={5}
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
        testIdPrefix="complaint"
      />,
    )

    const blocked = await screen.findByTestId('complaint-close-summary-transition-blocked')
    expect(blocked).toHaveTextContent('Received')
    expect(blocked).toHaveTextContent('Acknowledged or Escalated')
    // Lessons are already on the record, so lessons are not what is holding it.
    expect(screen.getByTestId('complaint-close-summary-confirm')).toBeDisabled()
  })

  it('says so plainly when there is no route from this status to closed', async () => {
    getValidation.mockResolvedValue({
      data: validation({
        can_close: false,
        reasons: ['INVALID_STATE_TRANSITION'],
        transition_allowed: false,
        allowed_next_statuses: [],
      }),
    })

    render(
      <CaseCloseSummaryDialog
        open
        caseType="near_miss"
        caseId={5}
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
        testIdPrefix="near-miss"
      />,
    )

    const blocked = await screen.findByTestId('near-miss-close-summary-transition-blocked')
    expect(blocked).toHaveTextContent('No route from this status to closed')
    expect(screen.getByTestId('near-miss-close-summary-confirm')).toBeDisabled()
  })

  it('degrades to its old behaviour on a reason code it does not know', async () => {
    // The dialog never enumerates reason codes, so an unrecognised one must not
    // render blank or silently disable the close. Legality is read from the
    // dedicated field, which an older server simply omits.
    getValidation.mockResolvedValue({
      data: validation({ can_close: false, reasons: ['SOME_FUTURE_REASON'] }),
    })
    const onConfirm = vi.fn().mockResolvedValue(undefined)

    render(
      <CaseCloseSummaryDialog
        open
        caseType="incident"
        caseId={5}
        onConfirm={onConfirm}
        onOpenChange={vi.fn()}
        testIdPrefix="incident"
      />,
    )

    await screen.findByText('INC-5')
    expect(screen.queryByText('SOME_FUTURE_REASON')).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('incident-close-summary-transition-blocked'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('incident-close-summary-confirm')).toBeEnabled()
  })

  it('surfaces a failed readiness check instead of implying the case is ready', async () => {
    getValidation.mockRejectedValue(new Error('boom'))

    render(
      <CaseCloseSummaryDialog
        open
        caseType="incident"
        caseId={5}
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
        testIdPrefix="incident"
      />,
    )

    expect(await screen.findByTestId('incident-close-summary-load-error')).toBeInTheDocument()
    expect(screen.getByTestId('incident-close-summary-confirm')).toBeDisabled()
  })

  it('stays open and re-reads readiness when the API refuses the close', async () => {
    getValidation.mockResolvedValue({ data: validation() })
    const onConfirm = vi.fn().mockRejectedValue(new Error('refused'))
    const onOpenChange = vi.fn()

    render(
      <CaseCloseSummaryDialog
        open
        caseType="incident"
        caseId={5}
        onConfirm={onConfirm}
        onOpenChange={onOpenChange}
        testIdPrefix="incident"
      />,
    )

    fireEvent.click(await screen.findByTestId('incident-close-summary-confirm'))

    await screen.findByTestId('incident-close-summary-error')
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    await waitFor(() => expect(getValidation).toHaveBeenCalledTimes(2))
  })
})

describe('CaseLifecycleControls', () => {
  beforeEach(() => {
    getValidation.mockReset()
    getValidation.mockResolvedValue({ data: validation() })
  })

  it('offers Close on an open case', () => {
    render(
      <CaseLifecycleControls
        caseType="incident"
        caseId={5}
        status="pending_review"
        onClose={vi.fn()}
        onReopen={vi.fn()}
        testIdPrefix="incident"
      />,
    )

    expect(screen.getByTestId('incident-close')).toBeInTheDocument()
    expect(screen.queryByTestId('incident-reopen')).not.toBeInTheDocument()
  })

  it('offers Reopen on a closed case and confirms it', async () => {
    const onReopen = vi.fn().mockResolvedValue(undefined)
    render(
      <CaseLifecycleControls
        caseType="incident"
        caseId={5}
        status="closed"
        onClose={vi.fn()}
        onReopen={onReopen}
        testIdPrefix="incident"
      />,
    )

    fireEvent.click(screen.getByTestId('incident-reopen'))
    fireEvent.click(await screen.findByTestId('incident-reopen-confirm'))

    await waitFor(() => expect(onReopen).toHaveBeenCalled())
  })

  it('treats a near miss CLOSED status as closed despite the uppercase enum', () => {
    render(
      <CaseLifecycleControls
        caseType="near_miss"
        caseId={5}
        status="CLOSED"
        onClose={vi.fn()}
        onReopen={vi.fn()}
        testIdPrefix="near-miss"
      />,
    )

    expect(screen.getByTestId('near-miss-reopen')).toBeInTheDocument()
  })
})
