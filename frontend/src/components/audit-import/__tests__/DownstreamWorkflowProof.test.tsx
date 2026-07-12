import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ExternalAuditPromotionReconciliation } from '../../../api/client'
import {
  DownstreamWorkflowProof,
  isCompleteReconciliation,
} from '../DownstreamWorkflowProof'

function completeReconciliation(
  overrides: Partial<ExternalAuditPromotionReconciliation> = {},
): ExternalAuditPromotionReconciliation {
  return {
    job_id: 42,
    audit_run_id: 7,
    audit_reference: 'AR-7',
    job_status: 'completed',
    canonical_read_model: 'external_audit_import',
    specialist_home: { path: '/audits/7', label: 'Audit run' },
    accepted_total: 3,
    promoted_total: 3,
    accepted_pending_total: 0,
    failed_total: 0,
    failed_drafts: [],
    materialized: {
      audit_findings: 5,
      capa_actions: 2,
      enterprise_risks: 1,
      uvdb_audit_id: 99,
    },
    proof_matrix: [
      { step: 'findings_materialized', status: 'ok', detail: '5 findings live' },
      { step: 'capa_linked', status: 'partial', detail: '2 of 3 CAPA linked' },
      { step: 'risk_register', status: 'none', detail: 'No risks yet' },
      { step: 'uvdb_sync', status: 'ok', detail: 'Synced' },
    ],
    draft_results: [],
    view_links: {
      actions: '/actions?sourceType=audit_finding',
      risk_register: '/risk-register',
      uvdb: '/uvdb/99',
    },
    ...overrides,
  }
}

describe('isCompleteReconciliation', () => {
  it('returns false for null, undefined, or incomplete shapes', () => {
    expect(isCompleteReconciliation(null)).toBe(false)
    expect(isCompleteReconciliation(undefined)).toBe(false)
    expect(
      isCompleteReconciliation({
        ...completeReconciliation(),
        materialized: undefined as unknown as ExternalAuditPromotionReconciliation['materialized'],
      }),
    ).toBe(false)
    expect(
      isCompleteReconciliation({
        ...completeReconciliation(),
        proof_matrix: null as unknown as ExternalAuditPromotionReconciliation['proof_matrix'],
      }),
    ).toBe(false)
    expect(
      isCompleteReconciliation({
        ...completeReconciliation(),
        view_links: null as unknown as ExternalAuditPromotionReconciliation['view_links'],
      }),
    ).toBe(false)
  })

  it('returns true for a complete reconciliation payload', () => {
    expect(isCompleteReconciliation(completeReconciliation())).toBe(true)
  })
})

describe('DownstreamWorkflowProof', () => {
  it('CUJ: renders findings/CAPA/risks counts and proof matrix statuses when complete', () => {
    render(
      <DownstreamWorkflowProof
        reconciliation={completeReconciliation()}
        onNavigate={() => {}}
      />,
    )

    expect(screen.getByText('Downstream Workflow Proof')).toBeInTheDocument()
    expect(screen.getByText('Findings')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('CAPA Actions')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Enterprise Risks')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('Row #99')).toBeInTheDocument()

    expect(screen.getByText('findings materialized')).toBeInTheDocument()
    expect(screen.getByText('capa linked')).toBeInTheDocument()
    expect(screen.getByText('risk register')).toBeInTheDocument()
    expect(screen.getByText('uvdb sync')).toBeInTheDocument()
    expect(screen.getAllByText('ok').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('partial')).toBeInTheDocument()
    expect(screen.getByText('none')).toBeInTheDocument()
    expect(screen.getByText('5 findings live')).toBeInTheDocument()
  })

  it('shows ≤2-click recover next-step when accepted drafts failed promotion', () => {
    render(
      <DownstreamWorkflowProof
        reconciliation={completeReconciliation({
          failed_total: 1,
          failed_drafts: [{ draft_id: 9, title: 'Broken draft', error: 'timeout' }],
        })}
        onNavigate={() => {}}
      />,
    )
    expect(screen.getByTestId('import-review-proof-recover-next')).toHaveTextContent(
      /Open failed draft, then Retry — two clicks to recover/i,
    )
  })

  it('hides recover next-step when no failed drafts', () => {
    render(
      <DownstreamWorkflowProof
        reconciliation={completeReconciliation({ failed_total: 0, failed_drafts: [] })}
        onNavigate={() => {}}
      />,
    )
    expect(screen.queryByTestId('import-review-proof-recover-next')).not.toBeInTheDocument()
  })

  it('returns null when reconciliation is incomplete', () => {
    const incomplete = {
      ...completeReconciliation(),
      materialized: undefined,
    } as unknown as ExternalAuditPromotionReconciliation

    const { container } = render(
      <DownstreamWorkflowProof reconciliation={incomplete} onNavigate={() => {}} />,
    )

    expect(container.firstChild).toBeNull()
    expect(screen.queryByText('Downstream Workflow Proof')).not.toBeInTheDocument()
  })

  it('navigates when view link buttons are clicked', () => {
    const onNavigate = vi.fn()
    render(
      <DownstreamWorkflowProof
        reconciliation={completeReconciliation()}
        onNavigate={onNavigate}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'View Audit Actions' }))
    expect(onNavigate).toHaveBeenCalledWith('/actions?sourceType=audit_finding')

    fireEvent.click(screen.getByRole('button', { name: 'View Audit Risks' }))
    expect(onNavigate).toHaveBeenCalledWith('/risk-register')

    fireEvent.click(screen.getByRole('button', { name: 'View UVDB Sync' }))
    expect(onNavigate).toHaveBeenCalledWith('/uvdb/99')

    fireEvent.click(screen.getByRole('button', { name: 'Open audit-sourced actions' }))
    expect(onNavigate).toHaveBeenCalledWith('/actions?sourceType=audit_finding')

    fireEvent.click(screen.getByRole('button', { name: 'Open import risk triage' }))
    expect(onNavigate).toHaveBeenCalledWith('/risk-register?triage=import')
  })
})
