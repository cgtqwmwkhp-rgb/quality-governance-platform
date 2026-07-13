import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText,
  Loader2,
  Plus,
  ChevronRight,
  Send,
  CheckCircle2,
} from 'lucide-react'
import {
  documentControlApi,
  getApiErrorMessage,
  type ControlledDocumentDetail,
  type ControlledDocumentSummary,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { cn } from '../helpers/utils'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

const statusVariant = (status: string) => {
  switch (status) {
    case 'approved':
    case 'effective':
      return 'success'
    case 'draft':
      return 'secondary'
    case 'in_review':
      return 'in-progress'
    case 'obsolete':
      return 'destructive'
    default:
      return 'outline'
  }
}

export default function DocumentControl() {
  const [documents, setDocuments] = useState<ControlledDocumentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<ControlledDocumentDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const [createForm, setCreateForm] = useState({
    title: '',
    document_type: 'procedure',
    category: 'general',
    description: '',
  })

  const [distributeForm, setDistributeForm] = useState({
    recipient_type: 'user',
    recipient_name: '',
    recipient_email: '',
  })

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentControlApi.list({ limit: 100 })
      setDocuments(response.data.documents ?? [])
    } catch (err) {
      setError(reportFailure(err))
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (documentId: number) => {
    setDetailLoading(true)
    try {
      const response = await documentControlApi.get(documentId)
      setDetail(response.data)
    } catch (err) {
      reportFailure(err)
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDocuments()
  }, [loadDocuments])

  useEffect(() => {
    if (selectedId) {
      void loadDetail(selectedId)
    } else {
      setDetail(null)
    }
  }, [selectedId, loadDetail])

  const handleCreate = async () => {
    if (createForm.title.trim().length < 5) {
      toast.error('Title must be at least 5 characters')
      return
    }
    setCreating(true)
    try {
      const response = await documentControlApi.create({
        title: createForm.title.trim(),
        document_type: createForm.document_type,
        category: createForm.category,
        description: createForm.description.trim() || undefined,
      })
      toast.success(`Created ${response.data.document_number}`)
      setShowCreate(false)
      setCreateForm({ title: '', document_type: 'procedure', category: 'general', description: '' })
      await loadDocuments()
      setSelectedId(response.data.id)
    } catch (err) {
      reportFailure(err)
    } finally {
      setCreating(false)
    }
  }

  const handleSubmitForApproval = async () => {
    if (!selectedId) return
    setSubmitting(true)
    try {
      await documentControlApi.submitForApproval(selectedId)
      toast.success('Submitted for approval')
      await loadDetail(selectedId)
      await loadDocuments()
    } catch (err) {
      reportFailure(err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDistribute = async () => {
    if (!selectedId || !distributeForm.recipient_name.trim()) return
    try {
      await documentControlApi.distribute(selectedId, {
        recipient_type: distributeForm.recipient_type,
        recipient_name: distributeForm.recipient_name.trim(),
        recipient_email: distributeForm.recipient_email.trim() || undefined,
        acknowledgment_required: true,
      })
      toast.success('Document distributed')
      setDistributeForm({ recipient_type: 'user', recipient_name: '', recipient_email: '' })
      await loadDetail(selectedId)
    } catch (err) {
      reportFailure(err)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Document Control</h1>
          <p className="text-muted-foreground mt-1">
            Controlled document lifecycle — versions, approval, and distribution
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to="/documents">Library</Link>
          </Button>
          <Button onClick={() => setShowCreate((v) => !v)}>
            <Plus className="w-4 h-4 mr-2" />
            New draft
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {showCreate && (
        <Card className="p-4 space-y-4">
          <h2 className="font-medium text-foreground">Create draft shell</h2>
          <Input
            placeholder="Title"
            value={createForm.title}
            onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              value={createForm.document_type}
              onValueChange={(v) => setCreateForm((f) => ({ ...f, document_type: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="policy">Policy</SelectItem>
                <SelectItem value="procedure">Procedure</SelectItem>
                <SelectItem value="work_instruction">Work instruction</SelectItem>
                <SelectItem value="form">Form</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Category"
              value={createForm.category}
              onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))}
            />
          </div>
          <Textarea
            placeholder="Description (optional)"
            value={createForm.description}
            onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
            rows={2}
          />
          <Button onClick={() => void handleCreate()} disabled={creating}>
            {creating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
            Create draft
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-1 space-y-2">
          {documents.length === 0 ? (
            <EmptyState
              icon={<FileText className="w-8 h-8 text-muted-foreground" />}
              title="No controlled documents"
              description="Create a draft shell to start the controlled document workflow."
            />
          ) : (
            documents.map((doc) => (
              <Card
                key={doc.id}
                hoverable
                onClick={() => setSelectedId(doc.id)}
                className={cn(
                  'p-4 cursor-pointer',
                  selectedId === doc.id && 'border-primary shadow-md',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-xs text-primary">{doc.document_number}</p>
                    <p className="font-medium text-foreground truncate">{doc.title}</p>
                    <p className="text-xs text-muted-foreground capitalize mt-1">
                      {doc.document_type} · v{doc.current_version}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                </div>
                <div className="mt-2">
                  <Badge variant={statusVariant(doc.status) as 'success'}>{doc.status}</Badge>
                </div>
              </Card>
            ))
          )}
        </div>

        <div className="xl:col-span-2">
          {!selectedId ? (
            <Card className="p-12 text-center">
              <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">Select a controlled document to view details</p>
            </Card>
          ) : detailLoading ? (
            <Card className="p-12 flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </Card>
          ) : detail ? (
            <div className="space-y-4">
              <Card className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-sm text-primary">{detail.document_number}</p>
                    <h2 className="text-xl font-bold text-foreground">{detail.title}</h2>
                    <p className="text-sm text-muted-foreground mt-1 capitalize">
                      {detail.document_type} · {detail.category} · v{detail.current_version}
                    </p>
                  </div>
                  <Badge variant={statusVariant(detail.status) as 'success'}>{detail.status}</Badge>
                </div>
                {detail.description && (
                  <p className="text-sm text-muted-foreground mt-3">{detail.description}</p>
                )}
                {detail.status === 'draft' && (
                  <Button
                    className="mt-4"
                    onClick={() => void handleSubmitForApproval()}
                    disabled={submitting}
                  >
                    {submitting ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                    )}
                    Submit for approval
                  </Button>
                )}
              </Card>

              <Card className="p-4">
                <h3 className="font-medium text-foreground mb-3">Versions</h3>
                {detail.versions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No version history yet.</p>
                ) : (
                  <div className="space-y-2">
                    {detail.versions.map((v) => (
                      <div
                        key={v.id}
                        className="rounded-lg border border-border p-3 text-sm"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">v{v.version_number}</span>
                          <Badge variant="outline">{v.status}</Badge>
                        </div>
                        <p className="text-muted-foreground mt-1">{v.change_summary}</p>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card className="p-4 space-y-4">
                <h3 className="font-medium text-foreground">Distribute</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Select
                    value={distributeForm.recipient_type}
                    onValueChange={(v) =>
                      setDistributeForm((f) => ({ ...f, recipient_type: v }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">User</SelectItem>
                      <SelectItem value="department">Department</SelectItem>
                      <SelectItem value="role">Role</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="Recipient name"
                    value={distributeForm.recipient_name}
                    onChange={(e) =>
                      setDistributeForm((f) => ({ ...f, recipient_name: e.target.value }))
                    }
                  />
                  <Input
                    placeholder="Email (optional)"
                    value={distributeForm.recipient_email}
                    onChange={(e) =>
                      setDistributeForm((f) => ({ ...f, recipient_email: e.target.value }))
                    }
                  />
                </div>
                <Button onClick={() => void handleDistribute()}>
                  <Send className="w-4 h-4 mr-2" />
                  Distribute
                </Button>

                {detail.distributions.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-border">
                    {detail.distributions.map((d) => (
                      <div
                        key={d.id}
                        className="flex items-center justify-between text-sm"
                      >
                        <span>{d.recipient_name}</span>
                        <Badge variant={d.acknowledged ? 'success' : 'outline'}>
                          {d.acknowledged ? 'Acknowledged' : 'Pending'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          ) : (
            <EmptyState
              icon={<FileText className="w-8 h-8 text-muted-foreground" />}
              title="Could not load document"
              description="Retry by selecting the document again."
            />
          )}
        </div>
      </div>
    </div>
  )
}
