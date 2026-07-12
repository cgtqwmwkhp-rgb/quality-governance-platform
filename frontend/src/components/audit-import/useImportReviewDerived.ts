import { useMemo } from 'react'
import type {
  AuditRunDetail,
  ExternalAuditImportDraft,
  ExternalAuditImportJob,
  ExternalAuditPromotionReconciliation,
} from '../../api/client'
import {
  ACTION_FINDING_TYPES,
  deriveDeclaredProgramLabel,
  deriveSpecialistHome,
  readProvenanceNumber,
  readProvenanceString,
  shouldCreateRisk,
} from './importReviewHelpers'

export function useImportReviewDerived(
  job: ExternalAuditImportJob | null,
  auditRun: AuditRunDetail | null,
  drafts: ExternalAuditImportDraft[],
  reconciliation: ExternalAuditPromotionReconciliation | null,
) {
  const approvedCount = useMemo(
    () =>
      drafts.filter((draft) => draft.status === 'accepted' || draft.status === 'promoted').length,
    [drafts],
  )
  const promoteableCount = useMemo(
    () =>
      drafts.filter((draft) => draft.status === 'accepted' && !draft.promoted_finding_id).length,
    [drafts],
  )
  const pendingDraftCount = useMemo(
    () => drafts.filter((draft) => draft.status === 'draft' && !draft.promoted_finding_id).length,
    [drafts],
  )
  const acceptedDrafts = useMemo(
    () => drafts.filter((draft) => draft.status === 'accepted' || draft.status === 'promoted'),
    [drafts],
  )
  const acceptedClauseCount = useMemo(() => {
    const clauseKeys = new Set<string>()
    acceptedDrafts.forEach((draft) => {
      draft.mapped_standards_json?.forEach((mapping) => {
        const clauseKey =
          typeof mapping?.clause_id === 'string'
            ? mapping.clause_id
            : [mapping?.standard, mapping?.clause_number].filter(Boolean).join(':')
        if (clauseKey) clauseKeys.add(clauseKey)
      })
    })
    return clauseKeys.size
  }, [acceptedDrafts])
  const acceptedActionCandidates = useMemo(
    () =>
      acceptedDrafts.filter((draft) => ACTION_FINDING_TYPES.includes(draft.finding_type)).length,
    [acceptedDrafts],
  )
  const acceptedRiskCandidates = useMemo(
    () => acceptedDrafts.filter(shouldCreateRisk).length,
    [acceptedDrafts],
  )
  const promotionSummary = job?.promotion_summary_json ?? null
  const schemeAlignment = promotionSummary?.scheme_alignment as Record<string, unknown> | undefined
  const declaredProgramLabel = deriveDeclaredProgramLabel(auditRun, job)
  const declaredSourceOrigin =
    auditRun?.source_origin || readProvenanceString(job, 'declared_source_origin')
  const declaredScheme =
    auditRun?.assurance_scheme || readProvenanceString(job, 'declared_assurance_scheme')
  const resolvedTemplateVersion =
    auditRun?.template_version ?? readProvenanceNumber(job, 'processing_template_version')
  const resolvedTemplateId =
    auditRun?.template_id ?? readProvenanceNumber(job, 'processing_template_id')
  const resolvedTemplateName = auditRun?.template_name
  const declaredExternalBody =
    auditRun?.external_body_name || readProvenanceString(job, 'declared_external_body_name')
  const declaredExternalReference =
    auditRun?.external_reference || readProvenanceString(job, 'declared_external_reference')
  const specialistHome = useMemo(() => deriveSpecialistHome(job), [job])
  const specialistHomePath =
    reconciliation?.view_links?.specialist_home ||
    reconciliation?.view_links?.uvdb ||
    specialistHome.path

  return {
    approvedCount,
    promoteableCount,
    pendingDraftCount,
    acceptedDrafts,
    acceptedClauseCount,
    acceptedActionCandidates,
    acceptedRiskCandidates,
    promotionSummary,
    schemeAlignment,
    declaredProgramLabel,
    declaredSourceOrigin,
    declaredScheme,
    resolvedTemplateVersion,
    resolvedTemplateId,
    resolvedTemplateName,
    declaredExternalBody,
    declaredExternalReference,
    specialistHome,
    specialistHomePath,
  }
}
