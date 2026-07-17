import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  FileText,
  AlertTriangle,
  MessageSquare,
  Car,
  ClipboardCheck,
  MoreVertical,
  Edit,
  Copy,
  Trash2,
  Eye,
  Check,
  X,
  Loader2,
} from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/Dialog'
import { cn } from '../../helpers/utils'
import { formConfigApi, type FormTemplateListItem } from '../../api/formConfigClient'
import { captureAdminLoadError } from './adminLoadHelpers'

const FORM_TYPE_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  incident: {
    label: 'Incident',
    icon: <AlertTriangle className="w-4 h-4" />,
    color: 'text-destructive bg-destructive/10',
  },
  near_miss: {
    label: 'Near Miss',
    icon: <AlertTriangle className="w-4 h-4" />,
    color: 'text-warning bg-warning/10',
  },
  complaint: {
    label: 'Complaint',
    icon: <MessageSquare className="w-4 h-4" />,
    color: 'text-info bg-info/10',
  },
  rta: {
    label: 'RTA',
    icon: <Car className="w-4 h-4" />,
    color: 'text-purple-600 bg-purple-100',
  },
  audit: {
    label: 'Audit',
    icon: <ClipboardCheck className="w-4 h-4" />,
    color: 'text-primary bg-primary/10',
  },
  custom: {
    label: 'Custom',
    icon: <FileText className="w-4 h-4" />,
    color: 'text-muted-foreground bg-muted',
  },
}

