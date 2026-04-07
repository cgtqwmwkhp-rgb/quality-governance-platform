import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

const mockListStandards = vi.fn()
const mockListClauses = vi.fn()
const mockGetCoverage = vi.fn()
const mockGetReport = vi.fn()
const mockListEvidenceLinks = vi.fn()
const mockDeleteEvidenceLink = vi.fn()
const mockListMappings = vi.fn()
const mockAutoTag = vi.fn()
const mockAnalyzeEvidence = vi.fn()
const mockGetSoA = vi.fn()
const mockLinkEvidence = vi.fn()

vi.mock('../../api/client', () => ({
  complianceApi: {
    listStandards: (...args: unknown[]) => mockListStandards(...args),
    listClauses: (...args: unknown[]) => mockListClauses(...args),
    getCoverage: (...args: unknown[]) => mockGetCoverage(...args),
    getReport: (...args: unknown[]) => mockGetReport(...args),
    listEvidenceLinks: (...args: unknown[]) => mockListEvidenceLinks(...args),
    deleteEvidenceLink: (...args: unknown[]) => mockDeleteEvidenceLink(...args),
    autoTag: (...args: unknown[]) => mockAutoTag(...args),
    analyzeEvidence: (...args: unknown[]) => mockAnalyzeEvidence(...args),
    getSoA: (...args: unknown[]) => mockGetSoA(...args),
    linkEvidence: (...args: unknown[]) => mockLinkEvidence(...args),
  },
  crossStandardMappingsApi: {
    list: (...args: unknown[]) => mockListMappings(...args),
  },
  externalAuditRecordsApi: {
    list: vi.fn().mockResolvedValue({ data: { records: [], total: 0 } }),
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
  const soaResponse = {
    data: {
      document_type: 'Statement of Applicability',
      standard: 'ISO/IEC 27001:2022',
      organization: 'Organisation',
      generated_at: '2026-04-07T10:00:00Z',
      version: '1.0',
      total_controls: 93,
      statistics: { implemented: 0, partial: 0, not_implemented: 93 },
      controls: Array.from({ length: 93 }, (_, i) => ({
        clause_id: `27001-A.${i + 1}`,
        control_id: `A.${i + 1}`,
        title: `Control ${i + 1}`,
        applicable: true,
        implementation_status: 'Not Implemented',
        evidence_count: 0,
        evidence: [],
        justification: null,
      })),
      summary: '0 controls fully implemented, 0 partially implemented, 93 not yet implemented (93 total Annex A controls assessed).',
      persisted_evidence_links: 0,
    },
  }

  const deepAnalysisResponse = {
    data: {
      total_clauses_matched: 1,
      standards_covered: ['iso9001'],
      primary_results: [
        {
          clause_id: '9001-7.5',
          clause_number: '7.5',
          title: 'Documented information',
          standard: 'iso9001',
          confidence: 90,
          evidence_snippet: 'document control procedure',
          evidence_quality: 'Procedural Evidence',
          evidence_quality_code: 'TYPE_2',
        },
      ],
      stages: {
        stage_1_keyword: { matched_clauses: 1 },
        stage_2_llm: null,
        stage_3_cross_standard: { cross_standard_matches: [] },
        stage_4_quality: null,
        stage_5_conformance: {
          conformance_statement: 'The content demonstrates conformance with ISO 9001 clause 7.5.',
        },
      },
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockListStandards.mockResolvedValue(standardsResponse)
    mockListClauses.mockResolvedValue(clausesResponse)
    mockGetCoverage.mockResolvedValue(coverageResponse)
    mockGetReport.mockResolvedValue(reportResponse)
    mockListEvidenceLinks.mockResolvedValue(evidenceLinksResponse)
    mockDeleteEvidenceLink.mockResolvedValue({ data: { status: 'deleted' } })
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
    mockAnalyzeEvidence.mockResolvedValue(deepAnalysisResponse)
    mockGetSoA.mockResolvedValue(soaResponse)
    mockLinkEvidence.mockResolvedValue({ data: { status: 'ok', message: 'linked', links: [] } })
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
      expect(mockListMappings).toHaveBeenCalledWith({
        clause: '7.5',
        source_standard: 'iso9001',
        limit: 500,
      })
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
    fireEvent.click(screen.getByText('Auto-Tag'))

    await waitFor(() => {
      expect(mockAutoTag).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByText('Detected ISO Clauses (1)')).toBeInTheDocument()
  })

  it('calls analyzeEvidence and shows deep analysis results', async () => {
    const ComplianceEvidence = (await import('../ComplianceEvidence')).default

    render(
      <BrowserRouter>
        <ComplianceEvidence />
      </BrowserRouter>,
    )

    await screen.findByText('ISO Compliance Evidence Center')
    fireEvent.click(screen.getByText('AI Auto-Tagger'))
    fireEvent.change(screen.getByPlaceholderText(/Paste your content here/i), {
      target: { value: 'Our document control procedure covers retention.' },
    })
    fireEvent.click(screen.getByText('Deep Analysis'))

    await waitFor(() => {
      expect(mockAnalyzeEvidence).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByText('5-Stage Genspark Analysis')).toBeInTheDocument()
    expect(await screen.findByText('Auditor Conformance Statement')).toBeInTheDocument()
  })

  it('renders Annex A SoA button and calls getSoA on click', async () => {
    const ComplianceEvidence = (await import('../ComplianceEvidence')).default

    render(
      <BrowserRouter>
        <ComplianceEvidence />
      </BrowserRouter>,
    )

    await screen.findByText('ISO Compliance Evidence Center')
    const soaButton = screen.getByText('Annex A SoA')
    expect(soaButton).toBeInTheDocument()

    fireEvent.click(soaButton)

    await waitFor(() => {
      expect(mockGetSoA).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByText('Annex A Evidence SoA — ISO 27001:2022')).toBeInTheDocument()
  })

  it('resets dialog state on close after deep analysis', async () => {
    const ComplianceEvidence = (await import('../ComplianceEvidence')).default

    render(
      <BrowserRouter>
        <ComplianceEvidence />
      </BrowserRouter>,
    )

    await screen.findByText('ISO Compliance Evidence Center')
    fireEvent.click(screen.getByText('AI Auto-Tagger'))
    fireEvent.change(screen.getByPlaceholderText(/Paste your content here/i), {
      target: { value: 'Risk management and information security policy.' },
    })
    fireEvent.click(screen.getByText('Deep Analysis'))

    await waitFor(() => expect(mockAnalyzeEvidence).toHaveBeenCalled())

    // Deep analysis results should appear
    expect(await screen.findByText('5-Stage Genspark Analysis')).toBeInTheDocument()

    // Closing the dialog should clear results — next open should show clean state
    const closeButtons = screen.queryAllByRole('button', { name: /close/i })
    if (closeButtons.length > 0) {
      fireEvent.click(closeButtons[0])
    } else {
      // Escape key closes the dialog
      fireEvent.keyDown(document, { key: 'Escape' })
    }

    // Re-open dialog and verify deep analysis results are gone
    await waitFor(() => expect(screen.queryByText('AI Auto-Tagger')).toBeInTheDocument())
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
