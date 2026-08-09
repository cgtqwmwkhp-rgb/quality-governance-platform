import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  Loader2,
  Sparkles,
  Tag,
  CheckCircle2,
  MessageSquare,
  Eye,
  Download,
  AlertTriangle,
  Brain,
} from 'lucide-react'
import api, {
  documentCampaignApi,
  documentGraphApi,
  entity360Api,
  getApiErrorMessage,
  knowledgeBankApi,
  type DiscussionMessage,
  type DiscussionThread,
  type DocumentEdge,
  type KnowledgeEvidenceLink,
  type QuizDraft,
  type RegulatoryImpact,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog'
import { DocumentVersionControlBar } from '../components/DocumentVersionControlBar'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { cn } from '../helpers/utils'
import {
  PROPOSED_EVIDENCE_ANCHOR_ID,
  documentDetailSectionDomId,
  resolveDocumentDetailSection,
  resolveDocumentDetailTab,
  shouldScrollToProposedEvidence,
} from './documentEvidenceTab'
import {
  resolveDocumentRelationshipAmbientCounts,
  shouldShowDocumentRelationshipChips,
  summariseDocumentRelationships,
} from './documentRelationshipHelpers'
import {
  buildDocumentRelationshipCoverageHonesty,
  measureRelationshipRoleCoverage,
} from './documentRelationshipCoverage'
import { buildPublishImpactPreview, publishImpactPreviewFromBundle, type PublishImpactPreview } from './documentPublishImpactHelpers'
import { complianceClauseHref } from './complianceEvidenceHelpers'
import { DocumentPublishImpactPreview } from './DocumentPublishImpactPreview'
import { DocumentRelationshipChips } from './DocumentRelationshipChips'
import { DocumentRelationshipsPanel } from './DocumentRelationshipsPanel'
import { DocumentThreadStrip } from '../components/graph/DocumentThreadStrip'
import { Entity360Strip } from '../components/graph/Entity360Strip'
import {
  buildDocumentDownstreamView,
  buildDocumentsExceptionsHref,
  DOCUMENT_CONTROL_GOLDEN_THREAD_PATH,
} from './documentsDownstreamHelpers'
import {
  isProposedEvidenceLink,
  parseEvidenceQuote,
} from './documentEvidenceSnippetHelpers'
import {
  isQuizAiFallback,
  normalizeQuestionCountInput,
  sanitizeQuestionCount,
} from './documentQuizHelpers'
import { DocumentCampaignPanel } from './DocumentCampaignPanel'
import { DocumentCampaignResults } from './DocumentCampaignResults'

const DocumentPdfPreview = lazy(() => import('../components/DocumentPdfPreview'))

interface LibraryDocument {
  id: number
  reference_number: string
  title: string
  description?: string
  file_name: string
  file_type: string
  document_type: string
  category?: string
  status: string
  version: string
  ai_summary?: string
  ai_tags?: string[]
  ai_keywords?: string[]
  view_count: number
  download_count: number
  created_at: string
  indexed_at?: string
  chunk_count?: number
  indexing_error?: string | null
}

interface LibraryVersionRow {
  id: number
  version_number: string
  change_notes?: string | null
  change_type: string
  status: string
  is_immutable: boolean
  read_only: boolean
  file_name: string
  file_size: number
  filename_version_hint?: string | null
  index_job_id?: number | null
  created_by_id?: number | null
  created_at?: string | null
  published_at?: string | null
  published_by_id?: number | null
}

interface CampaignOffer {
  eligible: boolean
  reason?: string | null
  document_id: number
  pel_doc_ref?: string | null
  suggested_title?: string
  ui_label?: string
  existing_draft_campaign_id?: number | null
  existing_active_campaign_id?: number | null
}

interface LibraryVersionHistory {
  document_id: number
  current_version: string
  status: string
  published_version?: string | null
  working_version?: string | null
  versions: LibraryVersionRow[]
  campaign_offer?: CampaignOffer | null
}

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

const evidenceStatusBadge = (link: KnowledgeEvidenceLink) => {
  if (link.status === 'confirmed' && link.auto_applied) {
    return <Badge variant="success">Auto-confirmed</Badge>
  }
  if (link.status === 'confirmed') {
    return <Badge variant="success">Confirmed</Badge>
  }
  if (link.status === 'proposed') {
    return <Badge variant="submitted">Proposed</Badge>
  }
  if (link.status === 'needs_review') {
    return <Badge variant="warning">Needs review</Badge>
  }
  if (link.status === 'rejected') {
    return <Badge variant="destructive">Rejected</Badge>
  }
  return <Badge variant="secondary">{link.status}</Badge>
}

export default function DocumentDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const documentId = Number(id)
  const documentGraphEnabled = useFeatureFlag('document_graph')
  const entity360Enabled = useFeatureFlag('entity_360')
  const tabParam = searchParams.get('tab')
  const defaultTab = resolveDocumentDetailTab(tabParam)
  const detailSection = resolveDocumentDetailSection(tabParam)
  const campaignIdParam = Number(searchParams.get('campaignId'))
  const initialCampaignId =
    Number.isFinite(campaignIdParam) && campaignIdParam > 0 ? campaignIdParam : null
  const proposedSectionRef = useRef<HTMLDivElement | null>(null)

  const [document, setDocument] = useState<LibraryDocument | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [partialLoad, setPartialLoad] = useState(false)

  const [evidence, setEvidence] = useState<KnowledgeEvidenceLink[]>([])
  const [evidenceLoading, setEvidenceLoading] = useState(false)
  const [mapping, setMapping] = useState(false)
  const [selectedLinkIds, setSelectedLinkIds] = useState<number[]>([])

  const [quizDraft, setQuizDraft] = useState<QuizDraft | null>(null)
  const [quizGenerating, setQuizGenerating] = useState(false)
  const [quizApproving, setQuizApproving] = useState(false)
  const [quizAiFallback, setQuizAiFallback] = useState(false)
  const [questionCountInput, setQuestionCountInput] = useState('5')
  const [passMark, setPassMark] = useState(70)
  const [includeMcq, setIncludeMcq] = useState(true)
  const [includeOpen, setIncludeOpen] = useState(true)
  const [autoApproveQuiz, setAutoApproveQuiz] = useState(false)

  const [threads, setThreads] = useState<DiscussionThread[]>([])
  const [threadMessages, setThreadMessages] = useState<Record<number, DiscussionMessage[]>>({})
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [newThreadTitle, setNewThreadTitle] = useState('')
  const [messageBody, setMessageBody] = useState('')
  const [useAiDraft, setUseAiDraft] = useState(false)
  const [postingMessage, setPostingMessage] = useState(false)

  const [impacts, setImpacts] = useState<RegulatoryImpact[]>([])
  const [versionHistory, setVersionHistory] = useState<LibraryVersionHistory | null>(null)
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [versionsError, setVersionsError] = useState<string | null>(null)
  const [revising, setRevising] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishPreviewOpen, setPublishPreviewOpen] = useState(false)
  const [publishPreviewLoading, setPublishPreviewLoading] = useState(false)
  const [publishPreviewError, setPublishPreviewError] = useState<string | null>(null)
  const [publishPreview, setPublishPreview] = useState<PublishImpactPreview | null>(null)
  const [publishCanPublish, setPublishCanPublish] = useState(true)
  const [publishDegradedReasons, setPublishDegradedReasons] = useState<string[]>([])
  const [titleDraft, setTitleDraft] = useState('')
  const [savingTitle, setSavingTitle] = useState(false)
  const [showInlinePreview, setShowInlinePreview] = useState(false)
  const [lifecycleBusy, setLifecycleBusy] = useState(false)
  const [campaignOffer, setCampaignOffer] = useState<CampaignOffer | null>(null)
  const [offeringCampaign, setOfferingCampaign] = useState(false)

  const [edges, setEdges] = useState<DocumentEdge[]>([])
  const [edgesLoading, setEdgesLoading] = useState(false)
  const [edgesError, setEdgesError] = useState<string | null>(null)

  const questionCount = useMemo(
    () => sanitizeQuestionCount(questionCountInput),
    [questionCountInput],
  )

  const proposedLinks = useMemo(
    () => evidence.filter((l) => l.status === 'proposed' || l.status === 'needs_review'),
    [evidence],
  )

  const loadDocument = useCallback(async () => {
    if (!documentId || Number.isNaN(documentId)) return
    setLoading(true)
    setError(null)
    setPartialLoad(false)
    try {
      const response = await api.get<LibraryDocument>(`/api/v1/documents/${documentId}`)
      setDocument(response.data)
    } catch (err) {
      setError(reportFailure(err))
      setDocument(null)
    } finally {
      setLoading(false)
    }
  }, [documentId])

  const loadVersions = useCallback(async () => {
    if (!documentId || Number.isNaN(documentId)) return
    setVersionsLoading(true)
    setVersionsError(null)
    try {
      const response = await api.get<LibraryVersionHistory>(
        `/api/v1/documents/${documentId}/versions`,
      )
      setVersionHistory(response.data)
    } catch (err) {
      setVersionsError(reportFailure(err))
      setVersionHistory(null)
    } finally {
      setVersionsLoading(false)
    }
  }, [documentId])

  const loadEvidence = useCallback(async () => {
    if (!documentId || Number.isNaN(documentId)) return
    setEvidenceLoading(true)
    try {
      const response = await knowledgeBankApi.listDocumentEvidence(documentId)
      setEvidence(response.data)
    } catch (err) {
      setPartialLoad(true)
      reportFailure(err)
    } finally {
      setEvidenceLoading(false)
    }
  }, [documentId])

  const loadThreads = useCallback(async () => {
    if (!documentId || Number.isNaN(documentId)) return
    try {
      const response = await knowledgeBankApi.listThreads(documentId)
      setThreads(response.data)
      if (response.data.length > 0) {
        setActiveThreadId((prev) => prev ?? response.data[0].id)
      }
    } catch (err) {
      setPartialLoad(true)
      reportFailure(err)
    }
  }, [documentId])

  const loadThreadMessages = useCallback(async (threadId: number) => {
    setMessagesLoading(true)
    try {
      const response = await knowledgeBankApi.listMessages(threadId)
      setThreadMessages((prev) => ({ ...prev, [threadId]: response.data }))
    } catch (err) {
      setPartialLoad(true)
      reportFailure(err)
    } finally {
      setMessagesLoading(false)
    }
  }, [])

  const loadImpacts = useCallback(async () => {
    try {
      const response = await knowledgeBankApi.listImpacts()
      setImpacts(response.data.filter((i) => i.document_id === documentId))
    } catch (err) {
      setPartialLoad(true)
      reportFailure(err)
    }
  }, [documentId])

  // Doc Graph edges load only while the flag is open; the routes 404 when closed,
  // so calling them anyway would surface a phantom error on every document.
  const loadEdges = useCallback(async () => {
    if (!documentGraphEnabled) {
      setEdges([])
      setEdgesError(null)
      return
    }
    if (!documentId || Number.isNaN(documentId)) return
    // Drop prior document's edges before fetch so chips/counts never flash stale rows.
    setEdges([])
    setEdgesError(null)
    setEdgesLoading(true)
    try {
      const response = await documentGraphApi.listEdges(documentId)
      setEdges(response.data.items)
    } catch (err) {
      setEdges([])
      setEdgesError(getApiErrorMessage(err))
    } finally {
      setEdgesLoading(false)
    }
  }, [documentId, documentGraphEnabled])

  const relationshipSummary = useMemo(
    () => summariseDocumentRelationships(documentId, edges),
    [documentId, edges],
  )

  const relationshipCoverageHonesty = useMemo(() => {
    // While edges are clearing/fetching, or after a listEdges failure, do not
    // invent a sparse spine gap from a temporarily empty array.
    if (!documentGraphEnabled || !document || edgesLoading || edgesError) {
      return buildDocumentRelationshipCoverageHonesty(null)
    }
    return buildDocumentRelationshipCoverageHonesty(
      measureRelationshipRoleCoverage(documentId, document.document_type, edges),
    )
  }, [documentGraphEnabled, document, documentId, edges, edgesLoading, edgesError])

  const confirmedEvidenceCount = useMemo(
    () => evidence.filter((link) => link.status === 'confirmed').length,
    [evidence],
  )

  useEffect(() => {
    if (document) setTitleDraft(document.title)
  }, [document])

  const canEditTitle = useMemo(() => {
    const status = (versionHistory?.status ?? document?.status ?? '').toLowerCase()
    return !['published', 'approved', 'active', 'superseded', 'retired', 'obsolete', 'archived'].includes(
      status,
    )
  }, [versionHistory?.status, document?.status])

  useEffect(() => {
    void loadDocument()
    void loadEvidence()
    void loadThreads()
    void loadImpacts()
    void loadVersions()
    void loadEdges()
  }, [loadDocument, loadEvidence, loadThreads, loadImpacts, loadVersions, loadEdges])

  useEffect(() => {
    if (activeThreadId == null) return
    void loadThreadMessages(activeThreadId)
  }, [activeThreadId, loadThreadMessages])

  const resolveSignedUrl = useCallback(async (download = false) => {
    if (!document) return null
    const response = await api.get<{ signed_url: string }>(
      `/api/v1/documents/${document.id}/signed-url`,
      { params: { download } },
    )
    const rawUrl = response.data.signed_url
    return new URL(rawUrl, api.defaults.baseURL || window.location.origin).toString()
  }, [document])

  const handleReviseVersion = async (changeSummary: string, isMajor: boolean, file?: File | null) => {
    if (!documentId) return
    setRevising(true)
    try {
      const form = new FormData()
      form.append('change_notes', changeSummary)
      form.append('change_type', 'revision')
      form.append('is_major_version', String(isMajor))
      if (file) form.append('file', file)
      await api.post(`/api/v1/documents/${documentId}/versions`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      toast.success(file ? 'Revision draft opened — re-index queued' : 'Revision draft opened')
      await loadVersions()
      await loadDocument()
    } catch (err) {
      reportFailure(err)
      throw err
    } finally {
      setRevising(false)
    }
  }

  const handleSaveTitle = async () => {
    if (!documentId || !titleDraft.trim()) return
    setSavingTitle(true)
    try {
      await api.patch(`/api/v1/documents/${documentId}`, { title: titleDraft.trim() })
      toast.success('Title updated (no version bump)')
      await loadDocument()
    } catch (err) {
      reportFailure(err)
    } finally {
      setSavingTitle(false)
    }
  }

  const executePublishVersion = async () => {
    if (!documentId) return
    setPublishing(true)
    try {
      await api.post(`/api/v1/documents/${documentId}/publish`)
      toast.success('Version published')
      setPublishPreviewOpen(false)
      setPublishPreview(null)
      await loadVersions()
      await loadDocument()
    } catch (err) {
      reportFailure(err)
    } finally {
      setPublishing(false)
    }
  }

  const handlePublishVersion = async () => {
    if (!documentId) return
    // Flag-off: publish immediately (prior behaviour).
    // entity_360 on: server ImpactBundle — block when incomplete (no silent path).
    // document_graph only: legacy client checklist (Promise.allSettled tolerated).
    if (!documentGraphEnabled && !entity360Enabled) {
      await executePublishVersion()
      return
    }

    setPublishPreviewOpen(true)
    setPublishPreviewLoading(true)
    setPublishPreviewError(null)
    setPublishPreview(null)
    setPublishCanPublish(true)
    setPublishDegradedReasons([])

    if (entity360Enabled) {
      try {
        const response = await entity360Api.getDocumentImpact(documentId)
        const bundle = response.data
        setPublishPreview(publishImpactPreviewFromBundle(bundle))
        setPublishCanPublish(Boolean(bundle.can_publish && bundle.complete))
        setPublishDegradedReasons(bundle.degraded_reasons ?? [])
        if (!bundle.complete) {
          setPublishPreviewError(
            (bundle.degraded_reasons && bundle.degraded_reasons[0]) ||
              'Impact bundle incomplete',
          )
        }
      } catch (err) {
        // Entity360 path must not silently enable publish on fetch failure.
        setPublishPreviewError(getApiErrorMessage(err))
        setPublishCanPublish(false)
        setPublishDegradedReasons([getApiErrorMessage(err)])
        setPublishPreview(null)
      } finally {
        setPublishPreviewLoading(false)
      }
      return
    }

    try {
      const [threadResult, campaignsResult] = await Promise.allSettled([
        documentGraphApi.getThread(documentId),
        documentCampaignApi.listCompliance(),
      ])

      const thread =
        threadResult.status === 'fulfilled' ? threadResult.value.data : null
      const campaigns =
        campaignsResult.status === 'fulfilled' ? campaignsResult.value.data.items : []
      const quizCount = quizDraft ? 1 : 0

      const failures = [threadResult, campaignsResult]
        .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
        .map((r) => getApiErrorMessage(r.reason))
      if (failures.length > 0) {
        setPublishPreviewError(failures[0])
      }

      setPublishPreview(
        buildPublishImpactPreview({
          documentId,
          edges,
          thread,
          evidence,
          campaigns,
          impacts,
          quizCount,
        }),
      )
    } catch (err) {
      setPublishPreviewError(getApiErrorMessage(err))
      setPublishPreview(
        buildPublishImpactPreview({
          documentId,
          edges,
          thread: null,
          evidence,
          campaigns: [],
          impacts,
        }),
      )
    } finally {
      setPublishPreviewLoading(false)
    }
  }

  const docStatus = (versionHistory?.status ?? document?.status ?? '').toLowerCase()

  const handleSubmitForReview = async () => {
    if (!documentId) return
    setLifecycleBusy(true)
    try {
      await api.post(`/api/v1/documents/${documentId}/submit`)
      toast.success('Submitted for HSEQ review')
      setCampaignOffer(null)
      await loadVersions()
      await loadDocument()
    } catch (err) {
      reportFailure(err)
    } finally {
      setLifecycleBusy(false)
    }
  }

  const handleApproveDocument = async () => {
    if (!documentId) return
    setLifecycleBusy(true)
    try {
      const response = await api.post<LibraryVersionHistory>(`/api/v1/documents/${documentId}/approve`)
      setVersionHistory(response.data)
      const offer = response.data.campaign_offer ?? null
      setCampaignOffer(offer?.eligible ? offer : null)
      toast.success('Document approved')
      await loadDocument()
    } catch (err) {
      reportFailure(err)
    } finally {
      setLifecycleBusy(false)
    }
  }

  const handleRejectDocument = async () => {
    if (!documentId) return
    setLifecycleBusy(true)
    try {
      await api.post(`/api/v1/documents/${documentId}/reject`, { review_notes: null })
      toast.success('Returned to draft')
      setCampaignOffer(null)
      await loadVersions()
      await loadDocument()
    } catch (err) {
      reportFailure(err)
    } finally {
      setLifecycleBusy(false)
    }
  }

  const handleAcceptCampaignOffer = async () => {
    if (!documentId || !campaignOffer?.eligible) return
    setOfferingCampaign(true)
    try {
      const response = await api.post<{
        offered: boolean
        campaign_id?: number
        reason?: string | null
      }>(`/api/v1/documents/${documentId}/offer-campaign`, {
        title: campaignOffer.suggested_title,
        launch: false,
      })
      const campaignId = response.data.campaign_id
      toast.success(
        response.data.offered
          ? 'HSEQ reading campaign draft created — refine & launch in the Campaign tab'
          : 'Draft HSEQ campaign already exists — open the Campaign tab',
      )
      setCampaignOffer(null)
      if (campaignId) {
        navigate(`/documents/${documentId}?tab=quiz&campaignId=${campaignId}`)
      }
    } catch (err) {
      reportFailure(err)
    } finally {
      setOfferingCampaign(false)
    }
  }

  // /documents/:id?tab=evidence → Coverage, scroll to proposed links.
  useEffect(() => {
    if (!shouldScrollToProposedEvidence(searchParams.get('tab'), window.location.hash)) return
    if (evidenceLoading) return
    const node = proposedSectionRef.current
    if (!node) return
    node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [defaultTab, evidenceLoading, evidence.length, searchParams])

  // Legacy assurance / used-by section anchors (?tab=qa|watch|quiz|campaign-results).
  useEffect(() => {
    if (!detailSection) return
    const id = documentDetailSectionDomId(detailSection)
    const frame = window.requestAnimationFrame(() => {
      window.document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [defaultTab, detailSection])

  const handleOpenPreview = async (download = false) => {
    if (!document) return
    try {
      const signedUrl = await resolveSignedUrl(download)
      if (!signedUrl) return
      if (download) {
        const link = window.document.createElement('a')
        link.href = signedUrl
        link.target = '_blank'
        link.rel = 'noopener noreferrer'
        link.click()
        return
      }
      window.open(signedUrl, '_blank', 'noopener,noreferrer')
    } catch (err) {
      reportFailure(err)
    }
  }

  const handleMapEvidence = async () => {
    setMapping(true)
    try {
      const response = await knowledgeBankApi.mapEvidence(documentId)
      setEvidence((prev) => {
        const ids = new Set(prev.map((l) => l.id))
        const merged = [...response.data.links, ...prev.filter((l) => !ids.has(l.id))]
        return merged
      })
      toast.success(`Mapped ${response.data.links_created} evidence link(s)`)
    } catch (err) {
      reportFailure(err)
    } finally {
      setMapping(false)
    }
  }

  const refreshEvidence = async () => {
    await loadEvidence()
  }

  const handleConfirmLink = async (linkId: number) => {
    try {
      await knowledgeBankApi.confirmLink(linkId)
      toast.success('Link confirmed')
      await refreshEvidence()
    } catch (err) {
      reportFailure(err)
    }
  }

  const handleRejectLink = async (linkId: number) => {
    try {
      await knowledgeBankApi.rejectLink(linkId)
      toast.success('Link rejected')
      await refreshEvidence()
    } catch (err) {
      reportFailure(err)
    }
  }

  const handleBulkConfirm = async () => {
    if (selectedLinkIds.length === 0) return
    try {
      const response = await knowledgeBankApi.bulkConfirm(selectedLinkIds)
      toast.success(`Confirmed ${response.data.count} link(s)`)
      setSelectedLinkIds([])
      await refreshEvidence()
    } catch (err) {
      reportFailure(err)
    }
  }

  const toggleLinkSelection = (linkId: number) => {
    setSelectedLinkIds((prev) =>
      prev.includes(linkId) ? prev.filter((id) => id !== linkId) : [...prev, linkId],
    )
  }

  const handleGenerateQuiz = async () => {
    setQuizGenerating(true)
    setQuizAiFallback(false)
    try {
      const response = await knowledgeBankApi.generateQuiz(documentId, {
        question_count: questionCount,
        include_mcq: includeMcq,
        include_open: includeOpen,
        pass_mark: passMark,
        auto_approve_if_quality: autoApproveQuiz,
      })
      setQuizDraft(response.data)
      const fallback = isQuizAiFallback(response.data.questions, questionCount)
      setQuizAiFallback(fallback)
      if (fallback) {
        toast.error(t('documents.detail.quiz_ai_fallback'))
      } else {
        toast.success('Quiz draft generated')
      }
    } catch (err) {
      reportFailure(err)
    } finally {
      setQuizGenerating(false)
    }
  }

  const handleApproveQuiz = async () => {
    setQuizApproving(true)
    try {
      await knowledgeBankApi.approveQuiz(documentId, quizDraft?.id)
      toast.success('Quiz approved')
      if (quizDraft) {
        setQuizDraft({ ...quizDraft, status: 'approved' })
      }
    } catch (err) {
      reportFailure(err)
    } finally {
      setQuizApproving(false)
    }
  }

  const handleCreateThread = async () => {
    try {
      const response = await knowledgeBankApi.createThread(documentId, {
        title: newThreadTitle.trim() || undefined,
        version: document?.version ?? '1.0',
      })
      setThreads((prev) => [response.data, ...prev])
      setActiveThreadId(response.data.id)
      setNewThreadTitle('')
      toast.success('Discussion thread created')
    } catch (err) {
      reportFailure(err)
    }
  }

  const handlePostMessage = async () => {
    if (!activeThreadId || !messageBody.trim()) return
    setPostingMessage(true)
    try {
      const response = await knowledgeBankApi.postMessage(activeThreadId, {
        body: messageBody.trim(),
        use_ai_draft: useAiDraft,
      })
      setThreadMessages((prev) => ({
        ...prev,
        [activeThreadId]: [...(prev[activeThreadId] ?? []), response.data],
      }))
      setMessageBody('')
      toast.success(useAiDraft ? 'AI draft posted' : 'Message posted')
    } catch (err) {
      reportFailure(err)
    } finally {
      setPostingMessage(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/documents')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Library
        </Button>
        <EmptyState
          icon={<AlertTriangle className="w-8 h-8 text-destructive" />}
          title="Document unavailable"
          description={error ?? 'Document not found'}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/documents">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Library
            </Link>
          </Button>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm text-primary">{document.reference_number}</span>
            <Badge variant="secondary">{document.status}</Badge>
            {partialLoad ? (
              <Badge variant="outline">Partial data — some sources unavailable</Badge>
            ) : (
              <Badge variant="secondary">Live data</Badge>
            )}
          </div>
          <h1 className="text-2xl font-bold text-foreground">{document.title}</h1>
          <p className="text-sm text-muted-foreground capitalize">
            {document.document_type}
            {document.category ? ` · ${document.category}` : ''} · v{document.version}
          </p>
          {shouldShowDocumentRelationshipChips(documentGraphEnabled, edgesError) ? (
            <DocumentRelationshipChips
              documentId={document.id}
              summary={relationshipSummary}
              evidenceCount={confirmedEvidenceCount}
            />
          ) : null}
          {documentGraphEnabled ? (
            <DocumentThreadStrip
              documentId={document.id}
              documentTitle={document.title}
              documentReference={document.reference_number}
              documentGraphEnabled={documentGraphEnabled}
            />
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {['draft', 'indexed', 'rejected'].includes(docStatus) ? (
            <Button onClick={() => void handleSubmitForReview()} disabled={lifecycleBusy}>
              {lifecycleBusy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Submit for HSEQ review
            </Button>
          ) : null}
          {docStatus === 'under_review' ? (
            <>
              <Button onClick={() => void handleApproveDocument()} disabled={lifecycleBusy}>
                {lifecycleBusy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : (
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                )}
                Approve
              </Button>
              <Button variant="outline" onClick={() => void handleRejectDocument()} disabled={lifecycleBusy}>
                Reject
              </Button>
            </>
          ) : null}
          <Button variant="outline" onClick={() => void handleOpenPreview(false)}>
            <Eye className="w-4 h-4 mr-2" />
            Preview
          </Button>
          <Button variant="outline" onClick={() => void handleOpenPreview(true)}>
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>
        </div>
      </div>

      {campaignOffer?.eligible ? (
        <Card className="p-4 border-primary/30 bg-primary/5" data-testid="hseq-campaign-offer">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium text-foreground">
                {campaignOffer.ui_label ?? 'HSEQ reading campaign'}
              </p>
              <p className="text-sm text-muted-foreground">
                Offer a DocumentCampaign so staff can read and acknowledge this approved document.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setCampaignOffer(null)} disabled={offeringCampaign}>
                Not now
              </Button>
              <Button onClick={() => void handleAcceptCampaignOffer()} disabled={offeringCampaign}>
                {offeringCampaign ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Create draft campaign
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      <Tabs defaultValue={defaultTab} key={defaultTab} data-testid="document-detail-layers">
        <TabsList className="flex flex-wrap h-auto gap-1" data-testid="document-detail-layer-list">
          <TabsTrigger value="control" data-testid="document-layer-control">
            {t('documents.detail.layer_control', 'Control')}
          </TabsTrigger>
          <TabsTrigger value="coverage" data-testid="document-layer-coverage">
            {t('documents.detail.layer_coverage', 'Coverage')}
          </TabsTrigger>
          <TabsTrigger value="related" data-testid="document-layer-related">
            {t('documents.detail.layer_related', 'Related')}
            {documentGraphEnabled && relationshipSummary.pending > 0
              ? ` (${relationshipSummary.pending})`
              : ''}
          </TabsTrigger>
          <TabsTrigger value="used-by" data-testid="document-layer-used-by">
            {t('documents.detail.layer_used_by', 'Used by')}
          </TabsTrigger>
          <TabsTrigger value="history" data-testid="document-layer-history">
            {t('documents.detail.layer_history', 'History')}
          </TabsTrigger>
          <TabsTrigger value="assurance" data-testid="document-layer-assurance">
            {t('documents.detail.layer_assurance', 'Assurance')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="control" className="mt-4 space-y-4">
          {canEditTitle && (
            <Card className="p-4 space-y-3" data-testid="document-title-edit">
              <h4 className="font-medium text-foreground">Document title</h4>
              <p className="text-xs text-muted-foreground">
                Edit the title on draft/working rows without opening a new version.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Input
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  data-testid="document-title-input"
                />
                <Button
                  size="sm"
                  onClick={() => void handleSaveTitle()}
                  disabled={savingTitle || !titleDraft.trim() || titleDraft.trim() === document.title}
                  data-testid="document-title-save"
                >
                  {savingTitle ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save title'}
                </Button>
              </div>
            </Card>
          )}

          {(() => {
            const downstream = buildDocumentDownstreamView(document)
            return (
              <Card data-testid="documents-downstream-thread">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Brain className="w-4 h-4 text-primary" />
                    {t('documents.downstream.panel.title')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="font-medium text-foreground">{t(downstream.titleKey)}</p>
                  <p className="text-sm text-muted-foreground">{t(downstream.descriptionKey)}</p>
                  {document.indexing_error ? (
                    <p className="text-sm text-amber-700 dark:text-amber-400 mt-1">{document.indexing_error}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {downstream.showExceptionsLink ? (
                      <Button variant="outline" size="sm" asChild>
                        <Link
                          to={buildDocumentsExceptionsHref(document.id)}
                          data-testid="documents-detail-exceptions-link"
                        >
                          {t('documents.downstream.open_exceptions')}
                        </Link>
                      </Button>
                    ) : null}
                    {downstream.showDocumentControlNote ? (
                      <Button variant="ghost" size="sm" asChild>
                        <Link
                          to={DOCUMENT_CONTROL_GOLDEN_THREAD_PATH}
                          data-testid="documents-detail-control-link"
                        >
                          {t('documents.downstream.open_document_control')}
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            )
          })()}

          {document.ai_summary && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="w-4 h-4 text-primary" />
                  AI Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-foreground">{document.ai_summary}</p>
              </CardContent>
            </Card>
          )}

          {document.ai_tags && document.ai_tags.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Tag className="w-4 h-4 text-primary" />
                  AI Tags
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {document.ai_tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileText className="w-4 h-4 text-primary" />
                Preview
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">{document.file_name}</p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => void handleOpenPreview(false)}>
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Open document
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowInlinePreview((prev) => !prev)}
                >
                  <Eye className="w-4 h-4 mr-2" />
                  {showInlinePreview ? 'Hide inline preview' : 'Show inline preview'}
                </Button>
              </div>
              {showInlinePreview ? (
                <Suspense
                  fallback={
                    <div className="flex justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  }
                >
                  <DocumentPdfPreview
                    documentId={document.id}
                    fileType={document.file_type}
                    fileName={document.file_name}
                  />
                </Suspense>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="coverage" className="mt-4 space-y-4">
          <div
            id={PROPOSED_EVIDENCE_ANCHOR_ID}
            ref={proposedSectionRef}
            data-testid="proposed-evidence-links"
            className="flex flex-wrap gap-2 scroll-mt-24"
          >
            <Button onClick={() => void handleMapEvidence()} disabled={mapping}>
              {mapping ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 mr-2" />
              )}
              Map with AI
            </Button>
            {proposedLinks.length > 0 && (
              <Button
                variant="secondary"
                onClick={() => void handleBulkConfirm()}
                disabled={selectedLinkIds.length === 0}
              >
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Bulk confirm proposed ({selectedLinkIds.length})
              </Button>
            )}
          </div>

          {evidenceLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : evidence.length === 0 ? (
            <EmptyState
              icon={<Sparkles className="w-8 h-8 text-muted-foreground" />}
              title="No evidence links"
              description={
                document.status === 'processing'
                  ? 'Indexing is still running — evidence links and AI Exceptions populate after indexing completes.'
                  : 'Run AI mapping to link this document to compliance standards, or review matches in AI Exceptions.'
              }
              action={
                document.status === 'indexed' ? (
                  <Button variant="outline" size="sm" asChild>
                    <Link
                      to={buildDocumentsExceptionsHref(document.id)}
                      data-testid="documents-evidence-exceptions-link"
                    >
                      {t('documents.downstream.open_exceptions')}
                    </Link>
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="space-y-3">
              {evidence.map((link) => {
                const isProposed = isProposedEvidenceLink(link)
                const evidenceQuote = isProposed ? parseEvidenceQuote(link) : null
                return (
                  <Card key={link.id} className="p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {evidenceStatusBadge(link)}
                          {link.scheme && (
                            <Badge variant="outline">{link.scheme}</Badge>
                          )}
                          {documentGraphEnabled ? (
                            <Link
                              to={complianceClauseHref(link.clause_id)}
                              className="font-mono text-xs text-primary hover:underline"
                              data-testid="document-clause-compliance-link"
                              title="Open clause on Compliance Evidence"
                            >
                              {link.clause_id}
                            </Link>
                          ) : (
                            <span className="font-mono text-xs text-muted-foreground">
                              {link.clause_id}
                            </span>
                          )}
                        </div>
                        {link.title && (
                          <p className="font-medium text-foreground">{link.title}</p>
                        )}
                        {isProposed && evidenceQuote?.snippet ? (
                          <blockquote
                            className="border-l-2 border-primary/40 pl-3 text-sm italic text-foreground"
                            data-testid="proposed-evidence-snippet"
                          >
                            &ldquo;{evidenceQuote.snippet}&rdquo;
                            {evidenceQuote.page != null ? (
                              <span className="block not-italic text-xs text-muted-foreground mt-1">
                                {t('documents.detail.evidence_page', { page: evidenceQuote.page })}
                              </span>
                            ) : null}
                          </blockquote>
                        ) : null}
                        {(!isProposed || !evidenceQuote?.snippet) && link.rationale ? (
                          <p className="text-sm text-muted-foreground">{link.rationale}</p>
                        ) : null}
                        {isProposed && evidenceQuote?.rationaleWithoutQuote ? (
                          <p className="text-sm text-muted-foreground">
                            {evidenceQuote.rationaleWithoutQuote}
                          </p>
                        ) : null}
                        {link.confidence != null && (
                          <p className="text-xs text-muted-foreground">
                            Confidence: {(link.confidence * 100).toFixed(0)}%
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {isProposed && (
                          <input
                            type="checkbox"
                            checked={selectedLinkIds.includes(link.id)}
                            onChange={() => toggleLinkSelection(link.id)}
                            aria-label={`Select link ${link.id}`}
                            className="rounded border-border"
                          />
                        )}
                        {isProposed && (
                          <>
                            <Button size="sm" onClick={() => void handleConfirmLink(link.id)}>
                              Confirm
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void handleRejectLink(link.id)}
                            >
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="related" className="mt-4 space-y-4">
          {documentGraphEnabled ? (
            <DocumentRelationshipsPanel
              documentId={document.id}
              documentTitle={document.title}
              documentType={document.document_type}
              edges={edges}
              loading={edgesLoading}
              error={edgesError}
              onChanged={loadEdges}
            />
          ) : (
            <Card className="p-4" data-testid="document-related-graph-off">
              <h3 className="font-medium text-foreground">
                {t('documents.detail.related_graph_off_title', 'Related links not recorded here')}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {t(
                  'documents.detail.related_graph_off_body',
                  'Document Graph is not switched on in this environment, so parent/child and reference links are not shown. That does not mean none exist — ask a platform admin to enable Doc Graph when relationship recording is required.',
                )}
              </p>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="used-by" className="mt-4 space-y-4">
          <div
            id={documentDetailSectionDomId('connections')}
            className="scroll-mt-24 space-y-2"
            data-testid="document-used-by-connections"
          >
            <h3 className="text-sm font-medium text-foreground">
              {t('documents.detail.used_by_connections', 'Connections')}
            </h3>
            <Entity360Strip
              entityType="document"
              entityId={document.id}
              documentGraphEnabled={documentGraphEnabled}
            />
          </div>
          <div
            id={documentDetailSectionDomId('campaign-results')}
            className="scroll-mt-24 space-y-2"
            data-testid="document-used-by-campaigns"
          >
            <h3 className="text-sm font-medium text-foreground">
              {t('documents.detail.used_by_campaigns', 'Campaigns')}
            </h3>
            <DocumentCampaignResults
              documentId={documentId}
              initialCampaignId={initialCampaignId}
            />
          </div>
        </TabsContent>

        <TabsContent value="history" className="mt-4 space-y-4">
          <DocumentVersionControlBar
            documentLabel={document.title}
            currentVersion={versionHistory?.current_version ?? document.version}
            status={versionHistory?.status ?? document.status}
            publishedVersion={versionHistory?.published_version}
            workingVersion={versionHistory?.working_version}
            versions={(versionHistory?.versions ?? []).map((v) => ({
              id: v.id,
              version_number: v.version_number,
              change_notes: v.change_notes,
              change_type: v.change_type,
              status: v.status,
              is_immutable: v.is_immutable,
              read_only: v.read_only,
              created_at: v.created_at,
              published_at: v.published_at,
            }))}
            loading={versionsLoading}
            error={versionsError}
            revising={revising}
            publishing={publishing}
            onRevise={handleReviseVersion}
            onPublish={handlePublishVersion}
            relationshipCounts={resolveDocumentRelationshipAmbientCounts(
              documentGraphEnabled,
              edgesError,
              relationshipSummary,
              relationshipCoverageHonesty.hasGap
                ? relationshipCoverageHonesty.headline
                : null,
            )}
          />
          <div className="flex justify-end">
            <Button variant="outline" size="sm" asChild>
              <Link to="/document-control">Open document control</Link>
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="assurance" className="mt-4 space-y-4">
          <div
            id={documentDetailSectionDomId('quiz')}
            className="scroll-mt-24 space-y-4"
            data-testid="document-assurance-quiz"
          >
            {quizAiFallback ? (
              <div
                className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground"
                role="alert"
                data-testid="quiz-ai-fallback-banner"
              >
                {t('documents.detail.quiz_ai_fallback')}
              </div>
            ) : null}
            <Card className="p-4 space-y-4">
              <h3 className="font-medium text-foreground">Generate comprehension quiz</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="gkb-question-count" className="text-sm text-muted-foreground">
                    Question count
                  </label>
                  <Input
                    id="gkb-question-count"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    min={1}
                    max={30}
                    value={questionCountInput}
                    onChange={(e) =>
                      setQuestionCountInput(normalizeQuestionCountInput(e.target.value))
                    }
                    onBlur={() =>
                      setQuestionCountInput(String(sanitizeQuestionCount(questionCountInput)))
                    }
                  />
                </div>
                <div>
                  <label htmlFor="gkb-pass-mark" className="text-sm text-muted-foreground">
                    Pass mark (%)
                  </label>
                  <Input
                    id="gkb-pass-mark"
                    type="number"
                    min={0}
                    max={100}
                    value={passMark}
                    onChange={(e) => setPassMark(Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeMcq}
                    onChange={(e) => setIncludeMcq(e.target.checked)}
                  />
                  Include MCQ
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeOpen}
                    onChange={(e) => setIncludeOpen(e.target.checked)}
                  />
                  Include open questions
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={autoApproveQuiz}
                    onChange={(e) => setAutoApproveQuiz(e.target.checked)}
                  />
                  Auto-approve if quality
                </label>
              </div>
              <Button onClick={() => void handleGenerateQuiz()} disabled={quizGenerating}>
                {quizGenerating ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4 mr-2" />
                )}
                Generate quiz
              </Button>
            </Card>

            {quizDraft && (
              <Card className="p-4 space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <h3 className="font-medium text-foreground">Quiz draft</h3>
                    <p className="text-sm text-muted-foreground">
                      {quizDraft.questions.length} questions · pass {quizDraft.pass_mark}% ·{' '}
                      {quizDraft.status}
                    </p>
                  </div>
                  {quizDraft.status !== 'approved' && (
                    <Button onClick={() => void handleApproveQuiz()} disabled={quizApproving}>
                      {quizApproving ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 mr-2" />
                      )}
                      Approve
                    </Button>
                  )}
                </div>
                <div className="space-y-3">
                  {(quizDraft.questions as Array<{ question?: string; type?: string }>).map(
                    (q, idx) => (
                      <div key={idx} className="rounded-lg border border-border p-3">
                        <p className="text-sm font-medium text-foreground">
                          {idx + 1}. {q.question ?? JSON.stringify(q)}
                        </p>
                        {q.type && (
                          <Badge variant="outline" className="mt-2 text-xs">
                            {q.type}
                          </Badge>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </Card>
            )}
          </div>

          <div
            id={documentDetailSectionDomId('share')}
            className="scroll-mt-24"
            data-testid="document-assurance-share"
          >
            <DocumentCampaignPanel
              documentId={documentId}
              hasApprovedQuiz={quizDraft?.status === 'approved'}
            />
          </div>

          <div
            id={documentDetailSectionDomId('qa')}
            className="scroll-mt-24 space-y-4"
            data-testid="document-assurance-qa"
          >
            <Card className="p-4 space-y-3">
              <h3 className="font-medium text-foreground">Start a discussion</h3>
              <Input
                placeholder="Thread title (optional)"
                value={newThreadTitle}
                onChange={(e) => setNewThreadTitle(e.target.value)}
              />
              <Button onClick={() => void handleCreateThread()}>
                <MessageSquare className="w-4 h-4 mr-2" />
                Ask a question
              </Button>
            </Card>

            {threads.length === 0 ? (
              <EmptyState
                icon={<MessageSquare className="w-8 h-8 text-muted-foreground" />}
                title="No discussions yet"
                description="Create a thread to ask questions about this document."
              />
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <Card className="p-2 lg:col-span-1">
                  <div className="space-y-1">
                    {threads.map((thread) => (
                      <button
                        key={thread.id}
                        type="button"
                        onClick={() => {
                          setActiveThreadId(thread.id)
                          void loadThreadMessages(thread.id)
                        }}
                        className={cn(
                          'w-full text-left rounded-lg px-3 py-2 text-sm transition-colors',
                          activeThreadId === thread.id
                            ? 'bg-primary/10 text-primary'
                            : 'hover:bg-muted/50 text-foreground',
                        )}
                      >
                        {thread.title ?? `Thread #${thread.id}`}
                      </button>
                    ))}
                  </div>
                </Card>
                <Card className="p-4 lg:col-span-2 space-y-4">
                  {activeThreadId ? (
                    <>
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {messagesLoading ? (
                          <div className="flex justify-center py-4">
                            <Loader2 className="w-5 h-5 animate-spin text-primary" />
                          </div>
                        ) : (threadMessages[activeThreadId] ?? []).length === 0 ? (
                          <p className="text-sm text-muted-foreground">No messages yet.</p>
                        ) : (
                          (threadMessages[activeThreadId] ?? []).map((msg) => (
                            <div
                              key={msg.id}
                              className="rounded-lg border border-border p-3 text-sm"
                            >
                              <p className="text-foreground">{msg.body}</p>
                              <div className="flex items-center gap-2 mt-1">
                                {msg.is_ai_draft && (
                                  <Badge variant="outline" className="text-xs">
                                    AI draft
                                  </Badge>
                                )}
                                <span className="text-xs text-muted-foreground">
                                  {new Date(msg.created_at).toLocaleString()}
                                </span>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                      <Textarea
                        placeholder="Write your message…"
                        value={messageBody}
                        onChange={(e) => setMessageBody(e.target.value)}
                        rows={3}
                      />
                      <div className="flex flex-wrap items-center gap-3">
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={useAiDraft}
                            onChange={(e) => setUseAiDraft(e.target.checked)}
                          />
                          Use AI draft
                        </label>
                        <Button
                          onClick={() => void handlePostMessage()}
                          disabled={postingMessage || !messageBody.trim()}
                        >
                          {postingMessage ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          ) : null}
                          Post
                        </Button>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">Select a thread to view messages.</p>
                  )}
                </Card>
              </div>
            )}
          </div>

          <div
            id={documentDetailSectionDomId('watch')}
            className="scroll-mt-24 space-y-4"
            data-testid="document-assurance-watch"
          >
            {impacts.length === 0 ? (
              <EmptyState
                icon={<Eye className="w-8 h-8 text-muted-foreground" />}
                title="No regulatory impacts"
                description="No watch impacts are linked to this document yet."
              />
            ) : (
              <div className="space-y-3">
                {impacts.map((impact) => (
                  <Card key={impact.id} className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-foreground">Update {impact.update_id}</p>
                        {impact.rationale && (
                          <p className="text-sm text-muted-foreground mt-1">{impact.rationale}</p>
                        )}
                      </div>
                      <Badge variant="outline">{impact.status}</Badge>
                    </div>
                    {impact.confidence != null && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Confidence: {(impact.confidence * 100).toFixed(0)}%
                      </p>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <Dialog
        open={publishPreviewOpen}
        onOpenChange={(open) => {
          if (publishing) return
          setPublishPreviewOpen(open)
          if (!open) {
            setPublishPreview(null)
            setPublishPreviewError(null)
          }
        }}
      >
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Publish impact preview</DialogTitle>
            <DialogDescription>
              Confirm side effects before publishing this library document version.
            </DialogDescription>
          </DialogHeader>
          <DocumentPublishImpactPreview
            documentTitle={document?.title || `Document #${documentId}`}
            preview={publishPreview}
            loading={publishPreviewLoading}
            error={publishPreviewError}
            publishing={publishing}
            canPublish={publishCanPublish}
            degradedReasons={publishDegradedReasons}
            onCancel={() => {
              if (publishing) return
              setPublishPreviewOpen(false)
              setPublishPreview(null)
              setPublishPreviewError(null)
              setPublishCanPublish(true)
              setPublishDegradedReasons([])
            }}
            onConfirm={() => {
              if (!publishCanPublish) return
              void executePublishVersion()
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}
