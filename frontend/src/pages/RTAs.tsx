import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Car, Search, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { rtasApi, RTA, RTACreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Switch } from '../components/ui/Switch'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { useToast, ToastContainer } from '../components/ui/Toast'

export default function RTAs() {
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();
  const navigate = useNavigate()
  const [rtas, setRtas] = useState<RTA[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; code?: string; requestId?: string } | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<RTACreate>({
    title: '',
    description: '',
    severity: 'damage_only',
    collision_date: new Date().toISOString().slice(0, 16),
    reported_date: new Date().toISOString().slice(0, 16),
    location: '',
    driver_name: '',
    company_vehicle_registration: '',
    police_attended: false,
    driver_injured: false,
  })

  useEffect(() => {
    loadRtas()
  }, [])

  const loadRtas = async () => {
    setLoading(true)
    setError(null)

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => {
      controller.abort()
    }, 15000) // 15 second timeout

    try {
      const response = await rtasApi.list(1, 50)
      setRtas(response.data.items)
      setError(null)
    } catch (err: unknown) {
      console.error('Failed to load RTAs:', err)
      showToast('Failed to load RTAs. Please try again.', 'error')
      
      // Extract error details for display
      const axiosErr = err as { code?: string; message?: string; name?: string; response?: { status?: number; data?: { request_id?: string; message?: string; detail?: { message?: string } }; headers?: Record<string, string> } };
      const isTimeout = axiosErr.code === 'ECONNABORTED' || axiosErr.message?.includes('timeout') || axiosErr.name === 'AbortError'
      const status = axiosErr.response?.status
      const requestId = axiosErr.response?.data?.request_id || axiosErr.response?.headers?.['x-request-id']
      
      if (isTimeout) {
        setError({
          message: 'Request timed out. The server took too long to respond.',
          code: 'TIMEOUT',
          requestId,
        })
      } else if (!axiosErr.response) {
        setError({
          message: 'Network error. Please check your connection.',
          code: 'NETWORK_ERROR',
          requestId,
        })
      } else {
        setError({
          message: axiosErr.response?.data?.message || axiosErr.response?.data?.detail?.message || 'Failed to load RTAs. Please try again.',
          code: status ? `HTTP_${status}` : 'UNKNOWN',
          requestId,
        })
      }
      setRtas([])
    } finally {
      clearTimeout(timeoutId)
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await rtasApi.create({
        ...formData,
        collision_date: new Date(formData.collision_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        severity: 'damage_only',
        collision_date: new Date().toISOString().slice(0, 16),
        reported_date: new Date().toISOString().slice(0, 16),
        location: '',
        driver_name: '',
        company_vehicle_registration: '',
        police_attended: false,
        driver_injured: false,
      })
      loadRtas()
    } catch (err) {
      console.error('Failed to create RTA:', err)
      showToast('Failed to report RTA. Please try again.', 'error')
    } finally {
      setCreating(false)
    }
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'fatal': return 'critical'
      case 'serious_injury': return 'critical'
      case 'minor_injury': return 'high'
      case 'damage_only': return 'medium'
      case 'near_miss': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': return 'resolved'
      case 'reported': return 'submitted'
      case 'under_investigation': return 'in-progress'
      case 'pending_insurance': return 'acknowledged'
      case 'pending_actions': return 'awaiting-user'
      default: return 'secondary'
    }
  }

  const filteredRtas = rtas.filter(
    r => r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.location.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-destructive" />
        </div>
        <div className="text-center">
          <h2 className="text-lg font-semibold text-foreground mb-1">Failed to Load RTAs</h2>
          <p className="text-muted-foreground max-w-md">{error.message}</p>
          {error.code && (
            <p className="text-xs text-muted-foreground mt-1">
              Error code: {error.code}
              {error.requestId && ` | Request ID: ${error.requestId}`}
            </p>
          )}
        </div>
        <Button onClick={loadRtas} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Road Traffic Collisions</h1>
          <p className="text-muted-foreground mt-1">Manage vehicle accidents and incidents</p>
        </div>
        <Button onClick={() => setShowModal(true)} data-testid="create-rta-btn">
          <Plus size={20} />
          Report RTA
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search RTAs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* RTAs Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Reference</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Title</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Location</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Severity</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredRtas.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                      <Car className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                      <p>No RTAs found</p>
                      <p className="text-sm mt-1">Report a road traffic collision to get started</p>
                    </td>
                  </tr>
                ) : (
                  filteredRtas.map((rta, index) => (
                    <tr
                      key={rta.id}
                      className="hover:bg-surface transition-colors cursor-pointer"
                      style={{ animationDelay: `${index * 30}ms` }}
                      onClick={() => navigate(`/rtas/${rta.id}`)}
                    >
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-primary">{rta.reference_number}</span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">{rta.title}</p>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm text-foreground truncate max-w-xs">{rta.location}</p>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getSeverityVariant(rta.severity) as BadgeVariant}>
                          {rta.severity.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(rta.status) as BadgeVariant}>
                          {rta.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(rta.collision_date).toLocaleDateString()}
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
            <DialogTitle>Report Road Traffic Collision</DialogTitle>
            <DialogDescription>
              Record details of a road traffic collision or near miss incident for investigation and follow-up.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Title</label>
              <Input
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Brief description of the collision..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description</label>
              <Textarea
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Full details of what happened..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Location</label>
              <Input
                type="text"
                required
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="Where did the collision occur..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Severity</label>
                <Select
                  value={formData.severity}
                  onValueChange={(value) => setFormData({ ...formData, severity: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select severity" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="near_miss">Near Miss</SelectItem>
                    <SelectItem value="damage_only">Damage Only</SelectItem>
                    <SelectItem value="minor_injury">Minor Injury</SelectItem>
                    <SelectItem value="serious_injury">Serious Injury</SelectItem>
                    <SelectItem value="fatal">Fatal</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Vehicle Reg</label>
                <Input
                  type="text"
                  value={formData.company_vehicle_registration || ''}
                  onChange={(e) => setFormData({ ...formData, company_vehicle_registration: e.target.value })}
                  placeholder="AB12 CDE"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Driver Name</label>
              <Input
                type="text"
                value={formData.driver_name || ''}
                onChange={(e) => setFormData({ ...formData, driver_name: e.target.value })}
                placeholder="Name of the driver..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Collision Date</label>
              <Input
                type="datetime-local"
                required
                value={formData.collision_date}
                onChange={(e) => setFormData({ ...formData, collision_date: e.target.value })}
              />
            </div>

            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.police_attended || false}
                  onCheckedChange={(checked) => setFormData({ ...formData, police_attended: checked })}
                />
                <label className="text-sm text-foreground">Police Attended</label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.driver_injured || false}
                  onCheckedChange={(checked) => setFormData({ ...formData, driver_injured: checked })}
                />
                <label className="text-sm text-foreground">Driver Injured</label>
              </div>
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
                    Reporting...
                  </>
                ) : (
                  'Report RTA'
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
