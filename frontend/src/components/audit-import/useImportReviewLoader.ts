import { useCallback, useEffect, useRef, useState } from 'react'
import {
  auditsApi,
  externalAuditImportsApi,
  getApiErrorMessage,
  type AuditRunDetail,
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
  type ExternalAuditPromotionReconciliation,
} from '../../api/client'
import { describeReconciliationFailure } from './importReviewHelpers'
import type { PromotionFailedDraftRow } from './importReviewHelpers'

export function useImportReviewLoader(jobId: number, routeAuditId: number, initialQueueNotice: string | null) {
  const [job, setJob] = useState<ExternalAuditImportJob | null>(null)
  const [auditRun, setAuditRun] = useState<AuditRunDetail | null>(null)
  const [drafts, setDrafts] = useState<ExternalAuditImportDraft[]>([])
  const [reconciliation, setReconciliation] = useState<ExternalAuditPromotionReconciliation | null>(null)
  const [loading, setLoading] = useState(true)
  const initialLoadDone = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [queueNotice, setQueueNotice] = useState<string | null>(initialQueueNotice)
  const [reconciliationNotice, setReconciliationNotice] = useState<string | null>(null)
  const [promotionFailedDrafts, setPromotionFailedDrafts] = useState<PromotionFailedDraftRow[] | null>(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null)
  const [isDocumentHidden, setIsDocumentHidden] = useState(
    () => typeof document !== 'undefined' && document.hidden,
  )
  const [isProcessing, setIsProcessing] = useState(false)
  const processingTriggered = useRef(false)
  const pollDelayMs = useRef(5000)

  const load = useCallback(async () => {
    if (!jobId && (!Number.isFinite(routeAuditId) || routeAuditId <= 0)) {
      setJob(null)
      setAuditRun(null)
      setDrafts([])
      setError('Missing import job reference.')
      setLoading(false)
      initialLoadDone.current = true
      return
    }

    if (!initialLoadDone.current) {
      setLoading(true)
    }
    setError(null)
    setPromotionFailedDrafts(null)
    setReconciliationNotice(null)
    try {
      let resolvedJobRes = null
      if (jobId) {
        resolvedJobRes = await externalAuditImportsApi.getJob(jobId)
      } else if (Number.isFinite(routeAuditId) && routeAuditId > 0) {
        resolvedJobRes = await externalAuditImportsApi.getLatestJobForRun(routeAuditId)
      }

      if (!resolvedJobRes) {
        throw new Error('Import job could not be resolved')
      }

      const [jobRes, draftsRes, reconciliationResult] = await Promise.all([
        Promise.resolve(resolvedJobRes),
        externalAuditImportsApi.listDrafts(resolvedJobRes.data.id),
        externalAuditImportsApi
          .getReconciliation(resolvedJobRes.data.id)
          .then((res) => ({ data: res.data, notice: null as string | null }))
          .catch((reconciliationErr) => ({
            data: null,
            notice: describeReconciliationFailure(reconciliationErr, resolvedJobRes.data.status) || null,
          })),
      ])
      if (
        Number.isFinite(routeAuditId) &&
        routeAuditId > 0 &&
        jobRes.data.audit_run_id !== routeAuditId
      ) {
        setJob(null)
        setAuditRun(null)
        setDrafts([])
        setError(
          'This import job belongs to a different audit run. Re-open it from the audits workspace.',
        )
        return
      }
      let auditRunDetail: AuditRunDetail | null = null
      try {
        const auditRunRes = await auditsApi.getRunDetail(jobRes.data.audit_run_id)
        auditRunDetail = auditRunRes.data
      } catch (auditRunErr) {
        console.error('Failed to load resolved audit run details for import review', auditRunErr)
      }
      setJob(jobRes.data)
      setAuditRun(auditRunDetail)
      setDrafts(draftsRes.data)
      setReconciliation(reconciliationResult.data)
      setReconciliationNotice(reconciliationResult.notice)
      setPromotionFailedDrafts(null)
      setLastUpdatedAt(new Date())
    } catch (err) {
      console.error('Failed to load external audit review workspace', err)
      setAuditRun(null)
      setReconciliation(null)
      setReconciliationNotice(null)
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404 && !jobId) {
        setError(
          'No import job has been created for this audit yet. Attach a source report and queue the import first.',
        )
      } else if (status === 422) {
        setError(getApiErrorMessage(err))
      } else {
        setError('Failed to load the import review workspace. Please retry.')
      }
    } finally {
      setLoading(false)
      initialLoadDone.current = true
    }
  }, [jobId, routeAuditId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const onVisibilityChange = () => {
      setIsDocumentHidden(document.hidden)
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [])

  useEffect(() => {
    if (!job || job.status !== 'queued' || isProcessing || processingTriggered.current) return
    processingTriggered.current = true
    setIsProcessing(true)
    externalAuditImportsApi
      .processJob(job.id)
      .then(() => load())
      .catch((err) => {
        console.error('Import processing failed', err)
        void load()
      })
      .finally(() => setIsProcessing(false))
  }, [job, isProcessing, load])

  useEffect(() => {
    if (!job || !['processing', 'promoting'].includes(job.status)) {
      pollDelayMs.current = 5000
      return
    }
    if (isDocumentHidden) return

    const delay = pollDelayMs.current
    const timeoutId = window.setTimeout(() => {
      void load().finally(() => {
        pollDelayMs.current = Math.min(pollDelayMs.current * 2, 30000)
      })
    }, delay)
    return () => window.clearTimeout(timeoutId)
  }, [job, load, isDocumentHidden])

  return {
    job,
    setJob,
    auditRun,
    setAuditRun,
    drafts,
    setDrafts,
    reconciliation,
    setReconciliation,
    loading,
    error,
    setError,
    queueNotice,
    setQueueNotice,
    reconciliationNotice,
    setReconciliationNotice,
    promotionFailedDrafts,
    setPromotionFailedDrafts,
    lastUpdatedAt,
    isProcessing,
    setIsProcessing,
    isDocumentHidden,
    load,
  }
}
