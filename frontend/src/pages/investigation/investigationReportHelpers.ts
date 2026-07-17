import type {
  CustomerPackSummary,
  GeneratedCustomerPack,
} from '../../api/investigationsClient'

export type PackExportKind = 'full_json' | 'manifest_stub'

export interface PackDownloadPayload {
  filename: string
  body: string
  exportKind: PackExportKind
}

/** Build a downloadable JSON export from a freshly generated pack (full server payload). */
export function buildGeneratedPackDownload(
  pack: GeneratedCustomerPack,
): PackDownloadPayload {
  const ref = pack.investigation_reference.replace(/[^\w-]+/g, '_')
  const stamp = pack.generated_at.slice(0, 10)
  return {
    filename: `investigation-report-${ref}-${stamp}.json`,
    body: JSON.stringify(
      {
        export_kind: 'full_json',
        pdf_note:
          'Branded Plantexpand PDF rendering is a follow-on — this JSON export is the authoritative pack payload today.',
        ...pack,
      },
      null,
      2,
    ),
    exportKind: 'full_json',
  }
}

/** Metadata-only stub when history list has no content payload (GET pack-by-id not exposed). */
export function buildPackManifestStubDownload(
  pack: CustomerPackSummary,
  investigationReference: string,
): PackDownloadPayload {
  const ref = investigationReference.replace(/[^\w-]+/g, '_')
  const stamp = pack.generated_at.slice(0, 10)
  return {
    filename: `investigation-report-${ref}-${pack.pack_uuid.slice(0, 8)}-manifest.json`,
    body: JSON.stringify(
      {
        export_kind: 'manifest_stub',
        pdf_note:
          'Branded PDF export is not wired yet — this manifest stub carries checksum metadata only. Regenerate the report to download the full JSON payload.',
        investigation_reference: investigationReference,
        pack_uuid: pack.pack_uuid,
        audience: pack.audience,
        generated_at: pack.generated_at,
        checksum_sha256: pack.checksum_sha256 ?? null,
      },
      null,
      2,
    ),
    exportKind: 'manifest_stub',
  }
}

/** Trigger a browser download for a pack export payload. */
export function triggerPackDownload(payload: PackDownloadPayload): void {
  const blob = new Blob([payload.body], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = payload.filename
  anchor.rel = 'noopener'
  anchor.click()
  URL.revokeObjectURL(url)
}
