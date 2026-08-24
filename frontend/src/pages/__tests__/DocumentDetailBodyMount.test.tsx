/**
 * WJ-1-M1 / ADR-0024 — the Detail body mount.
 *
 * Renders the real `library-editor` package through DocumentDetail's dynamic
 * import (it is not mocked here) so the assertions cover the wiring as well as
 * the components, and guards the size-limit contract that keeps the package off
 * the App shell and off the DocumentDetail route chunk.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DocumentDetail from '../DocumentDetail'

const mockGet = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rd Party', init: () => {} },
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: () => false,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

vi.mock('../../components/ui/Tabs', () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div role="tablist">{children}</div>,
  TabsTrigger: ({ children }: { children: ReactNode }) => <button type="button">{children}</button>,
  TabsContent: ({ children, value }: { children: ReactNode; value: string }) => (
    <div data-testid={`tabs-content-${value}`}>{children}</div>
  ),
}))

vi.mock('../../components/DocumentVersionControlBar', () => ({
  DocumentVersionControlBar: () => <div data-testid="version-control-bar-mock" />,
}))

vi.mock('../DocumentRelationshipsPanel', () => ({
  DocumentRelationshipsPanel: () => <div />,
}))

vi.mock('../DocumentCampaignPanel', () => ({
  DocumentCampaignPanel: () => <div />,
}))

vi.mock('../DocumentCampaignResults', () => ({
  DocumentCampaignResults: () => <div />,
}))

vi.mock('../../components/graph/DocumentThreadStrip', () => ({
  DocumentThreadStrip: () => <div />,
}))

vi.mock('../DocumentRelationshipChips', () => ({
  DocumentRelationshipChips: () => <div />,
}))

vi.mock('../../components/graph/Entity360Strip', () => ({
  Entity360Strip: () => <div />,
}))

vi.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn(),
    patch: vi.fn(),
    defaults: { baseURL: 'https://api.example.test' },
  },
  documentCampaignApi: { listCompliance: vi.fn() },
  documentGraphApi: { listEdges: vi.fn() },
  entity360Api: { getDocumentImpact: vi.fn() },
  knowledgeBankApi: {
    listDocumentEvidence: vi.fn().mockResolvedValue({ data: [] }),
    listThreads: vi.fn().mockResolvedValue({ data: [] }),
    listImpacts: vi.fn().mockResolvedValue({ data: [] }),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Request failed',
}))

/** A CUT-1 row as `DocumentResponse` actually serves it. */
const documentResponse = {
  id: 42,
  reference_number: 'DOC-2026-0042',
  pel_doc_ref: 'PEL-HSEQ-2001',
  cascade_level: 2,
  title: 'Health and Safety Policy',
  file_name: 'hs-policy-v3.pdf',
  file_type: 'pdf',
  document_type: 'policy',
  status: 'approved',
  version: '3.0',
  access_level: 'all_staff',
  is_statutory: true,
  control_status: 'current',
  view_count: 1,
  download_count: 0,
  created_at: '2026-01-05T00:00:00Z',
  effective_date: '2026-01-05T00:00:00Z',
  review_date: '2027-01-05T00:00:00Z',
  retention_until: '2032-01-05T00:00:00Z',
  retention_years: 6,
  retention_anchor: 'issue',
  retention_basis: 'Current + superseded 6 years',
}

function renderDetail(document: Record<string, unknown>) {
  mockGet.mockImplementation((url: string) => {
    if (url === '/api/v1/documents/42') return Promise.resolve({ data: document })
    if (url === '/api/v1/documents/42/versions') {
      return Promise.resolve({
        data: { current_version: '3.0', status: 'approved', versions: [] },
      })
    }
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
  return render(
    <MemoryRouter initialEntries={['/documents/42']}>
      <Routes>
        <Route path="/documents/:id" element={<DocumentDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DocumentDetail body mount (WJ-1-M1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('lazily mounts the Front Sheet inside the Control layer', async () => {
    renderDetail(documentResponse)

    const band = await screen.findByTestId('library-front-sheet-band')
    expect(screen.getByTestId('tabs-content-control')).toContainElement(band)
    expect(screen.getByTestId('library-document-body')).toHaveAttribute(
      'data-content-format',
      'binary',
    )
    expect(screen.getByTestId('front-sheet-lead-reference')).toHaveTextContent('PEL-HSEQ-2001')
    expect(screen.getByTestId('front-sheet-issue')).toHaveTextContent('v3.0')
  })

  it('shows the CUT-1 retention policy the API served for this document', async () => {
    renderDetail(documentResponse)

    await screen.findByTestId('front-sheet-retention')
    expect(screen.getByTestId('front-sheet-retention-headline')).toHaveTextContent(
      '6 years from issue',
    )
    expect(screen.getByTestId('front-sheet-retention-detail')).toHaveTextContent('05 Jan 2032')
    expect(screen.getByTestId('front-sheet-retention-basis')).toHaveTextContent(
      'Current + superseded 6 years',
    )
  })

  it('renders the honest absence for a pre-CUT-1 row with no retention columns', async () => {
    const legacy: Record<string, unknown> = { ...documentResponse }
    for (const column of [
      'retention_until',
      'retention_years',
      'retention_anchor',
      'retention_basis',
    ]) {
      delete legacy[column]
    }

    renderDetail(legacy)

    await screen.findByTestId('front-sheet-retention')
    expect(screen.getByTestId('front-sheet-retention')).toHaveAttribute(
      'data-policy-resolved',
      'false',
    )
    expect(screen.getByTestId('front-sheet-retention-headline')).toHaveTextContent(
      'No retention policy recorded',
    )
  })

  it('mounts the native draft shell instead when the register says native', async () => {
    renderDetail({ ...documentResponse, content_format: 'native' })

    await screen.findByTestId('library-native-draft-editor-shell')
    expect(screen.queryByTestId('library-front-sheet-band')).not.toBeInTheDocument()
    expect(screen.getByTestId('library-editor-save-draft')).toBeDisabled()
  })

  it('keeps the rest of the Control layer intact', async () => {
    renderDetail(documentResponse)
    await screen.findByTestId('library-front-sheet-band')
    await waitFor(() => {
      expect(screen.getByTestId('documents-downstream-thread')).toBeInTheDocument()
    })
  })
})

describe('library-editor chunk contract (size-limit)', () => {
  const source = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), '../DocumentDetail.tsx'),
    'utf-8',
  )

  it('reaches the editor package only through a dynamic import', () => {
    const specifiers = source.match(/['"][^'"\n]*library-editor[^'"\n]*['"]/g) ?? []
    expect(specifiers).toEqual(["'../library-editor/DocumentBodyPanel'"])
    expect(source).toContain("lazy(() => import('../library-editor/DocumentBodyPanel'))")
    // A static import would fold the package back into the route chunk, which is
    // what the dedicated size-limit row exists to prevent.
    expect(source).not.toMatch(/^\s*import[^\n]*library-editor/m)
  })
})
