import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuditsNcPanelSlot } from '../workspace/AuditsNcPanelSlot'
import { ActionsPanelSlot } from '../workspace/ActionsPanelSlot'
import type { StandardsCellAggregate } from '../../../api/standardsCellAggregateTypes'

const baseAggregate = (overrides: Partial<StandardsCellAggregate> = {}): StandardsCellAggregate => ({
  framework: '9001',
  clause_number: '7.5',
  catalogue_keys: ['7.5', '9001-7.5'],
  verdict: 'gap',
  cover_blocked: true,
  recurrence_red_flag: true,
  reasons: ['open_nc', 'recurrence'],
  findings: [
    {
      id: 11,
      run_id: 3,
      title: 'Document control gap',
      status: 'open',
      is_nc: true,
      audit_kind: 'mock',
      reference_number: 'AF-11',
      detail_path: '/audits?view=findings&findingId=11',
    },
  ],
  actions: [
    {
      id: 22,
      title: 'Fix filing',
      status: 'open',
      reference_number: 'CA-22',
      detail_path: '/actions/22',
    },
  ],
  risks: [],
  certificates: [],
  evidence: [],
  imported_priors: [],
  summary: {
    open_nc_count: 1,
    closed_nc_count: 1,
    open_action_count: 1,
    risk_count: 0,
    cert_count: 0,
    evidence_count: 0,
    imported_prior_count: 0,
    mock_finding_count: 1,
  },
  ...overrides,
})

describe('Standards workspace live panels (PR-B)', () => {
  it('renders findings with mock label, recurrence flag, and prior upload CTA', () => {
    render(
      <MemoryRouter>
        <AuditsNcPanelSlot
          data={baseAggregate()}
          loading={false}
          error={null}
          clauseNumber="7.5"
          frameworkId="9001"
        />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('workspace-finding-mock-11')).toBeInTheDocument()
    expect(screen.getByTestId('workspace-recurrence-flag')).toBeInTheDocument()
    expect(screen.getByTestId('workspace-prior-outcome-upload')).toHaveAttribute(
      'href',
      '/audits?modal=import',
    )
  })

  it('surfaces open-action cover block', () => {
    render(
      <MemoryRouter>
        <ActionsPanelSlot
          data={baseAggregate()}
          loading={false}
          error={null}
          clauseNumber="7.5"
          frameworkId="9001"
        />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('workspace-actions-cover-block')).toBeInTheDocument()
    expect(screen.getByText(/CA-22/)).toBeInTheDocument()
  })
})
