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

/**
 * Build a downloadable JSON export from a freshly generated pack (full server payload).
 *
 * The PDF is the client deliverable; this JSON is kept as the machine-readable record of
 * exactly what was issued, including the redaction log the PDF only summarises.
 */
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
          'The issuable document is the PDF (Download PDF on the Report tab). This JSON is the full machine-readable pack payload, including the complete redaction log.',
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
  return {
    filename: `investigation-report-${ref}-${pack.pack_uuid.slice(0, 8)}-manifest.json`,
    body: JSON.stringify(
      {
        export_kind: 'manifest_stub',
        pdf_note:
          'Checksum metadata only. Use Download PDF for the issuable document, or regenerate the report for the full JSON payload.',
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

/** Filename for a customer pack PDF, matching the server's Content-Disposition. */
export function packPdfFilename(
  investigationReference: string,
  packUuid: string,
): string {
  const ref = investigationReference.replace(/[^\w-]+/g, '_')
  return `investigation-report-${ref}-${packUuid.slice(0, 8)}.pdf`
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  anchor.click()
  URL.revokeObjectURL(url)
}

/** Trigger a browser download for a pack export payload. */
export function triggerPackDownload(payload: PackDownloadPayload): void {
  triggerBlobDownload(
    new Blob([payload.body], { type: 'application/json;charset=utf-8' }),
    payload.filename,
  )
}

/** Trigger a browser download for pack PDF bytes returned by the API. */
export function triggerPackPdfDownload(pdf: Blob, filename: string): void {
  triggerBlobDownload(new Blob([pdf], { type: 'application/pdf' }), filename)
}
