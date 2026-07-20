import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CustomerAudits from '../CustomerAudits'

const mockListRuns = vi.fn()
const mockListFindings = vi.fn()
const mockRecordsList = vi.fn()

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>()
  return {
    ...actual,
    auditsApi: {
      listRuns: (...args: unknown[]) => mockListRuns(...args),
      listFindings: (...args: unknown[]) => mockListFindings(...args),
    },
    externalAuditRecordsApi: {
      list: (...args: unknown[]) => mockRecordsList(...args),
    },
    default: {
      get: vi.fn(),
      defaults: { baseURL: 'http://localhost' },
    },
  }
})

function renderPage(initialEntry = '/customer-audits') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <CustomerAudits />
    </MemoryRouter>,
  )
}

describe('CustomerAudits programme shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListRuns.mockResolvedValue({ data: { items: [] } })
    mockListFindings.mockResolvedValue({ data: { items: [] } })
    mockRecordsList.mockResolvedValue({ data: { records: [], total: 0 } })
  })

  it('renders programme shell with honest empty state for runs', async () => {
    renderPage()

    expect(await screen.findByTestId('customer-audits-programme')).toBeInTheDocument()
    expect(screen.getByText('No customer audit runs yet')).toBeInTheDocument()
    expect(
      screen.getByText(/not an Achilles or UVDB replacement/i),
    ).toBeInTheDocument()
  })

  it('lists customer assurance runs and downstream hand-offs', async () => {
    mockListRuns.mockResolvedValue({
      data: {
        items: [
          {
            id: 7,
            reference_number: 'AUD-C-007',
            template_id: 1,
            template_version: 1,
            title: 'National Grid Q1 review',
            source_origin: 'customer',
            assurance_scheme: 'Customer Audit',
            external_body_name: 'National Grid',
            status: 'pending_review',
            is_external_audit_import: true,
            scheduled_date: '2026-03-01',
            created_at: '2026-03-01T00:00:00Z',
          },
        ],
      },
    })
    mockListFindings.mockResolvedValue({
      data: {
        items: [
          {
            id: 42,
            reference_number: 'AF-042',
            run_id: 7,
            title: 'NC: training records',
            description: 'Missing evidence',
            severity: 'major',
            finding_type: 'nonconformity',
            status: 'open',
            corrective_action_required: true,
          },
        ],
      },
    })

    renderPage()

    expect(await screen.findByText('AUD-C-007')).toBeInTheDocument()
    expect(screen.getByText('National Grid Q1 review')).toBeInTheDocument()
    expect(screen.getByTestId('customer-audits-downstream-handoffs')).toBeInTheDocument()
    expect(screen.getByTestId('customer-audits-open-capa')).toHaveAttribute(
      'href',
      '/actions?sourceType=audit_finding',
    )
  })

  it('switches to findings section', async () => {
    mockListRuns.mockResolvedValue({
      data: {
        items: [
          {
            id: 7,
            reference_number: 'AUD-C-007',
            template_id: 1,
            template_version: 1,
            source_origin: 'customer',
            status: 'completed',
            created_at: '2026-03-01T00:00:00Z',
          },
        ],
      },
    })
    mockListFindings.mockResolvedValue({
      data: {
        items: [
          {
            id: 42,
            reference_number: 'AF-042',
            run_id: 7,
            title: 'NC: training records',
            description: 'Missing evidence',
            severity: 'major',
            finding_type: 'nonconformity',
            status: 'open',
            corrective_action_required: true,
          },
        ],
      },
    })

    renderPage()
    await screen.findByText('AUD-C-007')

    await userEvent.click(screen.getByTestId('customer-audits-tab-findings'))

    await waitFor(() => {
      expect(screen.getByTestId('customer-audits-section-findings')).toBeInTheDocument()
    })
    expect(screen.getByText('NC: training records')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open CAPA' })).toBeInTheDocument()
  })

  it('shows sources empty state when no linked documents', async () => {
    renderPage()
    await screen.findByTestId('customer-audits-programme')

    await userEvent.click(screen.getByTestId('customer-audits-tab-sources'))

    await waitFor(() => {
      expect(screen.getByText('No source documents linked yet')).toBeInTheDocument()
    })
  })
})
