import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { workforceApi, auditsApi, getApiErrorMessage, type AuditTemplate, type EngineerProfile, type AssetType } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'

export default function InductionCreate() {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<AuditTemplate[]>([])
  const [engineers, setEngineers] = useState<EngineerProfile[]>([])
  const [assetTypes, setAssetTypes] = useState<AssetType[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [templateId, setTemplateId] = useState<string>('')
  const [engineerId, setEngineerId] = useState<string>('')
  const [assetTypeId, setAssetTypeId] = useState<string>('')
  const [title, setTitle] = useState('')
  const [location, setLocation] = useState('')
  const [scheduledDate, setScheduledDate] = useState('')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const [tRes, eRes, aRes] = await Promise.all([
          auditsApi.listTemplates(1, 100, { is_published: true }),
          workforceApi.listEngineers({ page_size: 200 }),
          workforceApi.listAssetTypes(),
        ])
        setTemplates(tRes.data.items || [])
        setEngineers(eRes.data.items || [])
        setAssetTypes(aRes.data.items || [])
      } catch {
        setError('Failed to load form data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!templateId || !engineerId) {
      setError('Template and engineer are required')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const res = await workforceApi.createInduction({
        template_id: Number(templateId),
        engineer_id: Number(engineerId),
        asset_type_id: assetTypeId ? Number(assetTypeId) : undefined,
        title: title || undefined,
        location: location || undefined,
        scheduled_date: scheduledDate || undefined,
        notes: notes || undefined,
      })
      navigate(`/workforce/training/${res.data.id}/execute`)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary/20 border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/training')} aria-label="Back">
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-foreground">New Induction</h1>
          <p className="text-muted-foreground text-sm">Create a training induction for an engineer</p>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <h2 className="text-lg font-semibold text-foreground">Induction Details</h2>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="inductioncreate-field-0" className="block text-sm font-medium text-foreground mb-1">
                Template <span className="text-destructive">*</span>
              </label>
              <select id="inductioncreate-field-0"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                required
                className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Select a template...</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.audit_type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="inductioncreate-field-1" className="block text-sm font-medium text-foreground mb-1">
                Engineer <span className="text-destructive">*</span>
              </label>
              <select id="inductioncreate-field-1"
                value={engineerId}
                onChange={(e) => setEngineerId(e.target.value)}
                required
                className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Select an engineer...</option>
                {engineers.map((eng) => (
                  <option key={eng.id} value={eng.id}>
                    {eng.employee_number || `#${eng.id}`} — {eng.job_title || 'Engineer'} ({eng.department || 'N/A'})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="inductioncreate-field-2" className="block text-sm font-medium text-foreground mb-1">Asset Type</label>
              <select id="inductioncreate-field-2"
                value={assetTypeId}
                onChange={(e) => setAssetTypeId(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">None (optional)</option>
                {assetTypes.map((at) => (
                  <option key={at.id} value={at.id}>
                    {at.name} ({at.category})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="inductioncreate-field-3" className="block text-sm font-medium text-foreground mb-1">Title</label>
              <input id="inductioncreate-field-3"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Site induction for new starter"
                className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label htmlFor="inductioncreate-field-4" className="block text-sm font-medium text-foreground mb-1">Location</label>
              <input id="inductioncreate-field-4"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Depot B"
                className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label htmlFor="inductioncreate-field-5" className="block text-sm font-medium text-foreground mb-1">Scheduled Date</label>
              <input id="inductioncreate-field-5"
                type="date"
                value={scheduledDate}
                onChange={(e) => setScheduledDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label htmlFor="inductioncreate-field-6" className="block text-sm font-medium text-foreground mb-1">Notes</label>
              <textarea id="inductioncreate-field-6"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional context or instructions..."
                className="w-full min-h-[80px] rounded-lg border border-border bg-card px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-destructive p-3">
                <p className="text-destructive text-sm">{error}</p>
              </div>
            )}

            <Button type="submit" disabled={submitting} className="w-full min-h-[48px] text-base">
              {submitting ? 'Creating...' : 'Create & Start Induction'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
