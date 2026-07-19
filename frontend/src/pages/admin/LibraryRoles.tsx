import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react'
import {
  getApiErrorMessage,
  usersApi,
  type RoleDetail,
} from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Input } from '../../components/ui/Input'

const FACET_OPTIONS: { id: string; label: string; permissions: string[] }[] = [
  {
    id: 'staff',
    label: 'Staff facet',
    permissions: ['document:read'],
  },
  {
    id: 'manager',
    label: 'Manager facet',
    permissions: ['document:read', 'document:create', 'document:update'],
  },
  {
    id: 'admin',
    label: 'Admin facet',
    permissions: [
      'document:read',
      'document:create',
      'document:update',
      'admin:manage',
      'document:restricted:oh',
      'document:restricted:driver',
      'document:restricted:breach',
    ],
  },
]

const RESTRICTED_OPTIONS = [
  { id: 'document:restricted:oh', label: 'Restricted — Occupational Health (02.08)' },
  { id: 'document:restricted:driver', label: 'Restricted — Driver Compliance (06.03)' },
  { id: 'document:restricted:breach', label: 'Restricted — Breach & Security (11.03)' },
]

function parsePermissions(raw: string | null | undefined): string[] {
  if (!raw) return []
  try {
    const decoded = JSON.parse(raw)
    if (Array.isArray(decoded)) {
      return decoded.map((item) => String(item).trim()).filter(Boolean)
    }
  } catch {
    // CSV fallback
  }
  return raw
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}

export default function LibraryRoles() {
  const [roles, setRoles] = useState<RoleDetail[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [draftPerms, setDraftPerms] = useState<string[]>([])
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const selected = useMemo(
    () => roles.find((role) => role.id === selectedId) ?? null,
    [roles, selectedId],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await usersApi.listRoles({ suppressErrorToast: true })
      const next = Array.isArray(response.data) ? response.data : []
      setRoles(next)
      if (next.length && selectedId == null) {
        setSelectedId(next[0].id)
        setDraftPerms(parsePermissions(next[0].permissions))
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not load roles'))
      setRoles([])
    } finally {
      setLoading(false)
    }
  }, [selectedId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!selected) return
    setDraftPerms(parsePermissions(selected.permissions))
  }, [selected])

  const togglePerm = (permission: string, enabled: boolean) => {
    setDraftPerms((prev) => {
      const set = new Set(prev)
      if (enabled) set.add(permission)
      else set.delete(permission)
      return Array.from(set).sort()
    })
  }

  const applyFacet = (permissions: string[]) => {
    setDraftPerms((prev) => Array.from(new Set([...prev, ...permissions])).sort())
  }

  const save = async () => {
    if (!selected || selected.is_system_role) return
    setSaving(true)
    try {
      await usersApi.updateRole(selected.id, { permissions: draftPerms })
      toast.success(`Updated permissions for ${selected.name}`)
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not update role'))
    } finally {
      setSaving(false)
    }
  }

  const createRole = async () => {
    const name = newName.trim()
    if (!name) {
      toast.error('Enter a role name')
      return
    }
    setSaving(true)
    try {
      const response = await usersApi.createRole({
        name,
        description: 'Governance Library role',
        permissions: ['document:read'],
      })
      toast.success(`Created role ${name}`)
      setNewName('')
      setSelectedId(response.data.id)
      await load()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not create role'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6" data-testid="library-roles-page">
      <div>
        <h1 className="text-2xl font-bold">Library roles & permissions</h1>
        <p className="text-muted-foreground mt-1">
          Map staff / manager / admin facets onto Role.permissions. Restricted categories use
          document:restricted:oh|driver|breach — not named user lists.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading roles…</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <div className="space-y-3">
            <div className="rounded-lg border border-border p-3 space-y-2">
              <p className="text-sm font-medium">Roles</p>
              {roles.map((role) => (
                <button
                  key={role.id}
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    role.id === selectedId ? 'border-primary bg-muted' : 'border-border'
                  }`}
                  onClick={() => setSelectedId(role.id)}
                >
                  <span className="font-medium">{role.name}</span>
                  {role.is_system_role ? (
                    <span className="ml-2 text-xs text-muted-foreground">system</span>
                  ) : null}
                </button>
              ))}
            </div>
            <div className="rounded-lg border border-border p-3 space-y-2">
              <p className="text-sm font-medium">Create role</p>
              <Input
                value={newName}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setNewName(event.target.value)}
                placeholder="e.g. library_manager"
              />
              <Button type="button" onClick={() => void createRole()} disabled={saving}>
                Create
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-border p-4 space-y-4">
            {!selected ? (
              <p className="text-sm text-muted-foreground">Select a role to edit permissions.</p>
            ) : (
              <>
                <div>
                  <h2 className="text-lg font-semibold">{selected.name}</h2>
                  <p className="text-sm text-muted-foreground">
                    {selected.description || 'No description'}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {FACET_OPTIONS.map((facet) => (
                    <Button
                      key={facet.id}
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={selected.is_system_role}
                      onClick={() => applyFacet(facet.permissions)}
                    >
                      Apply {facet.label}
                    </Button>
                  ))}
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Restricted category gates</p>
                  {RESTRICTED_OPTIONS.map((option) => (
                    <label key={option.id} className="flex items-start gap-3 text-sm">
                      <Checkbox
                        checked={draftPerms.includes(option.id)}
                        disabled={selected.is_system_role}
                        onCheckedChange={(value: boolean | 'indeterminate') =>
                          togglePerm(option.id, value === true)
                        }
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">All permissions on role</p>
                  <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">
                    {JSON.stringify(draftPerms, null, 2)}
                  </pre>
                </div>

                <Button
                  type="button"
                  onClick={() => void save()}
                  disabled={saving || selected.is_system_role}
                >
                  {saving ? 'Saving…' : 'Save permissions'}
                </Button>
                {selected.is_system_role ? (
                  <p className="text-xs text-muted-foreground">
                    System roles cannot be modified — create an overlay role instead.
                  </p>
                ) : null}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
