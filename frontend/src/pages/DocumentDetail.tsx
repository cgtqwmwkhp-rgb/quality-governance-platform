import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
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
} from 'lucide-react'
import api, {
  getApiErrorMessage,
  knowledgeBankApi,
  type DiscussionMessage,
  type DiscussionThread,
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
import { cn } from '../helpers/utils'
import {
  PROPOSED_EVIDENCE_ANCHOR_ID,
  resolveDocumentDetailTab,
  shouldScrollToProposedEvidence,
} from './documentEvidenceTab'

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
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const documentId = Number(id)
  const defaultTab = resolveDocumentDetailTab(searchParams.get('tab'))
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
  const [questionCount, setQuestionCount] = useState(5)
  const [passMark, setPassMark] = useState(70)
  const [includeMcq, setIncludeMcq] = useState(true)
  const [includeOpen, setIncludeOpen] = useState(true)
  const [autoApproveQuiz, setAutoApproveQuiz] = useState(false)

  const [threads, setThreads] = useState<DiscussionThread[]>([])
  const [threadMessages, setThreadMessages] = useState<Record<number, DiscussionMessage[]>>({})
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null)
  const [newThreadTitle, setNewThreadTitle] = useState('')
  const [messageBody, setMessageBody] = useState('')
  const [useAiDraft, setUseAiDraft] = useState(false)
  const [postingMessage, setPostingMessage] = useState(false)

  const [impacts, setImpacts] = useState<RegulatoryImpact[]>([])

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
    } catch (err) {
      setPartialLoad(true)
      reportFailure(err)
    }
  }, [documentId])

  const loadImpacts = useCallback(async () => {
    try {
      const response = await knowledgeBankApi.listImpacts()
      setImpacts(response.data.filter((i) => i.document_id === documentId))
    } catch (err) {
      setPartialLoad(true)
      reportFailure(err)
    }
  }, [documentId])

  useEffect(() => {
    void loadDocument()
    void loadEvidence()
    void loadThreads()
    void loadImpacts()
  }, [loadDocument, loadEvidence, loadThreads, loadImpacts])

  // /documents/:id?tab=evidence → Standards & Evidence, scroll to proposed links.
  useEffect(() => {
    if (!shouldScrollToProposedEvidence(searchParams.get('tab'), window.location.hash)) return
    if (evidenceLoading) return
    const node = proposedSectionRef.current
    if (!node) return
    node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [defaultTab, evidenceLoading, evidence.length, searchParams])

  const handleOpenPreview = async (download = false) => {
    if (!document) return
    try {
      const response = await api.get<{ url: string }>(
        `/api/v1/documents/${document.id}/signed-url`,
        { params: { download } },
      )
      window.open(response.data.url, '_blank', 'noopener,noreferrer')
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
    try {
      const response = await knowledgeBankApi.generateQuiz(documentId, {
        question_count: questionCount,
        include_mcq: includeMcq,
        include_open: includeOpen,
        pass_mark: passMark,
        auto_approve_if_quality: autoApproveQuiz,
      })
      setQuizDraft(response.data)
      toast.success('Quiz draft generated')
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
        </div>
        <div className="flex gap-2">
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

      <Tabs defaultValue={defaultTab} key={defaultTab}>
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Standards & Evidence</TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
          <TabsTrigger value="quiz">Share & Quiz</TabsTrigger>
          <TabsTrigger value="qa">Q&A</TabsTrigger>
          <TabsTrigger value="watch">Watch</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 space-y-4">
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
            <CardContent className="space-y-2">
              <p className="text-sm text-muted-foreground">{document.file_name}</p>
              <Button variant="outline" size="sm" onClick={() => void handleOpenPreview(false)}>
                <ExternalLink className="w-4 h-4 mr-2" />
                Open document
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evidence" className="mt-4 space-y-4">
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
              description="Run AI mapping to link this document to compliance standards."
            />
          ) : (
            <div className="space-y-3">
              {evidence.map((link) => {
                const isProposed =
                  link.status === 'proposed' || link.status === 'needs_review'
                return (
                  <Card key={link.id} className="p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {evidenceStatusBadge(link)}
                          {link.scheme && (
                            <Badge variant="outline">{link.scheme}</Badge>
                          )}
                          <span className="font-mono text-xs text-muted-foreground">
                            {link.clause_id}
                          </span>
                        </div>
                        {link.title && (
                          <p className="font-medium text-foreground">{link.title}</p>
                        )}
                        {link.rationale && (
                          <p className="text-sm text-muted-foreground">{link.rationale}</p>
                        )}
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

        <TabsContent value="versions" className="mt-4 space-y-4">
          <Card className="p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium text-foreground">Current version</p>
                <p className="text-sm text-muted-foreground">v{document.version}</p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/document-control">Controlled docs</Link>
              </Button>
            </div>
            <p className="text-sm text-muted-foreground mt-3">
              Promote this library document through document control for formal versioning,
              approval, and distribution.
            </p>
          </Card>
        </TabsContent>

        <TabsContent value="quiz" className="mt-4 space-y-4">
          <Card className="p-4 space-y-4">
            <h3 className="font-medium text-foreground">Generate comprehension quiz</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="gkb-question-count" className="text-sm text-muted-foreground">
                  Question count
                </label>
                <Input
                  id="gkb-question-count"
                  type="number"
                  min={1}
                  max={30}
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Number(e.target.value))}
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
        </TabsContent>

        <TabsContent value="qa" className="mt-4 space-y-4">
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
                      onClick={() => setActiveThreadId(thread.id)}
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
                      {(threadMessages[activeThreadId] ?? []).length === 0 ? (
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
        </TabsContent>

        <TabsContent value="watch" className="mt-4 space-y-4">
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
        </TabsContent>
      </Tabs>
    </div>
  )
}
