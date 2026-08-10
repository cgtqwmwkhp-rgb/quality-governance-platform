/**
 * WJ-1-M1 — the pure decisions behind the Detail body.
 *
 * These are the paths where inventing a value would be a governance defect
 * rather than a cosmetic one: guessing `native`, guessing a retention anchor, or
 * turning a missing policy into a disposal date.
 */
import { describe, expect, it } from 'vitest'
import { describeContentFormatReason, resolveLibraryContentFormat } from '../contentFormat'
import { buildFrontSheetBandModel, libraryFunctionCode } from '../frontSheetModel'
import { formatLibraryDate } from '../formatLibraryDate'
import { describeLibraryRetention } from '../retentionDisplay'

describe('resolveLibraryContentFormat (L-34)', () => {
  it('defaults to binary when the API serves no content_format', () => {
    expect(resolveLibraryContentFormat({})).toEqual({
      format: 'binary',
      reason: 'api_field_absent',
    })
    expect(resolveLibraryContentFormat({ content_format: null })).toEqual({
      format: 'binary',
      reason: 'api_field_absent',
    })
    expect(resolveLibraryContentFormat({ content_format: '   ' })).toEqual({
      format: 'binary',
      reason: 'api_field_absent',
    })
  })

  it('reads an explicit format case-insensitively', () => {
    expect(resolveLibraryContentFormat({ content_format: 'NATIVE' }).format).toBe('native')
    expect(resolveLibraryContentFormat({ content_format: ' binary ' }).format).toBe('binary')
  })

  it('never falls back to native on a value it does not recognise', () => {
    const decision = resolveLibraryContentFormat({ content_format: 'docx' })
    expect(decision).toEqual({ format: 'binary', reason: 'api_unrecognised' })
    expect(describeContentFormatReason(decision)).toMatch(/does not recognise/i)
  })

  it('explains every reason it can return', () => {
    for (const value of [undefined, 'native', 'binary', 'docx']) {
      const note = describeContentFormatReason(resolveLibraryContentFormat({ content_format: value }))
      expect(note.length).toBeGreaterThan(0)
    }
  })
})

describe('describeLibraryRetention (CUT-1 / R19)', () => {
  it('reports a resolved issue-anchored policy with its disposal date', () => {
    const display = describeLibraryRetention({
      retention_years: 6,
      retention_anchor: 'issue',
      retention_basis: 'Current + superseded 6 years',
      retention_until: '2032-01-05T00:00:00Z',
    })
    expect(display.policyResolved).toBe(true)
    expect(display.headline).toBe('6 years from issue')
    expect(display.detail).toContain('05 Jan 2032')
    expect(display.basis).toBe('Current + superseded 6 years')
  })

  it('explains why a supersede-anchored policy has no date while current', () => {
    const display = describeLibraryRetention({
      retention_years: 6,
      retention_anchor: 'supersede',
      retention_until: null,
    })
    expect(display.policyResolved).toBe(true)
    expect(display.headline).toBe('6 years from supersede')
    expect(display.detail).toMatch(/clock starts when it is superseded/i)
    expect(display.disposalDate).toBeNull()
  })

  it('never calculates a date for an event anchor or an indefinite rule', () => {
    const event = describeLibraryRetention({ retention_years: 6, retention_anchor: 'event' })
    expect(event.policyResolved).toBe(true)
    expect(event.detail).toMatch(/an event QGP does not hold/i)
    expect(event.disposalDate).toBeNull()

    const indefinite = describeLibraryRetention({ retention_anchor: 'indefinite' })
    expect(indefinite.policyResolved).toBe(true)
    expect(indefinite.headline).toBe('Kept indefinitely')
    expect(indefinite.disposalDate).toBeNull()
  })

  // `resolve_retention_rule` returns EVENT before it checks for a period, so
  // "Life of asset" reaches the API as an anchor with no years. That is a
  // decided policy, not an incomplete one.
  it('treats a period-less event or indefinite policy as decided, not incomplete', () => {
    const event = describeLibraryRetention({
      retention_anchor: 'event',
      retention_basis: 'Life of asset',
    })
    expect(event.policyResolved).toBe(true)
    expect(event.headline).toMatch(/an event QGP does not hold/i)
  })

  it('shows both sides when a no-date rule carries a stored date anyway', () => {
    const display = describeLibraryRetention({
      retention_anchor: 'indefinite',
      retention_until: '2030-06-30T00:00:00Z',
    })
    expect(display.policyResolved).toBe(true)
    expect(display.detail).toMatch(/kept indefinitely/i)
    expect(display.detail).toContain('30 Jun 2030')
    expect(display.detail).toMatch(/the rule, not the stored date, is the authority/i)
  })

  it('calls issue or supersede with no period incomplete, because the period is the rule', () => {
    const display = describeLibraryRetention({ retention_anchor: 'supersede' })
    expect(display.policyResolved).toBe(false)
    expect(display.headline).toBe('Retention policy incomplete')
  })

  it('refuses an anchor this build does not know rather than assuming issue', () => {
    const display = describeLibraryRetention({
      retention_years: 6,
      retention_anchor: 'on_asset_scrapped',
    })
    expect(display.policyResolved).toBe(false)
    expect(display.headline).toBe('Retention policy incomplete')
    expect(display.detail).toContain('on_asset_scrapped')
  })

  it('reports years with no anchor as incomplete, not as years from issue', () => {
    const display = describeLibraryRetention({ retention_years: 40, retention_anchor: null })
    expect(display.policyResolved).toBe(false)
    expect(display.detail).toMatch(/no anchor/i)
  })

  it('names a refused rule as refused and gives no date', () => {
    const display = describeLibraryRetention({
      retention_basis: 'Tacho data 12 months; working time records 2 years',
    })
    expect(display.policyResolved).toBe(false)
    expect(display.headline).toBe('Retention rule not machine-readable')
    expect(display.detail).toMatch(/never a disposal candidate/i)
    expect(display.disposalDate).toBeNull()
  })

  it('flags a legacy date whose policy was deliberately not backfilled', () => {
    const display = describeLibraryRetention({ retention_until: '2030-06-30T00:00:00Z' })
    expect(display.policyResolved).toBe(false)
    expect(display.headline).toBe('Disposal date with no recorded policy')
    expect(display.detail).toMatch(/not backfilled/i)
    expect(display.disposalDate).toBe('30 Jun 2030')
  })

  it('treats an empty row as unknown, not as disposable', () => {
    const display = describeLibraryRetention({})
    expect(display.headline).toBe('No retention policy recorded')
    expect(display.detail).toMatch(/not permission to dispose/i)
    expect(display.disposalDate).toBeNull()
    expect(display.basis).toBeNull()
  })
})

