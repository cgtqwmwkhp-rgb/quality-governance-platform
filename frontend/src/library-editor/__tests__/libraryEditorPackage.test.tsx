/**
 * WJ-1-M1 — library-editor package contract.
 *
 * Supersedes the WJ-1 scaffold suite: every assertion it made (package marker,
 * chunk id, empty draft, both components render, the package resolves through a
 * dynamic import) is kept here and extended to the mounted behaviour.
 */
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import {
  DocumentBodyPanel,
  EMPTY_NATIVE_DRAFT,
  FrontSheetBand,
  LIBRARY_EDITOR_CHUNK_ID,
  LIBRARY_EDITOR_PACKAGE,
  NativeDraftEditorShell,
  buildFrontSheetBandModel,
} from '../index'
import type { LibraryBodyDocument } from '../index'

const binaryDoc: LibraryBodyDocument = {
  id: 42,
  title: 'IMS 001 Quality Policy',
  reference_number: 'DOC-2026-0042',
  pel_doc_ref: 'PEL-HSEQ-2001',
  cascade_level: 2,
  status: 'approved',
  version: '3.0',
  file_name: 'quality-policy-v3.pdf',
  access_level: 'all_staff',
  is_statutory: true,
  control_status: 'current',
  effective_date: '2026-01-05T00:00:00Z',
  review_date: '2027-01-05T00:00:00Z',
  retention_until: '2032-01-05T00:00:00Z',
  retention_years: 6,
  retention_anchor: 'issue',
  retention_basis: 'Current + superseded 6 years',
}

