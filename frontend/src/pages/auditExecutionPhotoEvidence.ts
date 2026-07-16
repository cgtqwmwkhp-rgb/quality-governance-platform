/**
 * Audit-run photo evidence helpers.
 * Photos are stored on the shared evidence-assets spine (source_module=audit)
 * and linked from AuditResponse.response_json.evidence_asset_ids.
 */

export const AUDIT_QUESTION_EVIDENCE_PREFIX = 'audit_question:'

export function auditQuestionEvidenceDescription(questionId: string | number): string {
  return `${AUDIT_QUESTION_EVIDENCE_PREFIX}${questionId}`
}

export function extractEvidenceAssetIds(responseJson: unknown): number[] {
  if (!responseJson || typeof responseJson !== 'object') return []
  const raw = (responseJson as { evidence_asset_ids?: unknown }).evidence_asset_ids
  if (!Array.isArray(raw)) return []
  return raw
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id) && id > 0)
}

export function buildEvidenceResponseJson(assetIds: number[]): {
  evidence_asset_ids: number[]
} {
  return { evidence_asset_ids: [...new Set(assetIds.filter((id) => id > 0))] }
}

export function dataUrlToFile(dataUrl: string, filename: string): File | null {
  const match = /^data:([^;]+);base64,(.+)$/.exec(dataUrl)
  if (!match) return null
  const mime = match[1] || 'image/jpeg'
  const binary = atob(match[2])
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return new File([bytes], filename, { type: mime })
}
