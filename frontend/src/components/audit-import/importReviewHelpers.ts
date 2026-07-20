/**
 * Pure helpers for Audit Import Review (phase 2 extract from AuditImportReview page).
 */
import axios from 'axios'
import {
  createApiError,
  ErrorClass,
  getApiErrorMessage,
  type AuditRunDetail,
  type ExternalAuditImportJob,
} from '../../api/client'

export const ACTION_FINDING_TYPES: readonly string[] = [
  'nonconformity',
  'major_nonconformity',
  'minor_nonconformity',
  'competence_gap',
  'finding',
  'flagged_item',
  'question_answered_no',
] as const

export const RISK_CREATING_SEVERITIES: readonly string[] = ['medium', 'high', 'critical']

export function shouldCreateRisk(finding: {
  finding_type?: string | null
  severity?: string | null
}): boolean {
  const findingType = finding.finding_type?.trim().toLowerCase() ?? ''
  const severity = finding.severity?.trim().toLowerCase() ?? ''
  return (
    ACTION_FINDING_TYPES.includes(findingType) && RISK_CREATING_SEVERITIES.includes(severity)
  )
}

export function humanizeLabel(value: string | null | undefined) {
  if (!value) return ''
  return value.replace(/_/g, ' ')
}

/**
 * Build an import-review workspace path using the real audit run id.
 * Returns null when the run id is missing so callers can hide/disable the link
 * instead of navigating to the broken `/audits/0/...` placeholder.
 */
export function getImportReviewPath(
  auditRunId: number | null | undefined,
  importJobId?: number | null,
): string | null {
  if (auditRunId == null || !Number.isFinite(auditRunId) || auditRunId <= 0) {
    return null
  }
  const params = importJobId != null && Number.isFinite(importJobId) ? `?jobId=${importJobId}` : ''
  return `/audits/${auditRunId}/import-review${params}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return ''
  try {
    return new Intl.DateTimeFormat('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(value))
  } catch {
    return String(value)
  }
}

export function describeReconciliationFailure(error: unknown, jobStatus?: string): string {
  const apiError = createApiError(error)
  if (apiError.error_class === ErrorClass.NOT_FOUND) {
    if (!jobStatus || !['completed', 'promoting'].includes(jobStatus)) {
      return ''
    }
    return 'Downstream workflow diagnostics are unavailable for this job on the current backend.'
  }
  if (apiError.error_class === ErrorClass.VALIDATION_ERROR) {
    return `Downstream workflow diagnostics unavailable: ${getApiErrorMessage(error)}`
  }
  if (apiError.error_class === ErrorClass.SERVER_ERROR) {
    return 'Downstream workflow diagnostics are temporarily unavailable while the backend recovers.'
  }
  return 'Downstream workflow diagnostics could not be loaded right now.'
}

export function describePromotionFailure(error: unknown): string {
  const apiError = createApiError(error)
  if (apiError.error_class === ErrorClass.VALIDATION_ERROR) {
    return getApiErrorMessage(error)
  }
  if (apiError.error_class === ErrorClass.SERVER_ERROR) {
    return 'Promotion is temporarily unavailable while the backend recovers. Please retry shortly.'
  }
  return 'Promotion failed. Review the accepted drafts and try again.'
}

export type PromotionFailedDraftRow = {
  draft_id?: number
  title?: string
  error?: string
  error_type?: string
}

/** Server returns failed_drafts inside error.details on 422 when materialization fails. */
export function extractPromotionFailedDrafts(err: unknown): PromotionFailedDraftRow[] | null {
  if (!axios.isAxiosError(err) || err.response?.status !== 422) return null
  const data = err.response?.data as { error?: { details?: { failed_drafts?: unknown } } } | undefined
  const raw = data?.error?.details?.failed_drafts
  if (!Array.isArray(raw) || raw.length === 0) return null
  return raw.slice(0, 20).map((row: Record<string, unknown>) => ({
    draft_id: typeof row.draft_id === 'number' ? row.draft_id : undefined,
    title: typeof row.title === 'string' ? row.title : undefined,
    error: typeof row.error === 'string' ? row.error : undefined,
    error_type: typeof row.error_type === 'string' ? row.error_type : undefined,
  }))
}

export function readProvenanceString(job: ExternalAuditImportJob | null, key: string) {
  const value = job?.provenance_json?.[key]
  return typeof value === 'string' && value.trim() ? value : null
}

export function readProvenanceNumber(job: ExternalAuditImportJob | null, key: string) {
  const value = job?.provenance_json?.[key]
  return typeof value === 'number' ? value : null
}

export function deriveDeclaredProgramLabel(
  auditRun: AuditRunDetail | null,
  job: ExternalAuditImportJob | null,
) {
  const declaredScheme =
    auditRun?.assurance_scheme || readProvenanceString(job, 'declared_assurance_scheme') || ''
  const normalizedScheme = declaredScheme.toLowerCase()
  const declaredSource =
    auditRun?.source_origin || readProvenanceString(job, 'declared_source_origin') || ''

  if (normalizedScheme.includes('achilles') || normalizedScheme.includes('uvdb')) {
    return 'Achilles / UVDB'
  }
  if (normalizedScheme.includes('planet mark')) {
    return 'Planet Mark'
  }
  if (declaredSource === 'customer') {
    return 'Customer Audit'
  }
  if (declaredSource === 'certification' && normalizedScheme.startsWith('iso')) {
    return 'ISO Audit'
  }
  if (declaredScheme) {
    return declaredScheme
  }
  if (declaredSource) {
    return humanizeLabel(declaredSource)
  }
  return 'External Audit'
}

import { CUSTOMER_AUDITS_PROGRAMME_PATH } from '../assuranceHubHelpers'

export function deriveSpecialistHome(job: ExternalAuditImportJob | null): { path: string; label: string } {
  const path = job?.specialist_home_path?.trim()
  const label = job?.specialist_home_label?.trim()
  if (path && label) {
    return { path, label }
  }

  let scheme = (job?.detected_scheme || '').trim().toLowerCase()
  if (!scheme) {
    const provenance = job?.provenance_json || {}
    const declaredScheme = String(provenance.declared_assurance_scheme || '').toLowerCase()
    const declaredSource = String(provenance.declared_source_origin || '').toLowerCase()
    if (declaredScheme.includes('achilles') || declaredScheme.includes('uvdb')) {
      scheme = 'achilles_uvdb'
    } else if (declaredScheme.includes('planet mark')) {
      scheme = 'planet_mark'
    } else if (declaredScheme.startsWith('iso')) {
      scheme = 'iso'
    } else if (declaredSource === 'customer') {
      scheme = 'customer_other'
    }
  }

  if (scheme === 'achilles_uvdb') {
    return { path: '/uvdb', label: 'Open Achilles / UVDB' }
  }
  if (scheme === 'planet_mark') {
    return { path: '/planet-mark', label: 'Open Planet Mark' }
  }
  if (scheme === 'iso') {
    return { path: '/compliance', label: 'Open ISO Compliance' }
  }
  if (scheme === 'customer_other' || scheme === 'other') {
    return { path: CUSTOMER_AUDITS_PROGRAMME_PATH, label: 'Open Customer Audits' }
  }
  return { path: CUSTOMER_AUDITS_PROGRAMME_PATH, label: 'Open Customer Audits' }
}
