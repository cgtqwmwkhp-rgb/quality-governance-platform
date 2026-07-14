import { useState, type Dispatch, type SetStateAction } from 'react'
import {
  externalAuditImportsApi,
  getApiErrorMessage,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
  type ExternalAuditPromotionReconciliation,
} from '../../api/client'
import {
  describePromotionFailure,
  describeReconciliationFailure,
  extractPromotionFailedDrafts,
  type PromotionFailedDraftRow,
} from './importReviewHelpers'

type UseImportReviewActionsArgs = {
  job: ExternalAuditImportJob | null
  setJob: (job: ExternalAuditImportJob | null) => void
  setDrafts: Dispatch<SetStateAction<ExternalAuditImportDraft[]>>
  setReconciliation: (value: ExternalAuditPromotionReconciliation | null) => void
  setError: (value: string | null) => void
  setQueueNotice: (value: string | null) => void
  setReconciliationNotice: (value: string | null) => void
  setPromotionFailedDrafts: (value: PromotionFailedDraftRow[] | null) => void
  setIsProcessing: (value: boolean) => void
  load: () => Promise<void>
  promoteableCount: number
  pendingDraftCount: number
}

export function useImportReviewActions({
  job,
  setJob,
  setDrafts,
  setReconciliation,
  setError,
  setQueueNotice,
  setReconciliationNotice,
  setPromotionFailedDrafts,
  setIsProcessing,
  load,
  promoteableCount,
  pendingDraftCount,
}: UseImportReviewActionsArgs) {
  const [busyDraftId, setBusyDraftId] = useState<number | null>(null)
  const [isBulkReviewing, setIsBulkReviewing] = useState(false)
  const [isPromoting, setIsPromoting] = useState(false)
  const [isQueueing, setIsQueueing] = useState(false)
  const [showPromoteConfirm, setShowPromoteConfirm] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleDraftDecision = async (
    draftId: number,
    status: 'accepted' | 'rejected' | 'draft',
    extras?: Record<string, string>,
  ) => {
    setBusyDraftId(draftId)
    setError(null)
    setSuccessMessage(null)
    try {
      const payload: {
        status: 'accepted' | 'rejected' | 'draft'
        title?: string
        description?: string
        severity?: string
        review_notes?: string
      } = { status }
      if (extras) {
        if (extras.title) payload.title = extras.title
        if (extras.description) payload.description = extras.description
        if (extras.severity) payload.severity = extras.severity
        if (extras.review_notes) payload.review_notes = extras.review_notes
      }
      const res = await externalAuditImportsApi.reviewDraft(draftId, payload)
      setDrafts((prev) => prev.map((draft) => (draft.id === draftId ? res.data : draft)))
      setError(null)
    } catch (err) {
      console.error('Failed to update draft review decision', err)
      setError('Failed to update the draft. Please retry.')
    } finally {
      setBusyDraftId(null)
    }
  }

  const handlePromoteClick = () => {
    if (!job || promoteableCount === 0 || ['completed', 'promoting'].includes(job.status)) return
    setShowPromoteConfirm(true)
  }

  const handleBulkApprove = async () => {
    if (!job || pendingDraftCount === 0) return
    setIsBulkReviewing(true)
    setError(null)
    setSuccessMessage(null)
    try {
      const res = await externalAuditImportsApi.bulkReviewJob(job.id, { status: 'accepted' })
      setDrafts(res.data)
      setSuccessMessage(`Approved ${pendingDraftCount} pending finding(s). Review and promote when ready.`)
      await load()
    } catch (err) {
      console.error('Failed to bulk approve draft findings', err)
      setError(getApiErrorMessage(err) || 'Failed to approve all pending findings. Please retry.')
    } finally {
      setIsBulkReviewing(false)
    }
  }

  const handlePromoteConfirm = async () => {
    if (!job) return
    setShowPromoteConfirm(false)
    setIsPromoting(true)
    setError(null)
    setPromotionFailedDrafts(null)
    setSuccessMessage(null)
    try {
      const promoteRes = await externalAuditImportsApi.promoteJob(job.id)
      setJob(promoteRes.data)
      setSuccessMessage(
        'Promotion started. This workspace will refresh automatically while accepted drafts are materialized.',
      )
      if (promoteRes.data.status === 'promoting') {
        return
      }
      await load()
      let nextReconciliation: ExternalAuditPromotionReconciliation | null = null
      try {
        const reconciliationRes = await externalAuditImportsApi.getReconciliation(job.id)
        nextReconciliation = reconciliationRes.data
        setReconciliationNotice(null)
      } catch (reconciliationErr) {
        setReconciliationNotice(describeReconciliationFailure(reconciliationErr, 'completed') || null)
      }
      setReconciliation(nextReconciliation)
      if (nextReconciliation?.failed_total) {
        setSuccessMessage(
          `Promotion partially completed: ${nextReconciliation.promoted_total} finding(s) materialized, ${nextReconciliation.failed_total} still require review.`,
        )
      } else {
        const promotedFromSummary = promoteRes.data.promotion_summary_json?.[
          'promoted_findings'
        ] as unknown
        const promotedCount =
          nextReconciliation?.promoted_total ??
          (Array.isArray(promotedFromSummary) ? promotedFromSummary.length : promoteableCount)
        setSuccessMessage(
          `Successfully promoted ${promotedCount} finding(s) into the live governance system.`,
        )
      }
    } catch (err) {
      console.error('Failed to promote imported audit findings', err)
      setPromotionFailedDrafts(extractPromotionFailedDrafts(err))
      setError(describePromotionFailure(err))
    } finally {
      setIsPromoting(false)
    }
  }

  const handleRetryQueue = async () => {
    if (!job) return
    setIsQueueing(true)
    setError(null)
    try {
      const queueRes = await externalAuditImportsApi.queueJob(job.id)
      setQueueNotice(null)
      setJob(queueRes.data)

      if (queueRes.data.status === 'queued') {
        setIsProcessing(true)
        try {
          await externalAuditImportsApi.processJob(job.id)
        } catch (processErr) {
          console.error('Import processing failed after retry', processErr)
        } finally {
          setIsProcessing(false)
        }
      }
      await load()
    } catch (err) {
      console.error('Failed to queue external audit import job', err)
      setError('Failed to start processing. Please retry queueing the import.')
    } finally {
      setIsQueueing(false)
    }
  }

  const dismissSuccess = () => setSuccessMessage(null)

  return {
    busyDraftId,
    isBulkReviewing,
    isPromoting,
    isQueueing,
    showPromoteConfirm,
    setShowPromoteConfirm,
    successMessage,
    dismissSuccess,
    handleDraftDecision,
    handlePromoteClick,
    handleBulkApprove,
    handlePromoteConfirm,
    handleRetryQueue,
  }
}
