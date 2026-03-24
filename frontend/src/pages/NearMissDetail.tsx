import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, ArrowLeft, Calendar, FileText, FlaskConical, Pencil, Save, X } from 'lucide-react'
import { toast } from '../contexts/ToastContext'
import { Breadcrumbs } from '../components/ui/Breadcrumbs'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { trackError } from '../utils/errorTracker'
import {
  CreateFromRecordError,
  getApiErrorMessage,
  Investigation,
  investigationsApi,
  NearMiss,
  nearMissesApi,
  NearMissUpdate,
  RunningSheetEntry,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/Dialog'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { CaseSummaryRail } from '../components/case/CaseSummaryRail'
import { RunningSheetPanel } from '../components/case/RunningSheetPanel'

export default function NearMissDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [nearMiss, setNearMiss] = useState<NearMiss | null>(null)
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [runningSheet, setRunningSheet] = useState<RunningSheetEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showInvestigationModal, setShowInvestigationModal] = useState(false)
  const [creatingInvestigation, setCreatingInvestigation] = useState(false)
  const [newEntry, setNewEntry] = useState('')
  const [addingEntry, setAddingEntry] = useState(false)
  const [editForm, setEditForm] = useState<NearMissUpdate>({})
  const [investigationTitle, setInvestigationTitle] = useState('')
  const [investigationError, setInvestigationError] = useState('')

  useEffect(() => {
    if (id) {
      loadNearMiss(parseInt(id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const loadNearMiss = async (nearMissId: number) => {
    setError(null)
    try {
      const response = await nearMissesApi.get(nearMissId)
      setNearMiss(response.data)
      setEditForm({
        description: response.data.description,
        potential_consequences: response.data.potential_consequences,
        preventive_action_suggested: response.data.preventive_action_suggested,
        status: response.data.status,
        priority: response.data.priority,
        resolution_notes: response.data.resolution_notes,
        corrective_actions_taken: response.data.corrective_actions_taken,
        risk_category: response.data.risk_category,
        potential_severity: response.data.potential_severity,
      })
      loadInvestigations(nearMissId)
      loadRunningSheet(nearMissId)
    } catch (err) {
      trackError(err, { component: 'NearMissDetail', action: 'loadNearMiss' })
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const loadInvestigations = async (nearMissId: number) => {
    try {
      const response = await nearMissesApi.listInvestigations(nearMissId, 1, 10)
      setInvestigations(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'NearMissDetail', action: 'loadInvestigations' })
    }
  }

  const loadRunningSheet = async (nearMissId: number) => {
    try {
      const response = await nearMissesApi.listRunningSheet(nearMissId)
      setRunningSheet(response.data)
    } catch (err) {
      trackError(err, { component: 'NearMissDetail', action: 'loadRunningSheet' })
    }
  }

  const handleSaveEdit = async () => {
    if (!nearMiss) return
    setSaving(true)
    try {
      const response = await nearMissesApi.update(nearMiss.id, editForm)
      setNearMiss(response.data)
      setIsEditing(false)
      toast.success('Changes saved')
    } catch (err) {
      trackError(err, { component: 'NearMissDetail', action: 'saveEdit' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    if (!nearMiss) return
    setEditForm({
      description: nearMiss.description,
      potential_consequences: nearMiss.potential_consequences,
      preventive_action_suggested: nearMiss.preventive_action_suggested,
      status: nearMiss.status,
      priority: nearMiss.priority,
      resolution_notes: nearMiss.resolution_notes,
      corrective_actions_taken: nearMiss.corrective_actions_taken,
      risk_category: nearMiss.risk_category,
      potential_severity: nearMiss.potential_severity,
    })
    setIsEditing(false)
  }

  const handleAddEntry = async () => {
    if (!nearMiss || !newEntry.trim()) return
    setAddingEntry(true)
    try {
      await nearMissesApi.addRunningSheetEntry(nearMiss.id, { content: newEntry.trim() })
      setNewEntry('')
      loadRunningSheet(nearMiss.id)
    } catch (err) {
      trackError(err, { component: 'NearMissDetail', action: 'addRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setAddingEntry(false)
    }
  }

  const handleDeleteEntry = async (entryId: number) => {
    if (!nearMiss) return
    try {
      await nearMissesApi.deleteRunningSheetEntry(nearMiss.id, entryId)
      loadRunningSheet(nearMiss.id)
    } catch (err) {
      trackError(err, { component: 'NearMissDetail', action: 'deleteRunningSheetEntry' })
      toast.error(getApiErrorMessage(err))
    }
  }

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nearMiss) return
    setCreatingInvestigation(true)
    setInvestigationError('')
    try {
      await investigationsApi.createFromRecord({
        source_type: 'near_miss',
        source_id: nearMiss.id,
        title: investigationTitle || `Investigation - ${nearMiss.reference_number}`,
      })
      setShowInvestigationModal(false)
      setInvestigationTitle('')
      loadInvestigations(nearMiss.id)
      toast.success('Investigation created')
    } catch (err) {
      const apiErr = err as { response?: { data?: CreateFromRecordError } }
      setInvestigationError(apiErr.response?.data?.message || getApiErrorMessage(err))
    } finally {
      setCreatingInvestigation(false)
    }
  }

  if (loading) {
    return <CardSkeleton />
  }

  if (error || !nearMiss) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/near-misses')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Near Misses
        </Button>
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          {error || 'Near miss not found'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <Breadcrumbs
        items={[
          { label: t('near_misses.title', 'Near Misses'), href: '/near-misses' },
          { label: nearMiss.reference_number || `#${id}` },
        ]}
      />

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/near-misses')} className="mb-3">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Near Misses
          </Button>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-warning/10 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-warning" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">{nearMiss.reference_number}</h1>
              <p className="text-muted-foreground mt-1">{nearMiss.contract} near miss</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={handleCancelEdit}>
                <X className="w-4 h-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={handleSaveEdit} disabled={saving}>
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Saving...' : 'Save'}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setShowInvestigationModal(true)}>
                <FlaskConical className="w-4 h-4 mr-2" />
                Create Investigation
              </Button>
              <Button onClick={() => setIsEditing(true)}>
                <Pencil className="w-4 h-4 mr-2" />
                Edit
              </Button>
            </>
          )}
        </div>
      </div>

      <CaseSummaryRail
        items={[
          { label: 'Reporter', value: nearMiss.reporter_name, icon: <AlertTriangle className="w-4 h-4" /> },
          { label: 'Contract', value: nearMiss.contract, icon: <FileText className="w-4 h-4" /> },
          { label: 'Location', value: nearMiss.location, icon: <FileText className="w-4 h-4" /> },
          {
            label: 'Event date',
            value: new Date(nearMiss.event_date).toLocaleString(),
            icon: <Calendar className="w-4 h-4" />,
          },
          { label: 'Status', value: nearMiss.status, icon: <AlertTriangle className="w-4 h-4" /> },
          { label: 'Priority', value: nearMiss.priority, icon: <AlertTriangle className="w-4 h-4" /> },
          { label: 'Investigations', value: `${investigations.length}`, icon: <FlaskConical className="w-4 h-4" /> },
        ]}
      />

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="w-full justify-start flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="running-sheet">Running Sheet</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-primary" />
                    Near miss details
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {isEditing ? (
                    <>
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Description</label>
                        <Textarea
                          value={editForm.description || ''}
                          onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                          rows={4}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">
                          Potential consequences
                        </label>
                        <Textarea
                          value={editForm.potential_consequences || ''}
                          onChange={(e) =>
                            setEditForm({ ...editForm, potential_consequences: e.target.value })
                          }
                          rows={3}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">
                          Preventive action suggested
                        </label>
                        <Textarea
                          value={editForm.preventive_action_suggested || ''}
                          onChange={(e) =>
                            setEditForm({ ...editForm, preventive_action_suggested: e.target.value })
                          }
                          rows={3}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Status</label>
                        <Input
                          value={editForm.status || ''}
                          onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Priority</label>
                        <Input
                          value={editForm.priority || ''}
                          onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                          className="mt-1"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">Description</h3>
                        <p className="text-foreground whitespace-pre-wrap">{nearMiss.description}</p>
                      </div>
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">Potential consequences</h3>
                        <p className="text-foreground whitespace-pre-wrap">
                          {nearMiss.potential_consequences || 'Not recorded'}
                        </p>
                      </div>
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">
                          Preventive action suggested
                        </h3>
                        <p className="text-foreground whitespace-pre-wrap">
                          {nearMiss.preventive_action_suggested || 'Not recorded'}
                        </p>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FlaskConical className="w-5 h-5 text-primary" />
                    Investigations
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {investigations.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No investigations linked yet.</p>
                  ) : (
                    <div className="space-y-3">
                      {investigations.map((investigation) => (
                        <div key={investigation.id} className="rounded-lg border border-border p-3">
                          <div className="font-medium text-foreground">{investigation.reference_number}</div>
                          <div className="text-sm text-muted-foreground">{investigation.title}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Status summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Status</span>
                    <Badge variant="outline">{nearMiss.status}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Priority</span>
                    <Badge variant="secondary">{nearMiss.priority}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Potential severity</span>
                    <span className="text-sm text-foreground">{nearMiss.potential_severity || 'Not set'}</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="running-sheet" className="mt-6">
          <RunningSheetPanel
            entries={runningSheet}
            newEntry={newEntry}
            addingEntry={addingEntry}
            title={t('common.running_sheet', 'Running Sheet')}
            placeholder={t('common.running_sheet_placeholder', 'Add to the story... (auto-timestamped)')}
            emptyTitle={t('common.running_sheet_empty_title', 'No entries yet')}
            emptyDescription="Add notes to build the near-miss narrative over time"
            onNewEntryChange={setNewEntry}
            onAddEntry={handleAddEntry}
            onDeleteEntry={handleDeleteEntry}
          />
        </TabsContent>
      </Tabs>

      <Dialog open={showInvestigationModal} onOpenChange={setShowInvestigationModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create investigation</DialogTitle>
            <DialogDescription>
              Start a formal investigation for this near miss.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateInvestigation} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Investigation title</label>
              <Input
                value={investigationTitle}
                onChange={(e) => setInvestigationTitle(e.target.value)}
                className="mt-1"
                placeholder={`Investigation - ${nearMiss.reference_number}`}
              />
            </div>
            {investigationError && <div className="text-sm text-destructive">{investigationError}</div>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowInvestigationModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={creatingInvestigation}>
                {creatingInvestigation ? 'Creating…' : 'Create Investigation'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
