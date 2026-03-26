import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

const mockListStandards = vi.fn()
const mockListClauses = vi.fn()
const mockGetCoverage = vi.fn()
const mockGetReport = vi.fn()
const mockListEvidenceLinks = vi.fn()
const mockListMappings = vi.fn()
const mockAutoTag = vi.fn()

vi.mock('../../api/client', () => ({
  complianceApi: {
    listStandards: (...args: unknown[]) => mockListStandards(...args),
    listClauses: (...args: unknown[]) => mockListClauses(...args),
    getCoverage: (...args: unknown[]) => mockGetCoverage(...args),
    getReport: (...args: unknown[]) => mockGetReport(...args),
    listEvidenceLinks: (...args: unknown[]) => mockListEvidenceLinks(...args),
    autoTag: (...args: unknown[]) => mockAutoTag(...args),
  },
  crossStandardMappingsApi: {
    list: (...args: unknown[]) => mockListMappings(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

const standardsResponse = {
  data: [
    {
      id: 'iso9001',
      code: 'ISO 9001:2015',
      name: 'Quality Management System',
      description: 'QMS',
      clause_count: 1,
      db_standard_id: 1,
      db_standard_code: 'ISO9001',
      db_standard_name: 'ISO 9001:2015',
      db_clause_count: 1,
      ims_requirement_count: 2,
      covered_clauses: 1,
      coverage_percentage: 100,
      has_canonical_standard: true,
      canonical_data_degraded: false,
      canonical_data_message: null,
    },
  ],
}

const clausesResponse = {
  data: [
    {
      id: '9001-7.5',
      standard: 'iso9001',
      clause_number: '7.5',
      title: 'Documented information',
      description: 'Control of documented information',
      keywords: ['documents', 'records'],
      parent_clause: null,
      level: 2,
    },
  ],
}

const coverageResponse = {
  data: {
    total_clauses: 1,
    full_coverage: 1,
    partial_coverage: 0,
    gaps: 0,
    coverage_percentage: 100,
    gap_clauses: [],
    by_standard: {
      iso9001: {
        total: 1,
        covered: 1,
        percentage: 100,
      },
    },
  },
}

const reportResponse = {
  data: {
    generated_at: '2026-03-22T12:00:00Z',
    persisted_evidence_links: 1,
    summary: coverageResponse.data,
    clauses: [
      {
        clause_id: '9001-7.5',
        clause_number: '7.5',
        title: 'Documented information',
        description: 'Control of documented information',
        standard: 'iso9001',
        status: 'full',
        evidence_count: 1,
        evidence: [
          {
            entity_type: 'document',
            entity_id: 'DOC-001',
            linked_by: 'manual',
            confidence: 95,
          },
        ],
      },
    ],
  },
}

const evidenceLinksResponse = {
  data: [
    {
      id: 1,
      entity_type: 'document',
      entity_id: 'DOC-001',
      clause_id: '9001-7.5',
      linked_by: 'manual',
      confidence: 95,
      title: 'Quality policy',
      notes: 'Latest approved version',
      created_at: '2026-03-22T10:00:00Z',
      created_by_email: 'qa@example.com',
    },
  ],
}

const mappingsResponse = {
  data: [
    {
      id: 1,
      primary_standard: 'ISO 9001:2015',
      primary_clause: '7.5',
      mapped_standard: 'ISO 14001:2015',
      mapped_clause: '7.5',
      mapping_type: 'equivalent',
      mapping_strength: 9,
      mapping_notes: 'Shared documented information controls',
      annex_sl_element: 'Support',
    },
  ],
}

describe('ComplianceEvidence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListStandards.mockResolvedValue(standardsResponse)
    mockListClauses.mockResolvedValue(clausesResponse)
    mockGetCoverage.mockResolvedValue(coverageResponse)
    mockGetReport.mockResolvedValue(reportResponse)
    mockListEvidenceLinks.mockResolvedValue(evidenceLinksResponse)
    mockListMappings.mockResolvedValue(mappingsResponse)
    mockAutoTag.mockResolvedValue({
      data: [
        {
          clause_id: '9001-7.5',
          clause_number: '7.5',
          title: 'Documented information',
          standard: 'iso9001',
          confidence: 88,
          linked_by: 'auto',
        },
      ],
    })
  })

  it('renders live compliance evidence and cross-standard mappings', async () => {
    const ComplianceEvidence = (await import('../ComplianceEvidence')).default

    render(
      <BrowserRouter>
        <ComplianceEvidence />
      </BrowserRouter>,
    )

    await screen.findByText('ISO Compliance Evidence Center')

    expect(mockListStandards).toHaveBeenCalledTimes(1)
    expect(mockListClauses).toHaveBeenCalledTimes(1)
    await waitFor(() => {
      expect(mockListMappings).toHaveBeenCalledWith({ clause: '7.5' })
    })

    await waitFor(() => {
      expect(screen.getByText('Quality policy')).toBeInTheDocument()
    })

    expect(screen.getAllByText('Documented information').length).toBeGreaterThan(0)
    expect(screen.getByText('Shared documented information controls')).toBeInTheDocument()
  })

  it('uses the live auto-tag endpoint', async () => {
    const ComplianceEvidence = (await import('../ComplianceEvidence')).default

    render(
      <BrowserRouter>
        <ComplianceEvidence />
      </BrowserRouter>,
    )

    await screen.findByText('ISO Compliance Evidence Center')

    fireEvent.click(screen.getByText('AI Auto-Tagger'))
    fireEvent.change(screen.getByPlaceholderText(/Paste your content here/i), {
      target: { value: 'Our document control procedure covers retention and record management.' },
    })
    fireEvent.click(screen.getByText('Analyze & Auto-Tag'))

    await waitFor(() => {
      expect(mockAutoTag).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByText('Detected ISO Clauses (1)')).toBeInTheDocument()
  })

  it('shows a degraded-mode warning when canonical compliance enrichment is unavailable', async () => {
    mockListStandards.mockResolvedValue({
      data: [
        {
          ...standardsResponse.data[0],
          canonical_data_degraded: true,
          canonical_data_message:
            'Canonical compliance enrichment is temporarily unavailable (OperationalError). Static ISO defaults and persisted evidence coverage are still available.',
        },
      ],
    })

    const ComplianceEvidence = (await import('../ComplianceEvidence')).default

    render(
      <BrowserRouter>
        <ComplianceEvidence />
      </BrowserRouter>,
    )

    expect(await screen.findByText('Compliance data is running in degraded mode')).toBeInTheDocument()
    expect(screen.getByText(/Canonical compliance enrichment is temporarily unavailable/)).toBeInTheDocument()
    expect(screen.getByText(/canonical enrichment degraded/)).toBeInTheDocument()
  })
})