describe('formatLibraryDate', () => {
  it('formats in en-GB regardless of the reader locale', () => {
    expect(formatLibraryDate('2032-01-05T00:00:00Z')).toBe('05 Jan 2032')
  })

  it('returns the raw value rather than "Invalid Date" when it cannot parse', () => {
    expect(formatLibraryDate('not-a-date')).toBe('not-a-date')
    expect(formatLibraryDate('')).toBeNull()
    expect(formatLibraryDate(null)).toBeNull()
  })
})

describe('libraryFunctionCode (R01)', () => {
  it('reads the function out of PEL-<CODE>-<BAND><SEQ>', () => {
    expect(libraryFunctionCode('PEL-HSEQ-2001')).toBe('HSEQ')
    expect(libraryFunctionCode('pel-ops-3014')).toBe('OPS')
  })

  it('keeps a hyphenated function code intact', () => {
    expect(libraryFunctionCode('PEL-HSEQ-ENV-4002')).toBe('HSEQ-ENV')
  })

  it('falls back to the department only when no PEL reference is allocated', () => {
    expect(libraryFunctionCode(null, 'Operations')).toBe('Operations')
    expect(libraryFunctionCode('DOC-2026-0001', 'Operations')).toBe('Operations')
    expect(libraryFunctionCode(null, null)).toBeNull()
  })
})

describe('buildFrontSheetBandModel (L-36)', () => {
  it('leads on the DOC reference when no PEL is allocated', () => {
    const model = buildFrontSheetBandModel({
      id: 9,
      title: '  Spaced title  ',
      reference_number: 'DOC-2026-0009',
    })
    expect(model.leadReference).toBe('DOC-2026-0009')
    expect(model.secondaryReference).toBeNull()
    expect(model.title).toBe('Spaced title')
  })

  it('reports missing fields as null rather than inventing a default', () => {
    const model = buildFrontSheetBandModel({ id: 9, title: 'Bare row' })
    expect(model.issueLabel).toBeNull()
    expect(model.statusLabel).toBeNull()
    expect(model.controlStatusLabel).toBeNull()
    expect(model.accessLevel).toBeNull()
    expect(model.cascadeLevel).toBeNull()
    expect(model.isStatutory).toBe(false)
    expect(model.legalHoldActive).toBe(false)
    expect(model.coverageSummary).toBeNull()
    expect(model.retention.policyResolved).toBe(false)
  })
})
