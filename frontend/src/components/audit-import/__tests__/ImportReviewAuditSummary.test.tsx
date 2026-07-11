import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ImportReviewAuditSummary } from '../ImportReviewAuditSummary'

const job = {
  id: 72,
  organization_name: 'Acme Rail Ltd',
  auditor_name: 'Jordan Lee',
  audit_type: 'Surveillance',
  certificate_number: 'CERT-100',
  audit_scope: 'ISO 9001 operations',
  next_audit_date: '2026-12-01',
  provenance_json: {
    site_name: 'Depot A',
    site_address: '1 Track Lane',
  },
}

describe('ImportReviewAuditSummary', () => {
  it('renders organisation, auditor, and site metadata', () => {
    render(<ImportReviewAuditSummary job={job as never} />)

    expect(screen.getByText('Audit Report Summary')).toBeInTheDocument()
    expect(screen.getByText('Acme Rail Ltd')).toBeInTheDocument()
    expect(screen.getByText('Jordan Lee')).toBeInTheDocument()
    expect(screen.getByText('Depot A')).toBeInTheDocument()
  })

  it('returns null when no summary fields are present', () => {
    const { container } = render(
      <ImportReviewAuditSummary job={{ id: 1, provenance_json: {} } as never} />,
    )
    expect(container.firstChild).toBeNull()
  })
})
