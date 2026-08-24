import { describe, expect, it } from 'vitest'
import {
  documentRegisterPrimaryRef,
  documentRegisterStatusTone,
  resolveDocumentRegisterHref,
} from '../documentsRegisterHelpers'

describe('resolveDocumentRegisterHref', () => {
  it('prefers list-projection href from href_registry', () => {
    expect(resolveDocumentRegisterHref({ id: 11, href: '/documents/11' })).toBe('/documents/11')
  })

  it('trims href and never returns blank for filed docs', () => {
    expect(resolveDocumentRegisterHref({ id: 42, href: '  /documents/42  ' })).toBe(
      '/documents/42',
    )
  })

  it('falls back to Detail path when href omitted (mirrors document_href)', () => {
    expect(resolveDocumentRegisterHref({ id: 7 })).toBe('/documents/7')
    expect(resolveDocumentRegisterHref({ id: 7, href: null })).toBe('/documents/7')
    expect(resolveDocumentRegisterHref({ id: 7, href: 'nota/path' })).toBe('/documents/7')
  })
})

describe('documentRegisterPrimaryRef', () => {
  it('leads with PEL when present and keeps DOC secondary', () => {
    expect(
      documentRegisterPrimaryRef({
        reference_number: 'DOC-2026-0011',
        pel_doc_ref: 'PEL-01-01-0003',
      }),
    ).toEqual({
      lead: 'PEL-01-01-0003',
      secondary: 'DOC-2026-0011',
      hasPel: true,
    })
  })

  it('falls back to reference_number when PEL absent', () => {
    expect(
      documentRegisterPrimaryRef({
        reference_number: 'DOC-11',
        pel_doc_ref: null,
      }),
    ).toEqual({ lead: 'DOC-11', secondary: null, hasPel: false })
  })
})

describe('documentRegisterStatusTone (L-08 greyscale)', () => {
  it('maps known statuses to greyscale closed variant with distinct icons', () => {
    expect(documentRegisterStatusTone('approved')).toEqual({
      variant: 'closed',
      icon: 'check',
      label: 'approved',
    })
    expect(documentRegisterStatusTone('processing')).toEqual({
      variant: 'closed',
      icon: 'loader',
      label: 'processing',
    })
    expect(documentRegisterStatusTone('pending')).toEqual({
      variant: 'closed',
      icon: 'clock',
      label: 'pending',
    })
    expect(documentRegisterStatusTone('failed')).toEqual({
      variant: 'closed',
      icon: 'alert',
      label: 'failed',
    })
  })

  it('falls back for unknown status without inventing colour', () => {
    expect(documentRegisterStatusTone('weird')).toEqual({
      variant: 'closed',
      icon: 'dot',
      label: 'weird',
    })
    expect(documentRegisterStatusTone(null).variant).toBe('closed')
  })
})