export default function FormsList() {
  const navigate = useNavigate()
  const [forms, setForms] = useState<FormTemplateListItem[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string | null>(null)
  const [activeMenu, setActiveMenu] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const loadForms = async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const response = await formConfigApi.listTemplates({ page_size: 100 })
      setForms(response.items)
    } catch (err) {
      setLoadError(
        captureAdminLoadError(
          err,
          { component: 'FormsList', action: 'load' },
          'Unable to load forms. Please try again.',
        ),
      )
      setForms([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadForms()
  }, [])

  const filteredForms = forms.filter((form) => {
    const matchesSearch =
      form.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      form.description?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = !filterType || form.form_type === filterType
    return matchesSearch && matchesType
  })

  const handleDelete = (id: number) => {
    setDeleteTarget(id)
    setActiveMenu(null)
  }

  const confirmDelete = async () => {
    if (deleteTarget === null) return
    setActionError(null)
    try {
      await formConfigApi.deleteTemplate(deleteTarget)
      setForms((prev) => prev.filter((f) => f.id !== deleteTarget))
    } catch {
      setActionError('Failed to delete form.')
    } finally {
      setDeleteTarget(null)
    }
  }

  const handleDuplicate = async (form: FormTemplateListItem) => {
    setActionError(null)
    setActiveMenu(null)
    try {
      const source = await formConfigApi.getTemplate(form.id)
      const copySlug = `${source.slug}-copy-${Date.now()}`
      const created = await formConfigApi.createTemplate({
        name: `${source.name} (Copy)`,
        slug: copySlug,
        description: source.description,
        form_type: source.form_type,
        icon: source.icon,
        color: source.color,
        allow_drafts: source.allow_drafts,
        allow_attachments: source.allow_attachments,
        require_signature: source.require_signature,
        auto_assign_reference: source.auto_assign_reference,
        reference_prefix: source.reference_prefix,
        notify_on_submit: source.notify_on_submit,
        notification_emails: source.notification_emails,
        steps: source.steps.map((step, stepIndex) => ({
          name: step.name,
          description: step.description,
          order: stepIndex,
          icon: step.icon,
          fields: step.fields.map((field, fieldIndex) => ({
            name: field.name,
            label: field.label,
            field_type: field.field_type,
            order: fieldIndex,
            placeholder: field.placeholder,
            help_text: field.help_text,
            is_required: field.is_required,
            options: field.options,
            width: field.width,
          })),
        })),
      })
      setForms((prev) => [
        ...prev,
        {
          id: created.id,
          name: created.name,
          slug: created.slug,
          form_type: created.form_type,
          description: created.description,
          is_active: created.is_active,
          is_published: created.is_published,
          version: created.version,
          steps_count: created.steps.length,
          fields_count: created.steps.reduce((sum, step) => sum + step.fields.length, 0),
          updated_at: created.updated_at,
        },
      ])
    } catch {
      setActionError('Failed to duplicate form.')
    }
  }

  const togglePublish = async (form: FormTemplateListItem) => {
    setActionError(null)
    setActiveMenu(null)
    try {
      const updated = form.is_published
        ? await formConfigApi.updateTemplate(form.id, { is_published: false })
        : await formConfigApi.publishTemplate(form.id)
      setForms((prev) =>
        prev.map((f) =>
          f.id === form.id
            ? {
                ...f,
                is_published: updated.is_published,
                version: updated.version,
                updated_at: updated.updated_at,
              }
            : f,
        ),
      )
    } catch {
      setActionError('Failed to update publish status.')
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Form Builder</h1>
              <p className="text-muted-foreground mt-1">
                Create and manage customizable forms for incidents, complaints, and more
              </p>
            </div>
            <Button onClick={() => navigate('/admin/forms/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Create New Form
            </Button>
          </div>

          {/* Filters */}
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search forms..."
                className="pl-10"
              />
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setFilterType(null)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                  !filterType
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                All
              </button>
              {Object.entries(FORM_TYPE_CONFIG).map(([type, config]) => (
                <button
                  key={type}
                  onClick={() => setFilterType(type === filterType ? null : type)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5',
                    filterType === type
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:text-foreground',
                  )}
                >
                  {config.icon}
                  {config.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Forms Grid */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {actionError && (
          <p className="text-sm text-destructive mb-4" role="alert">
            {actionError}
          </p>
        )}

        {isLoading ? (
          <Card className="p-12 text-center">
            <Loader2 className="w-8 h-8 mx-auto text-muted-foreground animate-spin mb-4" />
            <p className="text-muted-foreground">Loading forms...</p>
          </Card>
        ) : loadError ? (
          <Card className="p-12 text-center">
            <p className="text-destructive mb-4">{loadError}</p>
            <Button variant="outline" onClick={() => void loadForms()}>
              Retry
            </Button>
          </Card>
        ) : filteredForms.length === 0 ? (
          <Card className="p-12 text-center">
            <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">No forms found</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery
                ? 'Try adjusting your search or filters'
                : 'Get started by creating your first form'}
            </p>
            <Button onClick={() => navigate('/admin/forms/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Create New Form
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredForms.map((form) => {
              const typeConfig = FORM_TYPE_CONFIG[form.form_type] || FORM_TYPE_CONFIG.custom

              return (
                <Card
                  key={form.id}
                  className="p-5 hover:shadow-md transition-shadow cursor-pointer group relative"
                  onClick={() => navigate(`/admin/forms/${form.id}`)}
                >
                  {/* Status Badges */}
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
                        typeConfig.color,
                      )}
                    >
                      {typeConfig.icon}
                      {typeConfig.label}
                    </span>
                    <div className="flex items-center gap-2">
                      {form.is_published ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                          <Check className="w-3 h-3" />
                          Published
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-muted text-muted-foreground rounded-full text-xs">
                          Draft
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Form Details */}
                  <h3 className="text-lg font-semibold text-foreground mb-1 group-hover:text-primary transition-colors">
                    {form.name}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {form.description || 'No description'}
                  </p>

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{form.steps_count} steps</span>
                    <span>•</span>
                    <span>{form.fields_count} fields</span>
                    <span>•</span>
                    <span>v{form.version}</span>
                  </div>

                  {/* Actions Menu */}
                  <div className="absolute top-4 right-4">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setActiveMenu(activeMenu === form.id ? null : form.id)
                      }}
                      className="p-2 hover:bg-muted rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <MoreVertical className="w-4 h-4 text-muted-foreground" />
                    </button>

                    {activeMenu === form.id && (
                      <div
                        className="absolute right-0 top-full mt-1 w-48 bg-card border border-border rounded-xl shadow-lg z-10 overflow-hidden"
                        role="button"
                        tabIndex={0}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') e.stopPropagation()
                        }}
                      >
                        <button
                          onClick={() => navigate(`/admin/forms/${form.id}`)}
                          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                          <Edit className="w-4 h-4" />
                          Edit Form
                        </button>
                        <button
                          onClick={() => {}}
                          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                          Preview
                        </button>
                        <button
                          onClick={() => void handleDuplicate(form)}
                          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                          <Copy className="w-4 h-4" />
                          Duplicate
                        </button>
                        <button
                          onClick={() => void togglePublish(form)}
                          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                          {form.is_published ? (
                            <>
                              <X className="w-4 h-4" />
                              Unpublish
                            </>
                          ) : (
                            <>
                              <Check className="w-4 h-4" />
                              Publish
                            </>
                          )}
                        </button>
                        <hr className="border-border" />
                        <button
                          onClick={() => handleDelete(form.id)}
                          className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </main>

      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Form</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete this form? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => void confirmDelete()}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
