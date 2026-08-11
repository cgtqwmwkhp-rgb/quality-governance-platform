/**
 * WB-1 / L-29 — Document Detail six-layer spine.
 * First page-level coverage for DocumentDetail layer collapse.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DocumentDetail from '../DocumentDetail'

const flagState: Record<string, boolean> = {
  document_graph: false,
  entity_360: false,
}

const mockGet = vi.fn()
const mockListDocumentEvidence = vi.fn()
const mockListThreads = vi.fn()
const mockListImpacts = vi.fn()
const mockListEdges = vi.fn()
const mockListCampaigns = vi.fn()
const mockGetBundle = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      typeof fallback === 'string' ? fallback : key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rd Party', init: () => {} },
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../components/ui/Tabs', () => ({
  Tabs: ({
    children,
    defaultValue,
    ...rest
  }: {
    children: ReactNode
    defaultValue?: string
    'data-testid'?: string
  }) => (
    <div data-testid={rest['data-testid'] ?? 'tabs'} data-default-tab={defaultValue}>
      {children}
    </div>
  ),
  TabsList: ({
    children,
    ...rest
  }: {
    children: ReactNode
    'data-testid'?: string
    className?: string
  }) => (
    <div role="tablist" data-testid={rest['data-testid']}>
      {children}
    </div>
  ),
  TabsTrigger: ({
    children,
    value,
    ...rest
  }: {
    children: ReactNode
    value: string
    'data-testid'?: string
  }) => (
    <button type="button" role="tab" data-value={value} data-testid={rest['data-testid']}>
      {children}
    </button>
  ),
  // Force-mount all panels so layer placement assertions do not depend on Radix.
  TabsContent: ({
    children,
    value,
  }: {
    children: ReactNode
    value: string
  }) => <div data-testid={`tabs-content-${value}`}>{children}</div>,
}))

vi.mock('../../components/DocumentVersionControlBar', () => ({
  DocumentVersionControlBar: () => <div data-testid="version-control-bar-mock" />,
}))

vi.mock('../DocumentRelationshipsPanel', () => ({
  DocumentRelationshipsPanel: () => <div data-testid="relationships-panel-mock" />,
}))

vi.mock('../DocumentCampaignPanel', () => ({
  DocumentCampaignPanel: () => <div data-testid="campaign-panel-mock" />,
}))

vi.mock('../DocumentCampaignResults', () => ({
  DocumentCampaignResults: ({ initialCampaignId }: { initialCampaignId?: number | null }) => (
    <div data-testid="document-campaign-results">
      campaign:{initialCampaignId ?? 'none'}
    </div>
  ),
}))

vi.mock('../../components/graph/DocumentThreadStrip', () => ({
  DocumentThreadStrip: () => <div data-testid="thread-strip-mock" />,
}))

vi.mock('../DocumentRelationshipChips', () => ({
  DocumentRelationshipChips: () => <div data-testid="relationship-chips-mock" />,
}))

vi.mock('../../components/graph/Entity360Strip', () => ({
  Entity360Strip: () => <div data-testid="entity360-connections-strip" />,
}))

vi.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn(),
    patch: vi.fn(),
    defaults: { baseURL: 'https://api.example.test' },
  },
  documentCampaignApi: {
    listCampaigns: (...args: unknown[]) => mockListCampaigns(...args),
    getCampaignOffer: vi.fn().mockResolvedValue({ data: { eligible: false } }),
  },
  documentGraphApi: {
    listEdges: (...args: unknown[]) => mockListEdges(...args),
  },
  entity360Api: {
    getBundle: (...args: unknown[]) => mockGetBundle(...args),
    getDocumentImpact: vi.fn(),
  },
  knowledgeBankApi: {
    listDocumentEvidence: (...args: unknown[]) => mockListDocumentEvidence(...args),
    listThreads: (...args: unknown[]) => mockListThreads(...args),
    listImpacts: (...args: unknown[]) => mockListImpacts(...args),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Request failed',
}))

const libraryDoc = {
  id: 42,
  reference_number: 'DOC-42',
  title: 'IMS Policy',
  file_name: 'policy.pdf',
  file_type: 'pdf',
  document_type: 'policy',
  status: 'published',
  version: '1.0',
}

function renderDetail(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/documents/:id" element={<DocumentDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DocumentDetail seven layers (WB-1 + Preview)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flagState.document_graph = false
    flagState.entity_360 = false
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/v1/documents/42') {
        return Promise.resolve({ data: libraryDoc })
      }
      if (url === '/api/v1/documents/42/versions') {
        return Promise.resolve({
          data: {
            current_version: '1.0',
            status: 'published',
            versions: [],
          },
        })
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
    mockListDocumentEvidence.mockResolvedValue({ data: [] })
    mockListThreads.mockResolvedValue({ data: [] })
    mockListImpacts.mockResolvedValue({ data: [] })
    mockListEdges.mockResolvedValue({ data: { items: [] } })
    mockListCampaigns.mockResolvedValue({ data: [] })
    mockGetBundle.mockResolvedValue({
      data: { complete: true, upstream: [], downstream: [], sources: [] },
    })
  })

  it('renders seven layers in Control→Preview order with flags off', async () => {
    renderDetail('/documents/42')
    await waitFor(() => {
      expect(screen.getByTestId('document-detail-layer-list')).toBeInTheDocument()
    })
    const list = screen.getByTestId('document-detail-layer-list')
    const tabs = within(list).getAllByRole('tab')
    expect(tabs.map((t) => t.getAttribute('data-value'))).toEqual([
      'control',
      'coverage',
      'related',
      'used-by',
      'history',
      'assurance',
      'preview',
    ])
    expect(screen.getByTestId('document-related-graph-off')).toBeInTheDocument()
    expect(mockListEdges).not.toHaveBeenCalled()
  })

  it('still shows seven layers when Doc Graph and Entity360 are on', async () => {
    flagState.document_graph = true
    flagState.entity_360 = true
    renderDetail('/documents/42')
    await waitFor(() => {
      expect(screen.getByTestId('document-detail-layer-list')).toBeInTheDocument()
    })
    const tabs = within(screen.getByTestId('document-detail-layer-list')).getAllByRole('tab')
    expect(tabs).toHaveLength(7)
    expect(screen.getByTestId('relationships-panel-mock')).toBeInTheDocument()
    expect(screen.queryByTestId('document-related-graph-off')).not.toBeInTheDocument()
  })

  it('aliases ?tab=evidence to Coverage and mounts proposed-evidence anchor', async () => {
    renderDetail('/documents/42?tab=evidence')
    await waitFor(() => {
      expect(screen.getByTestId('document-detail-layers')).toHaveAttribute(
        'data-default-tab',
        'coverage',
      )
    })
    expect(screen.getByTestId('proposed-evidence-links')).toBeInTheDocument()
  })

  it('aliases ?tab=campaign-results&campaignId=9 onto Used by with campaign selected', async () => {
    renderDetail('/documents/42?tab=campaign-results&campaignId=9')
    await waitFor(() => {
      expect(screen.getByTestId('document-detail-layers')).toHaveAttribute(
        'data-default-tab',
        'used-by',
      )
    })
    expect(screen.getByTestId('document-campaign-results')).toHaveTextContent('campaign:9')
  })

  it('aliases ?tab=qa onto Assurance with Q&A section present', async () => {
    renderDetail('/documents/42?tab=qa')
    await waitFor(() => {
      expect(screen.getByTestId('document-detail-layers')).toHaveAttribute(
        'data-default-tab',
        'assurance',
      )
    })
    expect(screen.getByTestId('document-assurance-qa')).toBeInTheDocument()
  })

  it('opens Preview as its own layer with reader and next-review notes', async () => {
    renderDetail('/documents/42?tab=preview')
    await waitFor(() => {
      expect(screen.getByTestId('document-detail-layers')).toHaveAttribute(
        'data-default-tab',
        'preview',
      )
    })
    expect(screen.getByTestId('tabs-content-preview')).toBeInTheDocument()
    expect(screen.getByTestId('document-preview-reader')).toBeInTheDocument()
    expect(screen.getByTestId('document-next-review-notes')).toBeInTheDocument()
    expect(screen.getByTestId('document-review-notes-input')).toBeInTheDocument()
    expect(screen.getByTestId('document-control-preview-handoff')).toBeInTheDocument()
  })

  it('mounts Entity360Strip once inside Used by, not in the header', async () => {
    renderDetail('/documents/42')
    await waitFor(() => {
      expect(screen.getByTestId('document-used-by-connections')).toBeInTheDocument()
    })
    const strips = screen.getAllByTestId('entity360-connections-strip')
    expect(strips).toHaveLength(1)
    expect(screen.getByTestId('document-used-by-connections')).toContainElement(strips[0])
  })
})
