import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, MessageSquare, Search, Loader2 } from 'lucide-react'
import { complaintsApi, Complaint, ComplaintCreate, getApiErrorMessage } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
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

export default function Complaints() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<ComplaintCreate>({
    title: '',
    description: '',
    complaint_type: 'other',
    priority: 'medium',
    received_date: new Date().toISOString().slice(0, 16),
    complainant_name: '',
    complainant_email: '',
    complainant_phone: '',
  })

  useEffect(() => {
    loadComplaints()
  }, [])

  const loadComplaints = async () => {
    try {
      const response = await complaintsApi.list(1, 50)
      setComplaints(response.data.items ?? [])
    } catch (err) {
      console.error('Failed to load complaints:', err)
      setFormError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.title.trim() || !formData.description.trim()) {
      setFormError(t('complaints.form.required_error'))
      return
    }
    setFormError(null)
    setCreating(true)
    try {
      await complaintsApi.create({
        ...formData,
        received_date: new Date(formData.received_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        complaint_type: 'other',
        priority: 'medium',
        received_date: new Date().toISOString().slice(0, 16),
        complainant_name: '',
        complainant_email: '',
        complainant_phone: '',
      })
      loadComplaints()
    } catch (err) {
      console.error('Failed to create complaint:', err)
      setFormError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const getPriorityVariant = (priority: string) => {
    switch (priority) {
      case 'critical': return 'critical'
      case 'high': return 'high'
      case 'medium': return 'medium'
      case 'low': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': case 'resolved': return 'resolved'
      case 'received': return 'submitted'
      case 'acknowledged': return 'acknowledged'
      case 'under_investigation': return 'in-progress'
      case 'pending_response': return 'awaiting-user'
      case 'awaiting_customer': return 'awaiting-user'
      case 'escalated': return 'critical'
      default: return 'secondary'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'product': return '📦'
      case 'service': return '🛠️'
      case 'delivery': return '🚚'
      case 'communication': return '📞'
      case 'billing': return '💳'
      case 'staff': return '👤'
      case 'environmental': return '🌿'
      case 'safety': return '⚠️'
      default: return '📋'
    }
  }

  const filteredComplaints = complaints.filter(
    c => c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         c.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         c.complainant_name.toLowerCase().includes(searchTerm.toLowerCase())
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
          <h1 className="text-2xl font-bold text-foreground">{t('complaints.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('complaints.subtitle')}</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          {t('complaints.new')}
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('complaints.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Complaints Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.reference')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.title')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.type')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.complainant')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.priority')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.status')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('complaints.table.received')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredComplaints.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                      <MessageSquare className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                      <p>{t('complaints.empty.title')}</p>
                      <p className="text-sm mt-1">{t('complaints.empty.subtitle')}</p>
                    </td>
                  </tr>
                ) : (
                  filteredComplaints.map((complaint, index) => (
                    <tr
                      key={complaint.id}
                      className="hover:bg-surface transition-colors cursor-pointer"
                      style={{ animationDelay: `${index * 30}ms` }}
                      onClick={() => navigate(`/complaints/${complaint.id}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/complaints/${complaint.id}`); } }}
                    >
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-primary">{complaint.reference_number}</span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">{complaint.title}</p>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
                          <span>{getTypeIcon(complaint.complaint_type)}</span>
                          {complaint.complaint_type}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm text-foreground">{complaint.complainant_name}</p>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getPriorityVariant(complaint.priority) as any}>
                          {complaint.priority}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(complaint.status) as any}>
                          {complaint.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(complaint.received_date).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('complaints.dialog.title')}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label htmlFor="complaints-field-0" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.title')}</label>
              <Input id="complaints-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('complaints.form.title_placeholder')}
              />
            </div>

            <div>
              <label htmlFor="complaints-field-1" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.description')}</label>
              <Textarea id="complaints-field-1"
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('complaints.form.description_placeholder')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="complaints-field-2" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.type')}</label>
                <Select
                  value={formData.complaint_type}
                  onValueChange={(value) => setFormData({ ...formData, complaint_type: value })}
                >
                  <SelectTrigger id="complaints-field-2">
                    <SelectValue placeholder={t('complaints.form.select_type')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="product">{t('complaints.type.product')}</SelectItem>
                    <SelectItem value="service">{t('complaints.type.service')}</SelectItem>
                    <SelectItem value="delivery">{t('complaints.type.delivery')}</SelectItem>
                    <SelectItem value="communication">{t('complaints.type.communication')}</SelectItem>
                    <SelectItem value="billing">{t('complaints.type.billing')}</SelectItem>
                    <SelectItem value="staff">{t('complaints.type.staff')}</SelectItem>
                    <SelectItem value="environmental">{t('complaints.type.environmental')}</SelectItem>
                    <SelectItem value="safety">{t('complaints.type.safety')}</SelectItem>
                    <SelectItem value="other">{t('complaints.type.other')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="complaints-field-3" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.priority')}</label>
                <Select
                  value={formData.priority}
                  onValueChange={(value) => setFormData({ ...formData, priority: value })}
                >
                  <SelectTrigger id="complaints-field-3">
                    <SelectValue placeholder={t('complaints.form.select_priority')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">{t('priority.critical')}</SelectItem>
                    <SelectItem value="high">{t('priority.high')}</SelectItem>
                    <SelectItem value="medium">{t('priority.medium')}</SelectItem>
                    <SelectItem value="low">{t('priority.low')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <label htmlFor="complaints-field-4" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.complainant_name')}</label>
              <Input id="complaints-field-4"
                type="text"
                required
                value={formData.complainant_name}
                onChange={(e) => setFormData({ ...formData, complainant_name: e.target.value })}
                placeholder={t('complaints.form.name_placeholder')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="complaints-field-5" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.email')}</label>
                <Input id="complaints-field-5"
                  type="email"
                  value={formData.complainant_email || ''}
                  onChange={(e) => setFormData({ ...formData, complainant_email: e.target.value })}
                  placeholder={t('complaints.form.email_placeholder')}
                />
              </div>
              <div>
                <label htmlFor="complaints-field-6" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.phone')}</label>
                <Input id="complaints-field-6"
                  type="tel"
                  value={formData.complainant_phone || ''}
                  onChange={(e) => setFormData({ ...formData, complainant_phone: e.target.value })}
                  placeholder={t('complaints.form.phone_placeholder')}
                />
              </div>
            </div>

            <div>
              <label htmlFor="complaints-field-7" className="block text-sm font-medium text-foreground mb-2">{t('complaints.form.received_date')}</label>
              <Input id="complaints-field-7"
                type="datetime-local"
                required
                value={formData.received_date}
                onChange={(e) => setFormData({ ...formData, received_date: e.target.value })}
              />
            </div>

            <DialogFooter className="gap-3 pt-4">
              {formError && <p className="text-sm text-destructive">{formError}</p>}
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowModal(false)}
              >
                {t('cancel')}
              </Button>
              <Button
                type="submit"
                disabled={creating}
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('complaints.creating')}
                  </>
                ) : (
                  t('complaints.create')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
