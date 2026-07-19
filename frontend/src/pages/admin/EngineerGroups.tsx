import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { documentCampaignApi, type CampaignGroup } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/utils/apiError'

export default function EngineerGroups() {
  const [groups, setGroups] = useState<CampaignGroup[]>([])
  const [name, setName] = useState('')
  const [memberIds, setMemberIds] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await documentCampaignApi.listGroups()
      setGroups(Array.isArray(response.data) ? response.data : [])
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not load engineer groups'))
      setGroups([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const create = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('Enter a group name')
      return
    }
    const ids = memberIds
      .split(/[\s,]+/)
      .map((part) => Number(part.trim()))
      .filter((value) => Number.isFinite(value) && value > 0)
    setSaving(true)
    try {
      await documentCampaignApi.createGroup(trimmed, ids)
      toast.success(`Created group ${trimmed}`)
      setName('')
      setMemberIds('')
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not create group'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6" data-testid="engineer-groups-page">
      <div>
        <h1 className="text-2xl font-bold">Engineer groups</h1>
        <p className="text-muted-foreground mt-1">
          Manage audience groups used when launching document campaigns (HSEQ read / quiz / sign).
        </p>
      </div>

      <div className="rounded-lg border border-border p-4 space-y-3 max-w-xl">
        <p className="text-sm font-medium">Create group</p>
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Field engineers — North"
        />
        <Input
          value={memberIds}
          onChange={(event) => setMemberIds(event.target.value)}
          placeholder="Optional member user IDs (comma-separated)"
        />
        <Button type="button" onClick={() => void create()} disabled={saving}>
          {saving ? 'Creating…' : 'Create group'}
        </Button>
      </div>

      <div className="rounded-lg border border-border p-4 space-y-3">
        <p className="text-sm font-medium">Existing groups</p>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">No groups yet.</p>
        ) : (
          <ul className="space-y-2">
            {groups.map((group) => (
              <li key={group.id} className="rounded-md border border-border px-3 py-2 text-sm">
                <span className="font-medium">{group.name}</span>
                <span className="ml-2 text-muted-foreground">
                  {typeof group.member_count === 'number'
                    ? `${group.member_count} members`
                    : Array.isArray(group.member_user_ids)
                      ? `${group.member_user_ids.length} members`
                      : 'members unknown'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
