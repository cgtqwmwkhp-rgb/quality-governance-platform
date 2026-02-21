import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, MessageSquare, Search, Loader2 } from 'lucide-react'
import { complaintsApi, Complaint, ComplaintCreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
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
import { useToast, ToastContainer } from '../components/ui/Toast'

export default function Complaints() {
  const { toasts, show: showToast, dismiss: dismissToast } = useToast()
  const navigate = useNavigate()
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
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
      setComplaints(response.data.items)
    } catch (err) {
      console.error('Failed to load complaints:', err)
      showToast('Failed to load complaints. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
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
      showToast('Failed to create complaint. Please try again.', 'error')
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
          <h1 className="text-2xl font-bold text-foreground">Complaints</h1>
          <p className="text-muted-foreground mt-1">Manage customer complaints and feedback</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Complaint
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search complaints..."
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
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Reference</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Title</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Type</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Complainant</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Priority</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Received</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredComplaints.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                      <MessageSquare className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                      <p>No complaints found</p>
                      <p className="text-sm mt-1">Record a complaint to get started</p>
                    </td>
                  </tr>
                ) : (
                  filteredComplaints.map((complaint, index) => (
                    <tr
                      key={complaint.id}
                      className="hover:bg-surface transition-colors cursor-pointer"
                      style={{ animationDelay: `${index * 30}ms` }}
                      onClick={() => navigate(`/complaints/${complaint.id}`)}
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
                        <Badge variant={getPriorityVariant(complaint.priority) as BadgeVariant}>
                          {complaint.priority}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(complaint.status) as BadgeVariant}>
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
            <DialogTitle>New Complaint</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Title</label>
              <Input
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Brief summary of the complaint..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description</label>
              <Textarea
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Full details of the complaint..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Type</label>
                <Select
                  value={formData.complaint_type}
                  onValueChange={(value) => setFormData({ ...formData, complaint_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="product">Product</SelectItem>
                    <SelectItem value="service">Service</SelectItem>
                    <SelectItem value="delivery">Delivery</SelectItem>
                    <SelectItem value="communication">Communication</SelectItem>
                    <SelectItem value="billing">Billing</SelectItem>
                    <SelectItem value="staff">Staff</SelectItem>
                    <SelectItem value="environmental">Environmental</SelectItem>
                    <SelectItem value="safety">Safety</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Priority</label>
                <Select
                  value={formData.priority}
                  onValueChange={(value) => setFormData({ ...formData, priority: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">Critical</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Complainant Name</label>
              <Input
                type="text"
                required
                value={formData.complainant_name}
                onChange={(e) => setFormData({ ...formData, complainant_name: e.target.value })}
                placeholder="Name of the person making the complaint..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Email</label>
                <Input
                  type="email"
                  value={formData.complainant_email || ''}
                  onChange={(e) => setFormData({ ...formData, complainant_email: e.target.value })}
                  placeholder="email@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Phone</label>
                <Input
                  type="tel"
                  value={formData.complainant_phone || ''}
                  onChange={(e) => setFormData({ ...formData, complainant_phone: e.target.value })}
                  placeholder="+44 123 456 7890"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Received Date</label>
              <Input
                type="datetime-local"
                required
                value={formData.received_date}
                onChange={(e) => setFormData({ ...formData, received_date: e.target.value })}
              />
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={creating}
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Create Complaint'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
