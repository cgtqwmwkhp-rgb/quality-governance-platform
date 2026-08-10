import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  EMPTY_NATIVE_DRAFT,
  FrontSheetBand,
  LIBRARY_EDITOR_CHUNK_ID,
  LIBRARY_EDITOR_PACKAGE,
  NativeDraftEditorShell,
} from '../index'
import { loadLibraryEditorPackage } from '../loadLibraryEditorPackage'

describe('WJ-1 library-editor scaffold', () => {
  it('exports a stable package marker and empty draft', () => {
    expect(LIBRARY_EDITOR_PACKAGE).toBe('frontend/src/library-editor')
    expect(LIBRARY_EDITOR_CHUNK_ID).toBe('library-native-draft-editor')
    expect(EMPTY_NATIVE_DRAFT.schemaVersion).toBe(1)
    expect(EMPTY_NATIVE_DRAFT.blocks).toEqual([])
  })

  it('renders NativeDraftEditorShell honesty while authoring is off', () => {
    render(<NativeDraftEditorShell documentId={42} />)
    expect(screen.getByTestId('library-native-draft-editor-shell')).toBeInTheDocument()
    expect(screen.getByTestId('library-editor-waiting-wj0')).toHaveTextContent(/WJ-0/)
  })

  it('renders FrontSheetBand stub fields without mutating bytes', () => {
    render(
      <FrontSheetBand
        model={{
          documentId: 7,
          title: 'IMS 001 Quality Policy',
          pelReference: 'PEL-HSEQ-0001',
          issueLabel: 'Issue 3',
          statusLabel: 'CURRENT',
          functionCode: 'HSEQ',
          coverageSummary: null,
        }}
      />,
    )
    expect(screen.getByTestId('library-front-sheet-band')).toBeInTheDocument()
    expect(screen.getByTestId('front-sheet-pel')).toHaveTextContent('PEL-HSEQ-0001')
    expect(screen.getByTestId('front-sheet-scaffold-note')).toHaveTextContent(/L-36/)
  })

  it('loadLibraryEditorPackage resolves the barrel for a future lazy chunk', async () => {
    const mod = await loadLibraryEditorPackage()
    expect(mod.NativeDraftEditorShell).toBeTypeOf('function')
    expect(mod.FrontSheetBand).toBeTypeOf('function')
  })
})