function renderInRouter(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('library-editor package', () => {
  it('exports a stable package marker, chunk id and empty draft', () => {
    expect(LIBRARY_EDITOR_PACKAGE).toBe('frontend/src/library-editor')
    expect(LIBRARY_EDITOR_CHUNK_ID).toBe('library-native-draft-editor')
    expect(EMPTY_NATIVE_DRAFT.schemaVersion).toBe(1)
    expect(EMPTY_NATIVE_DRAFT.blocks).toEqual([])
  })

  it('resolves DocumentBodyPanel through a dynamic import with a default export', async () => {
    const mod = await import('../DocumentBodyPanel')
    expect(mod.default).toBeTypeOf('function')
    expect(mod.DocumentBodyPanel).toBeTypeOf('function')
  })

  it('renders the Front Sheet for a binary document with real Register metadata', () => {
    renderInRouter(<DocumentBodyPanel document={binaryDoc} />)

    const body = screen.getByTestId('library-document-body')
    expect(body).toHaveAttribute('data-content-format', 'binary')
    expect(screen.getByTestId('library-front-sheet-band')).toBeInTheDocument()
    expect(screen.queryByTestId('library-native-draft-editor-shell')).not.toBeInTheDocument()

    expect(screen.getByTestId('front-sheet-lead-reference')).toHaveTextContent('PEL-HSEQ-2001')
    expect(screen.getByTestId('front-sheet-lead-reference')).toHaveTextContent('DOC-2026-0042')
    expect(screen.getByTestId('front-sheet-issue')).toHaveTextContent('v3.0')
    expect(screen.getByTestId('front-sheet-function')).toHaveTextContent('HSEQ')
    expect(screen.getByTestId('front-sheet-cascade-level')).toHaveTextContent('2')
    expect(screen.getByTestId('front-sheet-access')).toHaveTextContent('all_staff')
    expect(screen.getByTestId('front-sheet-statutory')).toBeInTheDocument()
    expect(screen.getByTestId('front-sheet-control-status')).toHaveTextContent('current')
  })

  it('surfaces the CUT-1 retention policy and the date it produced', () => {
    renderInRouter(<DocumentBodyPanel document={binaryDoc} />)

    expect(screen.getByTestId('front-sheet-retention')).toHaveAttribute(
      'data-policy-resolved',
      'true',
    )
    expect(screen.getByTestId('front-sheet-retention-headline')).toHaveTextContent(
      '6 years from issue',
    )
    expect(screen.getByTestId('front-sheet-retention-detail')).toHaveTextContent('05 Jan 2032')
    expect(screen.getByTestId('front-sheet-retention-basis')).toHaveTextContent(
      'Current + superseded 6 years',
    )
  })

  it('says a pre-CUT-1 document has no recorded policy instead of inventing one', () => {
    renderInRouter(
      <DocumentBodyPanel document={{ id: 7, title: 'Legacy upload', reference_number: 'DOC-7' }} />,
    )

    expect(screen.getByTestId('front-sheet-retention')).toHaveAttribute(
      'data-policy-resolved',
      'false',
    )
    expect(screen.getByTestId('front-sheet-retention-headline')).toHaveTextContent(
      'No retention policy recorded',
    )
    expect(screen.getByTestId('front-sheet-retention-detail')).toHaveTextContent(
      /not permission to dispose/i,
    )
    expect(screen.queryByTestId('front-sheet-retention-basis')).not.toBeInTheDocument()
  })

  it('flags a legal hold and its matter reference on the cover', () => {
    renderInRouter(
      <DocumentBodyPanel
        document={{
          ...binaryDoc,
          legal_hold_active: true,
          legal_matter_reference: 'MATTER-2026-11',
        }}
      />,
    )
    expect(screen.getByTestId('front-sheet-legal-hold')).toHaveTextContent('MATTER-2026-11')
  })

  it('renders the native draft shell only when the register says native', () => {
    renderInRouter(<DocumentBodyPanel document={{ ...binaryDoc, content_format: 'native' }} />)

    expect(screen.getByTestId('library-document-body')).toHaveAttribute(
      'data-content-format',
      'native',
    )
    expect(screen.getByTestId('library-native-draft-editor-shell')).toBeInTheDocument()
    expect(screen.queryByTestId('library-front-sheet-band')).not.toBeInTheDocument()
    expect(screen.getByTestId('library-editor-publish-link')).toHaveAttribute(
      'href',
      '/documents/42?tab=history',
    )
  })

  it('disables draft save and lease while no endpoint serves them, and says so', () => {
    renderInRouter(<NativeDraftEditorShell documentId={42} />)

    expect(screen.getByTestId('library-editor-save-draft')).toBeDisabled()
    expect(screen.getByTestId('library-editor-acquire-lease')).toBeDisabled()
    expect(screen.getByTestId('library-editor-backend-gap')).toHaveTextContent(
      /no draft-content or draft-lease endpoint/i,
    )
    expect(screen.getByTestId('library-editor-lease-state')).toHaveTextContent('No draft lease held')
  })

  it('enables save once a persistence seam is supplied', () => {
    const onSaveDraft = vi.fn()
    renderInRouter(<NativeDraftEditorShell documentId={42} onSaveDraft={onSaveDraft} />)

    const save = screen.getByTestId('library-editor-save-draft')
    expect(save).not.toBeDisabled()
    fireEvent.click(save)
    expect(onSaveDraft).toHaveBeenCalledWith(EMPTY_NATIVE_DRAFT)
  })

  it('carries no WJ-0 waiting copy now that WJ-0 is live', () => {
    const { container } = renderInRouter(<DocumentBodyPanel document={binaryDoc} />)
    expect(screen.queryByTestId('library-editor-waiting-wj0')).not.toBeInTheDocument()
    expect(screen.queryByTestId('front-sheet-scaffold-note')).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/WJ-0/)
    expect(container.textContent).not.toMatch(/scaffold/i)
  })

  it('renders the band from a prebuilt model without touching the document bytes', () => {
    const model = buildFrontSheetBandModel(binaryDoc)
    expect(model.coverageSummary).toBeNull()
    renderInRouter(<FrontSheetBand model={model} />)
    expect(screen.getByTestId('front-sheet-coverage')).toHaveTextContent(/not composed/i)
    expect(screen.getByTestId('front-sheet-format-note')).toHaveTextContent(
      'quality-policy-v3.pdf',
    )
  })
})
