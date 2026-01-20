import { useEffect, useState } from 'react'
import { Plus, Search, FlaskConical, ArrowRight, FileQuestion, GitBranch, CheckCircle, Clock, AlertTriangle, Car, MessageSquare, Loader2 } from 'lucide-react'
import { investigationsApi, Investigation } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog'
import { cn } from '../lib/utils'

const STATUS_STEPS = [
  { id: 'draft', label: 'Draft', icon: FileQuestion },
  { id: 'in_progress', label: 'In Progress', icon: Clock },
  { id: 'under_review', label: 'Under Review', icon: GitBranch },
  { id: 'completed', label: 'Completed', icon: CheckCircle },
]

const ENTITY_ICONS: Record<string, typeof AlertTriangle> = {
  road_traffic_collision: Car,
  reporting_incident: AlertTriangle,
  complaint: MessageSquare,
}

export default function Investigations() {
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedInvestigation, setSelectedInvestigation] = useState<Investigation | null>(null)

  useEffect(() => {
    loadInvestigations()
  }, [])

  const loadInvestigations = async () => {
    try {
      const response = await investigationsApi.list(1, 100)
      setInvestigations(response.data.items || [])
    } catch (err) {
      console.error('Failed to load investigations:', err)
      setInvestigations([])
    } finally {
      setLoading(false)
    }
  }

  const getStatusIndex = (status: string) => {
    return STATUS_STEPS.findIndex(s => s.id === status)
  }

  const getEntityIcon = (type: string) => {
    return ENTITY_ICONS[type] || AlertTriangle
  }

  const filteredInvestigations = investigations.filter(
    i => i.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         i.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const stats = {
    total: investigations.length,
    inProgress: investigations.filter(i => i.status === 'in_progress').length,
    underReview: investigations.filter(i => i.status === 'under_review').length,
    completed: investigations.filter(i => i.status === 'completed').length,
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
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Root Cause Investigations</h1>
          <p className="text-muted-foreground mt-1">5-Whys analysis, RCA workflows & corrective actions</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Investigation
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total', value: stats.total, variant: 'primary' as const },
          { label: 'In Progress', value: stats.inProgress, variant: 'warning' as const },
          { label: 'Under Review', value: stats.underReview, variant: 'info' as const },
          { label: 'Completed', value: stats.completed, variant: 'success' as const },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center mb-3",
              stat.variant === 'primary' && "bg-primary/10",
              stat.variant === 'warning' && "bg-warning/10",
              stat.variant === 'info' && "bg-info/10",
              stat.variant === 'success' && "bg-success/10",
            )}>
              <span className={cn(
                "text-xl font-bold",
                stat.variant === 'primary' && "text-primary",
                stat.variant === 'warning' && "text-warning",
                stat.variant === 'info' && "text-info",
                stat.variant === 'success' && "text-success",
              )}>
                {stat.value}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
          </Card>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search investigations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Investigation Cards */}
      <div className="space-y-4">
        {filteredInvestigations.length === 0 ? (
          <Card className="p-12 text-center">
            <FlaskConical className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">No Investigations Found</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Start a root cause investigation to analyze incidents, RTAs, or complaints.
            </p>
          </Card>
        ) : (
          filteredInvestigations.map((investigation) => {
            const EntityIcon = getEntityIcon(investigation.assigned_entity_type)
            const statusIndex = getStatusIndex(investigation.status)
            
            return (
              <Card
                key={investigation.id}
                hoverable
                onClick={() => setSelectedInvestigation(investigation)}
                className="p-6 cursor-pointer"
              >
                <div className="flex flex-col lg:flex-row lg:items-center gap-6">
                  {/* Entity Icon */}
                  <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <EntityIcon className="w-8 h-8 text-primary" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-sm text-primary">{investigation.reference_number}</span>
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-surface text-muted-foreground capitalize">
                        {investigation.assigned_entity_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-1">
                      {investigation.title}
                    </h3>
                    {investigation.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2">{investigation.description}</p>
                    )}
                  </div>

                  {/* Status Timeline */}
                  <div className="flex items-center gap-2 lg:w-80">
                    {STATUS_STEPS.map((step, stepIndex) => {
                      const isActive = stepIndex <= statusIndex
                      const isCurrent = stepIndex === statusIndex
                      return (
                        <div key={step.id} className="flex items-center">
                          <div className={cn(
                            "relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-300",
                            isCurrent 
                              ? 'bg-primary shadow-lg' 
                              : isActive 
                                ? 'bg-primary/20' 
                                : 'bg-surface'
                          )}>
                            <step.icon className={cn(
                              "w-5 h-5",
                              isActive ? 'text-primary-foreground' : 'text-muted-foreground'
                            )} />
                            {isCurrent && (
                              <div className="absolute inset-0 rounded-xl animate-pulse bg-primary/30" />
                            )}
                          </div>
                          {stepIndex < STATUS_STEPS.length - 1 && (
                            <ArrowRight className={cn(
                              "w-4 h-4 mx-1",
                              isActive ? 'text-primary' : 'text-muted-foreground/30'
                            )} />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* RCA Preview */}
                {investigation.data && Object.keys(investigation.data).length > 0 && (
                  <div className="mt-6 pt-6 border-t border-border">
                    <div className="flex items-center gap-2 mb-3">
                      <GitBranch className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium text-primary">Root Cause Analysis</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {['Why 1', 'Why 2', 'Why 3'].map((why, i) => (
                        <Card key={i} className="p-3">
                          <span className="text-xs text-muted-foreground">{why}</span>
                          <p className="text-sm text-foreground mt-1">
                            {typeof investigation.data === 'object' && 
                              (investigation.data as Record<string, unknown>)[`why_${i + 1}`] as string || 
                              'Not documented'}
                          </p>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            )
          })
        )}
      </div>

      {/* Detail Modal */}
      <Dialog open={!!selectedInvestigation} onOpenChange={() => setSelectedInvestigation(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
          {selectedInvestigation && (
            <>
              <DialogHeader>
                <span className="font-mono text-sm text-primary">{selectedInvestigation.reference_number}</span>
                <DialogTitle>{selectedInvestigation.title}</DialogTitle>
              </DialogHeader>
              <div className="overflow-y-auto max-h-[calc(90vh-120px)] space-y-6 py-4">
                {/* 5 Whys Analysis */}
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <GitBranch className="w-5 h-5 text-primary" />
                    5 Whys Analysis
                  </h3>
                  <div className="space-y-4">
                    {[1, 2, 3, 4, 5].map((num) => (
                      <div key={num} className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0 font-bold text-primary-foreground">
                          {num}
                        </div>
                        <div className="flex-1">
                          <label className="block text-sm font-medium text-foreground mb-2">
                            Why {num}?
                          </label>
                          <Textarea
                            rows={2}
                            placeholder={`Enter the ${num === 1 ? 'initial' : 'deeper'} cause...`}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Root Cause */}
                <Card className="p-6 border-primary/20 bg-primary/5">
                  <h3 className="text-lg font-semibold text-foreground mb-4">Root Cause Identified</h3>
                  <Textarea
                    rows={3}
                    placeholder="Document the root cause based on your 5 Whys analysis..."
                  />
                </Card>

                {/* Corrective Actions */}
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-4">Corrective Actions</h3>
                  <Button variant="outline" className="w-full">
                    <Plus className="w-5 h-5" />
                    Add Corrective Action
                  </Button>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Start New Investigation</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="text-muted-foreground text-center py-8">
              Investigation creation coming soon. Use the API to create investigations.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
