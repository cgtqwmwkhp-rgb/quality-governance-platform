import { describe, expect, it } from 'vitest'
import {
  buildGeneratedPackDownload,
  buildPackManifestStubDownload,
} from '../investigationReportHelpers'

describe('investigationReportHelpers', () => {
  it('builds a full JSON export for a freshly generated pack', () => {
    const payload = buildGeneratedPackDownload({
      pack_id: 9,
      pack_uuid: 'uuid-full-1234',
      audience: 'internal_customer',
      investigation_id: 7,
      investigation_reference: 'INV-2026-0007',
      generated_at: '2026-03-05T10:00:00Z',
      content: '{ "sections": [] }',
      redaction_log: [],
      included_assets: [],
      checksum_sha256: 'abc123',
    })

    expect(payload.exportKind).toBe('full_json')
    expect(payload.filename).toContain('INV-2026-0007')
    const parsed = JSON.parse(payload.body) as { export_kind: string; content: string }
    expect(parsed.export_kind).toBe('full_json')
    expect(parsed.content).toBe('{ "sections": [] }')
  })

  it('builds a manifest stub when only pack metadata is available', () => {
    const payload = buildPackManifestStubDownload(
      {
        id: 1,
        generated_at: '2026-03-05T10:00:00Z',
        pack_uuid: 'abcdef1234567890',
        audience: 'external_customer',
        checksum_sha256: 'deadbeef',
      },
      'INV-7',
    )

    expect(payload.exportKind).toBe('manifest_stub')
    expect(payload.filename).toContain('manifest')
    const parsed = JSON.parse(payload.body) as { pack_uuid: string; pdf_note: string }
    expect(parsed.pack_uuid).toBe('abcdef1234567890')
    expect(parsed.pdf_note).toMatch(/PDF/i)
  })
})
