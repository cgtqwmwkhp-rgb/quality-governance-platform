import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Car,
  MapPin,
  Calendar,
  FileText,
  Loader2,
  History,
  Shield,
} from 'lucide-react'
import { rtasApi, RTA } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

export default function RTADetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [rta, setRta] = useState<RTA | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (id) {
      loadRTA(parseInt(id))
    }
  }, [id])

  const loadRTA = async (rtaId: number) => {
    try {
      const response = await rtasApi.get(rtaId)
      setRta(response.data)
    } catch (err) {
      console.error('Failed to load RTA:', err)
    } finally {
      setLoading(false)
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  if (!rta) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Car className="w-12 h-12 text-muted-foreground" />
        <p className="text-muted-foreground">RTA not found</p>
        <Button variant="outline" onClick={() => navigate('/rtas')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to RTAs
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button 
            variant="outline" 
            size="icon"
            onClick={() => navigate('/rtas')}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-primary">{rta.reference_number}</span>
              <Badge variant={getSeverityVariant(rta.severity) as any}>
                {rta.severity.replace('_', ' ')}
              </Badge>
              <Badge variant={getStatusVariant(rta.status) as any}>
                {rta.status.replace('_', ' ')}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">{rta.title}</h1>
            <p className="text-muted-foreground mt-1">
              Reported on {new Date(rta.reported_date).toLocaleDateString()}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                Collision Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground">Description</label>
                <p className="mt-1 text-foreground whitespace-pre-wrap">
                  {rta.description || 'No description provided'}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Severity</label>
                  <p className="mt-1 text-foreground capitalize">{rta.severity.replace('_', ' ')}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Status</label>
                  <p className="mt-1 text-foreground capitalize">{rta.status.replace('_', ' ')}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Collision Date</label>
                  <p className="mt-1 text-foreground">
                    {new Date(rta.collision_date).toLocaleString()}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Location</label>
                  <p className="mt-1 text-foreground">{rta.location || 'Not specified'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Vehicle & Driver Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Car className="w-5 h-5 text-primary" />
                Vehicle & Driver Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Vehicle Registration</label>
                  <p className="mt-1 text-foreground">{rta.company_vehicle_registration || 'Not specified'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Driver Name</label>
                  <p className="mt-1 text-foreground">{rta.driver_name || 'Not specified'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Driver Injured</label>
                  <p className="mt-1 text-foreground">{rta.driver_injured ? 'Yes' : 'No'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Police Attended</label>
                  <p className="mt-1 text-foreground">{rta.police_attended ? 'Yes' : 'No'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Quick Info */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Calendar className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Created</p>
                  <p className="font-medium text-foreground">
                    {new Date(rta.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center">
                  <MapPin className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Location</p>
                  <p className="font-medium text-foreground">{rta.location || 'Not specified'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Insurance Notified</p>
                  <p className="font-medium text-foreground">{rta.insurance_notified ? 'Yes' : 'No'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Timeline Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="w-4 h-4" />
                Activity Timeline
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">RTA Reported</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(rta.reported_date).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-muted mt-2" />
                  <div>
                    <p className="text-sm font-medium text-foreground">Record Created</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(rta.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
