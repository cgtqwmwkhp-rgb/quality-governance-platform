/**
 * L-34 — which body a document gets: Front Sheet (binary) or draft editor (native).
 *
 * `DocumentResponse` does not carry `content_format` yet. That is deliberate for
 * M1: the column and its alembic revision are M2, and ADR-0024 says the legacy
 * estate defaults to `binary` and conversion is an explicit signed act. So the
 * resolver reads the field if it is there and otherwise answers `binary` with a
 * reason that names the gap, rather than guessing from a filename.
 */
import type { LibraryBodyDocument, LibraryContentFormat } from './types'

export type ContentFormatReason =
  /** The API said `native`. */
  | 'api_native'
  /** The API said `binary`. */
  | 'api_binary'
  /** The API served a value this build does not know — treated as binary. */
  | 'api_unrecognised'
  /** The API has no `content_format` field yet (today's estate). */
  | 'api_field_absent'

export interface ContentFormatDecision {
  format: LibraryContentFormat
  reason: ContentFormatReason
}

/** Total: every input returns a decision, and the fallback is never `native`. */
export function resolveLibraryContentFormat(
  document: Pick<LibraryBodyDocument, 'content_format'>,
): ContentFormatDecision {
  const raw =
    typeof document.content_format === 'string' ? document.content_format.trim().toLowerCase() : ''
  if (!raw) return { format: 'binary', reason: 'api_field_absent' }
  if (raw === 'native') return { format: 'native', reason: 'api_native' }
  if (raw === 'binary') return { format: 'binary', reason: 'api_binary' }
  return { format: 'binary', reason: 'api_unrecognised' }
}

/**
 * One line explaining why this body was chosen. Rendered on the page — a reader
 * should never have to guess whether "no editor" means "not native" or "broken".
 */
export function describeContentFormatReason(decision: ContentFormatDecision): string {
  switch (decision.reason) {
    case 'api_native':
      return 'This document is registered as native, so its content is authored here as blocks.'
    case 'api_binary':
      return 'This document is registered as binary. Its bytes are never edited in QGP — revise by replacing the file.'
    case 'api_unrecognised':
      return 'The register reported a content format this build does not recognise. Treated as binary, which never mutates the stored bytes.'
    case 'api_field_absent':
    default:
      return 'Every filed document is binary today — QGP does not yet record a content format (L-34), so its bytes are never edited here. Revise by replacing the file.'
  }
}
