import { useEffect, useState } from 'react'
import { Plus, FileText, Search, Loader2 } from 'lucide-react'
import { policiesApi, Policy, PolicyCreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'

export default function Policies() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<PolicyCreate>({
    title: '',
    description: '',
    document_type: 'policy',
    category: '',
    department: '',
    review_frequency_months: 12,
  })

  useEffect(() => {
    loadPolicies()
  }, [])

  const loadPolicies = async () => {
    try {
      const response = await policiesApi.list(1, 50)
      setPolicies(response.data.items ?? [])
    } catch (err) {
      console.error('Failed to load policies:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await policiesApi.create(formData)
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        document_type: 'policy',
        category: '',
        department: '',
        review_frequency_months: 12,
      })
      loadPolicies()
    } catch (err) {
      console.error('Failed to create policy:', err)
    } finally {
      setCreating(false)
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'policy': return '📜'
      case 'procedure': return '📋'
      case 'work_instruction': return '📝'
      case 'sop': return '📘'
      case 'form': return '📄'
      case 'template': return '📑'
      case 'guideline': return '📖'
      case 'manual': return '📚'
      case 'record': return '🗂️'
      default: return '📎'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'published': return 'resolved'
      case 'approved': return 'success'
      case 'under_review': return 'in-progress'
      case 'draft': return 'submitted'
      case 'superseded': return 'closed'
      case 'retired': return 'destructive'
      default: return 'secondary'
    }
  }

  const filteredPolicies = policies.filter(
    p => p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         p.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         (p.category || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Policies & Documents</h1>
          <p className="text-muted-foreground mt-1">Manage policies, procedures, and documents</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Document
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search documents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPolicies.length === 0 ? (
          <div className="col-span-full">
            <Card className="p-12 text-center">
              <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <p className="text-muted-foreground">No documents found</p>
              <p className="text-sm text-muted-foreground mt-1">Create your first document to get started</p>
            </Card>
          </div>
        ) : (
          filteredPolicies.map((policy) => (
            <Card
              key={policy.id}
              hoverable
              className="p-5 cursor-pointer"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-2xl">
                  {getTypeIcon(policy.document_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-xs text-primary mb-1">{policy.reference_number}</p>
                  <h3 className="font-semibold text-foreground truncate">{policy.title}</h3>
                  {policy.description && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{policy.description}</p>
                  )}
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <Badge variant={getStatusVariant(policy.status) as any}>
                  {policy.status.replace('_', ' ')}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {policy.document_type.replace('_', ' ')}
                </span>
              </div>
              {policy.next_review_date && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-muted-foreground">
                    Review due: {new Date(policy.next_review_date).toLocaleDateString()}
                  </p>
                </div>
              )}
            </Card>
          ))
        )}
      </div>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Document</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Title</label>
              <Input
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Document title..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description</label>
              <Textarea
                rows={3}
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of the document..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Type</label>
                <Select
                  value={formData.document_type}
                  onValueChange={(value) => setFormData({ ...formData, document_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="policy">Policy</SelectItem>
                    <SelectItem value="procedure">Procedure</SelectItem>
                    <SelectItem value="work_instruction">Work Instruction</SelectItem>
                    <SelectItem value="sop">SOP</SelectItem>
                    <SelectItem value="form">Form</SelectItem>
                    <SelectItem value="template">Template</SelectItem>
                    <SelectItem value="guideline">Guideline</SelectItem>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="record">Record</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Review Frequency</label>
                <Select
                  value={String(formData.review_frequency_months)}
                  onValueChange={(value) => setFormData({ ...formData, review_frequency_months: parseInt(value) })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select frequency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="6">6 months</SelectItem>
                    <SelectItem value="12">12 months</SelectItem>
                    <SelectItem value="24">24 months</SelectItem>
                    <SelectItem value="36">36 months</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Category</label>
                <Input
                  type="text"
                  value={formData.category || ''}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  placeholder="e.g., Health & Safety"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Department</label>
                <Input
                  type="text"
                  value={formData.department || ''}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  placeholder="e.g., Operations"
                />
              </div>
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Create Document'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
