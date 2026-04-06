import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink, Loader2, Save } from 'lucide-react'
import { actionsApi, Action as ApiAction, ActionUpdate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { Input } from '../components/ui/Input'

export default function ActionDetail() {
  const [searchParams] = useSearchParams()
  const key = searchParams.get('key') || ''
  const [action, setAction] = useState<ApiAction | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [statusDraft, setStatusDraft] = useState<string>('')

  const load = useCallback(async () => {
    if (!key.trim()) {
      setError('Missing key')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await actionsApi.getByKey(key.trim())
      setAction(res.data)
      setStatusDraft(res.data.display_status || res.data.status)
    } catch {
      setError('Could not load this action.')
      setAction(null)
    } finally {
      setLoading(false)
    }
  }, [key])

  useEffect(() => {
    load()
  }, [load])

  const saveStatus = async () => {
    if (!action) return
    setSaving(true)
    setError(null)
    try {
      const payload: ActionUpdate = { status: statusDraft }
      const res = await actionsApi.update(action.id, action.source_type, payload)
      setAction(res.data)
      setStatusDraft(res.data.display_status || res.data.status)
    } catch {
      setError('Update failed. Check permissions and status value.')
    } finally {
      setSaving(false)
    }
  }

  if (!key.trim()) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Open an action from the Actions list.</p>
        <Button variant="outline" className="mt-4" asChild>
          <Link to="/actions">Back to Actions</Link>
        </Button>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        Loading…
      </div>
    )
  }

  if (error || !action) {
    return (
      <div className="p-6 space-y-4">
        <p className="text-destructive">{error || 'Not found'}</p>
        <Button variant="outline" asChild>
          <Link to="/actions">Back to Actions</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-4 max-w-3xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/actions">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Actions
          </Link>
        </Button>
      </div>

      <div>
        <p className="text-sm font-mono text-primary">{action.action_key}</p>
        <h1 className="text-2xl font-bold text-foreground mt-1">{action.title}</h1>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="secondary">{action.source_type}</Badge>
          <Badge variant="outline">{action.display_status}</Badge>
          <Badge variant="outline">raw: {action.status}</Badge>
        </div>
      </div>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Description
            </p>
            <p className="text-foreground whitespace-pre-wrap mt-1">{action.description || '—'}</p>
          </div>

          {action.source_type === 'audit_finding' && action.audit_run_id ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link to={`/audits/${action.audit_run_id}/execute`}>
                  Open audit run
                  <ExternalLink className="w-3 h-3 ml-1" />
                </Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link to={`/audits/${action.audit_run_id}/import-review`}>Import review</Link>
              </Button>
            </div>
          ) : null}

          <div className="border-t border-border pt-4 space-y-3">
            <p className="text-sm font-medium text-foreground">Update status</p>
            <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
              <div className="flex-1">
                <Select value={statusDraft} onValueChange={setStatusDraft}>
                  <SelectTrigger>
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">open</SelectItem>
                    <SelectItem value="in_progress">in_progress</SelectItem>
                    <SelectItem value="pending_verification">pending_verification</SelectItem>
                    <SelectItem value="completed">completed</SelectItem>
                    <SelectItem value="cancelled">cancelled</SelectItem>
                    <SelectItem value="closed">closed (CAPA)</SelectItem>
                    <SelectItem value="verification">verification (CAPA)</SelectItem>
                    <SelectItem value="overdue">overdue (CAPA)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" onClick={saveStatus} disabled={saving}>
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-1" />
                )}
                Save
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Use values your source supports; CAPA rows accept closed / verification / overdue.
            </p>
          </div>

          <div className="border-t border-border pt-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Assignee email (optional)
            </p>
            <form
              className="flex flex-col sm:flex-row gap-2 mt-2"
              onSubmit={async (e) => {
                e.preventDefault()
                const fd = new FormData(e.currentTarget)
                const email = String(fd.get('email') || '').trim()
                if (!email || !action) return
                setSaving(true)
                try {
                  const res = await actionsApi.update(action.id, action.source_type, {
                    assigned_to_email: email,
                  })
                  setAction(res.data)
                } catch {
                  setError('Could not update assignee.')
                } finally {
                  setSaving(false)
                }
              }}
            >
              <Input name="email" type="email" placeholder="user@company.com" className="flex-1" />
              <Button type="submit" variant="secondary" disabled={saving}>
                Assign
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
