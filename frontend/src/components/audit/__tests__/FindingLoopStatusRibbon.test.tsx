import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import {
  FindingLoopStatusRibbon,
  isCapaBlockingClose,
} from '../FindingLoopStatusRibbon'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, number>) => {
      const map: Record<string, string> = {
        'audits.findings.loop.title': 'Loop status',
        'audits.findings.loop.complete': 'Loop closed',
        'audits.findings.loop.finding': 'Finding',
        'audits.findings.loop.capa': 'CAPA',
        'audits.findings.loop.risk': 'Risk',
        'audits.findings.loop.capa_loading': 'Loading…',
        'audits.findings.loop.capa_unavailable': 'Status unavailable',
        'audits.findings.loop.capa_missing': 'Not linked',
        'audits.findings.loop.unassigned': 'Unassigned',
        'audits.findings.loop.risk_linked': `Linked (${options?.count ?? 0})`,
        'audits.findings.loop.risk_pending': 'Not linked',
        'audits.findings.loop.gate_hint': 'Finding close is gated',
        'audits.findings.loop.assign_capa': 'Assign CAPA',
        'audits.findings.loop.create_assign_capa': 'Create & assign CAPA',
        'audits.findings.loop.open_capa': 'Open CAPA detail',
        'audits.findings.loop.open_risk': 'Open linked risk',
        'audits.findings.loop.view_risk': 'View risk register',
        'audits.findings.loop.close_finding': 'Close finding',
        'audits.findings.loop.assign_dialog_title': 'Assign CAPA from finding',
        'audits.findings.loop.assign_dialog_body': 'Set assignee',
        'audits.findings.loop.assign_email_label': 'Assignee email',
        'audits.findings.loop.assign_email_required': 'Enter an assignee email.',
        'audits.findings.loop.assign_failed': 'Could not assign CAPA.',
        'audits.findings.loop.assign_submit': 'Save assignee',
        'audits.findings.loop.close_dialog_title': 'Close finding',
        'audits.findings.loop.close_dialog_body': 'Close after CAPA',
        'audits.findings.loop.close_dialog_blocked': 'CAPA still open',
        'audits.findings.loop.verification_note_placeholder': 'Optional note',
        'audits.findings.loop.override_label': 'Supervisor override',
        'audits.findings.loop.override_reason_placeholder': 'Reason…',
        'audits.findings.loop.override_reason_required': 'Override reason is required.',
        'audits.findings.loop.override_required': 'Confirm override',
        'audits.findings.loop.close_failed': 'Could not close',
        'audits.findings.loop.close_submit': 'Close finding',
        'audits.findings.loop.close_with_override': 'Close with override',
        'common.cancel': 'Cancel',
      }
      return map[key] ?? key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('isCapaBlockingClose', () => {
  it('blocks while CAPA is open and clears when completed', () => {
    expect(
      isCapaBlockingClose(
        { id: 1, action_key: 'capa:1', display_status: 'open', status: 'open' },
        'ready',
        true,
      ),
    ).toBe(true)
    expect(
      isCapaBlockingClose(
        { id: 1, action_key: 'capa:1', display_status: 'completed', status: 'closed' },
        'ready',
        true,
      ),
    ).toBe(false)
  })

  it('requires override when CAPA status is unavailable or missing with corrective required', () => {
    expect(isCapaBlockingClose(null, 'unavailable', true)).toBe(true)
    expect(isCapaBlockingClose(null, 'missing', true)).toBe(true)
    expect(isCapaBlockingClose(null, 'missing', false)).toBe(false)
  })
})

describe('FindingLoopStatusRibbon', () => {
  it('renders loop chips and gates close while CAPA is open', async () => {
    const onCloseFinding = vi.fn().mockResolvedValue(undefined)
    const onAssignCapa = vi.fn().mockResolvedValue(undefined)

    render(
      <FindingLoopStatusRibbon
        findingId={501}
        findingStatus="open"
        correctiveActionRequired
        capa={{
          id: 900,
          action_key: 'capa:900',
          display_status: 'open',
          status: 'open',
          assigned_to_email: 'owner@example.com',
        }}
        capaLoadState="ready"
        riskLinked
        riskCount={1}
        onAssignCapa={onAssignCapa}
        onOpenCapa={vi.fn()}
        onOpenRisk={vi.fn()}
        onCloseFinding={onCloseFinding}
      />,
    )

    expect(screen.getByTestId('finding-loop-ribbon-501')).toBeInTheDocument()
    expect(screen.getByTestId('finding-loop-capa-status-501')).toHaveTextContent('open')
    expect(screen.getByTestId('finding-loop-capa-assignee-501')).toHaveTextContent(
      'owner@example.com',
    )
    expect(screen.getByTestId('finding-loop-risk-status-501')).toHaveTextContent('Linked (1)')
    expect(screen.getByTestId('finding-loop-gate-501')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('finding-loop-close-501'))
    expect(screen.getByTestId('finding-loop-close-dialog-501')).toBeInTheDocument()
    expect(screen.getByTestId('finding-loop-close-submit-501')).toBeDisabled()

    fireEvent.click(screen.getByTestId('finding-loop-override-501'))
    fireEvent.change(screen.getByTestId('finding-loop-override-reason-501'), {
      target: { value: 'Supervisor accepted residual risk' },
    })
    fireEvent.click(screen.getByTestId('finding-loop-close-submit-501'))

    await waitFor(() => {
      expect(onCloseFinding).toHaveBeenCalledWith({
        override: true,
        reason: 'Supervisor accepted residual risk',
        note: undefined,
      })
    })
  })

  it('closes without override when CAPA is completed', async () => {
    const onCloseFinding = vi.fn().mockResolvedValue(undefined)

    render(
      <FindingLoopStatusRibbon
        findingId={502}
        findingStatus="open"
        correctiveActionRequired
        capa={{
          id: 901,
          action_key: 'capa:901',
          display_status: 'completed',
          status: 'closed',
        }}
        capaLoadState="ready"
        riskLinked={false}
        riskCount={0}
        onAssignCapa={vi.fn()}
        onOpenCapa={vi.fn()}
        onOpenRisk={vi.fn()}
        onCloseFinding={onCloseFinding}
      />,
    )

    expect(screen.queryByTestId('finding-loop-gate-502')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('finding-loop-close-502'))
    fireEvent.click(screen.getByTestId('finding-loop-close-submit-502'))

    await waitFor(() => {
      expect(onCloseFinding).toHaveBeenCalledWith({
        override: false,
        reason: undefined,
        note: undefined,
      })
    })
  })
})
