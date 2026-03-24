import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Mail, Plus, RefreshCw, Search, Shield, UserCog, UserX } from 'lucide-react'
import {
  getApiErrorMessage,
  type RoleDetail,
  type UserCreatePayload,
  type UserDetail,
  type UserUpdatePayload,
  usersApi,
} from '../../api/client'
import { Badge } from '../../components/ui/Badge'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Checkbox } from '../../components/ui/Checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/Dialog'
import { Input } from '../../components/ui/Input'
import { TableSkeleton } from '../../components/ui/SkeletonLoader'
import { Button } from '../../components/ui/Button'

type ModalMode = 'create' | 'edit'

interface UserFormState {
  email: string
  first_name: string
  last_name: string
  department: string
  job_title: string
  phone: string
  role_ids: number[]
  is_active: boolean
  is_superuser: boolean
}

const EMPTY_FORM: UserFormState = {
  email: '',
  first_name: '',
  last_name: '',
  department: '',
  job_title: '',
  phone: '',
  role_ids: [],
  is_active: true,
  is_superuser: false,
}

function formatUserName(user: UserDetail): string {
  return user.full_name || `${user.first_name} ${user.last_name}`.trim() || user.email
}

function getRoleNames(user: UserDetail): string[] {
  const names = user.roles.map((role) => role.name)
  if (user.is_superuser && !names.includes('admin')) {
    names.unshift('admin')
  }
  return names
}

export default function UserManagement() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<UserDetail[]>([])
  const [roles, setRoles] = useState<RoleDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [modalMode, setModalMode] = useState<ModalMode | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [form, setForm] = useState<UserFormState>(EMPTY_FORM)

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [usersResponse, rolesResponse] = await Promise.all([
        usersApi.list(1, 100),
        usersApi.listRoles(),
      ])
      setUsers(usersResponse.data.items ?? [])
      setRoles(rolesResponse.data ?? [])
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const filteredUsers = useMemo(() => {
    const query = searchTerm.trim().toLowerCase()
    if (!query) return users

    return users.filter((user) => {
      const roleNames = getRoleNames(user).join(' ').toLowerCase()
      return (
        formatUserName(user).toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query) ||
        roleNames.includes(query)
      )
    })
  }, [searchTerm, users])

  const openCreateModal = () => {
    setSelectedUser(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setModalMode('create')
  }

  const openEditModal = (user: UserDetail) => {
    setSelectedUser(user)
    setForm({
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      department: user.department ?? '',
      job_title: user.job_title ?? '',
      phone: user.phone ?? '',
      role_ids: user.roles.map((role) => role.id),
      is_active: user.is_active,
      is_superuser: user.is_superuser,
    })
    setFormError(null)
    setModalMode('edit')
  }

  const closeModal = () => {
    setModalMode(null)
    setSelectedUser(null)
    setFormError(null)
    setForm(EMPTY_FORM)
  }

  const updateForm = <K extends keyof UserFormState>(field: K, value: UserFormState[K]) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const toggleRole = (roleId: number, checked: boolean) => {
    updateForm(
      'role_ids',
      checked ? [...form.role_ids, roleId] : form.role_ids.filter((currentRoleId) => currentRoleId !== roleId),
    )
  }

  const handleSubmit = async () => {
    if (!form.email.trim() || !form.first_name.trim() || !form.last_name.trim()) {
      setFormError('Email, first name, and last name are required.')
      return
    }

    try {
      setSaving(true)
      setFormError(null)

      if (modalMode === 'create') {
        const payload: UserCreatePayload = {
          auth_provider: 'microsoft_sso',
          email: form.email.trim().toLowerCase(),
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          department: form.department.trim() || undefined,
          job_title: form.job_title.trim() || undefined,
          phone: form.phone.trim() || undefined,
          role_ids: form.role_ids,
          is_active: form.is_active,
          is_superuser: form.is_superuser,
        }
        await usersApi.create(payload)
      } else if (selectedUser) {
        const payload: UserUpdatePayload = {
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          department: form.department.trim() || undefined,
          job_title: form.job_title.trim() || undefined,
          phone: form.phone.trim() || undefined,
          role_ids: form.role_ids,
          is_active: form.is_active,
          is_superuser: form.is_superuser,
        }
        await usersApi.update(selectedUser.id, payload)
      }

      await loadData()
      closeModal()
    } catch (err) {
      setFormError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async (user: UserDetail) => {
    try {
      setError(null)
      await usersApi.update(user.id, { is_active: !user.is_active })
      await loadData()
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  if (loading) {
    return <TableSkeleton rows={8} columns={5} />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('admin.users.title', 'User Management')}</h1>
          <p className="mt-1 text-muted-foreground">
            {t(
              'admin.users.subtitle',
              'Create Microsoft SSO users, assign roles, and control superuser access.',
            )}
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void loadData()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={openCreateModal}>
            <Plus className="mr-2 h-4 w-4" />
            Add User
          </Button>
        </div>
      </div>

      {error && <div className="rounded-lg bg-destructive/10 p-4 text-destructive">{error}</div>}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          aria-label="Search users"
          placeholder={t('admin.users.search', 'Search by name, email, or role')}
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          className="pl-10"
        />
      </div>

      {filteredUsers.length === 0 ? (
        <Card>
          <CardHeader className="py-12 text-center text-muted-foreground">
            {users.length === 0
              ? 'No users have been provisioned yet.'
              : 'No users matched your current search.'}
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4">
          {filteredUsers.map((user) => (
            <Card key={user.id}>
              <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{formatUserName(user)}</p>
                    {user.is_superuser && (
                      <Badge className="bg-primary/10 text-primary">
                        <Shield className="mr-1 h-3 w-3" />
                        Superuser
                      </Badge>
                    )}
                    <Badge className={user.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    {user.azure_oid ? (
                      <Badge className="bg-blue-100 text-blue-800">Linked to Microsoft</Badge>
                    ) : (
                      <Badge className="bg-amber-100 text-amber-800">Awaiting first sign-in</Badge>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Mail className="h-3.5 w-3.5" />
                    {user.email}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {getRoleNames(user).length === 0 ? (
                      <Badge className="bg-gray-100 text-gray-700">No roles assigned</Badge>
                    ) : (
                      getRoleNames(user).map((roleName) => (
                        <Badge key={`${user.id}-${roleName}`} className="bg-secondary text-secondary-foreground">
                          {roleName}
                        </Badge>
                      ))
                    )}
                  </div>

                  {user.last_login && (
                    <p className="text-xs text-muted-foreground">Last login: {user.last_login}</p>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => openEditModal(user)}>
                    <UserCog className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button variant="outline" onClick={() => void handleToggleActive(user)}>
                    <UserX className="mr-2 h-4 w-4" />
                    {user.is_active ? 'Deactivate' : 'Reactivate'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={modalMode !== null} onOpenChange={(open) => (!open ? closeModal() : undefined)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{modalMode === 'create' ? 'Create Microsoft user' : 'Update user access'}</DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="user-first-name" className="mb-2 block text-sm font-medium">
                First name
              </label>
              <Input
                id="user-first-name"
                value={form.first_name}
                onChange={(event) => updateForm('first_name', event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="user-last-name" className="mb-2 block text-sm font-medium">
                Last name
              </label>
              <Input
                id="user-last-name"
                value={form.last_name}
                onChange={(event) => updateForm('last_name', event.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="user-email" className="mb-2 block text-sm font-medium">
                Email
              </label>
              <Input
                id="user-email"
                type="email"
                value={form.email}
                disabled={modalMode === 'edit'}
                onChange={(event) => updateForm('email', event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="user-department" className="mb-2 block text-sm font-medium">
                Department
              </label>
              <Input
                id="user-department"
                value={form.department}
                onChange={(event) => updateForm('department', event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="user-job-title" className="mb-2 block text-sm font-medium">
                Job title
              </label>
              <Input
                id="user-job-title"
                value={form.job_title}
                onChange={(event) => updateForm('job_title', event.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="user-phone" className="mb-2 block text-sm font-medium">
                Phone
              </label>
              <Input
                id="user-phone"
                value={form.phone}
                onChange={(event) => updateForm('phone', event.target.value)}
              />
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">Roles</p>
            {roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">No roles are currently available.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {roles.map((role) => {
                  const checked = form.role_ids.includes(role.id)
                  return (
                    <label
                      key={role.id}
                      htmlFor={`role-${role.id}`}
                      className="flex items-start gap-3 rounded-lg border border-border p-3"
                    >
                      <Checkbox
                        id={`role-${role.id}`}
                        checked={checked}
                        onCheckedChange={(value) => toggleRole(role.id, value === true)}
                      />
                      <span>
                        <span id={`role-${role.id}-label`} className="block text-sm font-medium">
                          {role.name}
                        </span>
                        {role.description && (
                          <span className="block text-xs text-muted-foreground">{role.description}</span>
                        )}
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label htmlFor="user-active" className="flex items-start gap-3 rounded-lg border border-border p-3">
              <Checkbox
                id="user-active"
                checked={form.is_active}
                onCheckedChange={(value) => updateForm('is_active', value === true)}
              />
              <span>
                <span id="user-active-label" className="block text-sm font-medium">
                  User is active
                </span>
                <span className="block text-xs text-muted-foreground">
                  Inactive users cannot sign in, including through Microsoft SSO.
                </span>
              </span>
            </label>

            <label
              htmlFor="user-superuser"
              className="flex items-start gap-3 rounded-lg border border-border p-3"
            >
              <Checkbox
                id="user-superuser"
                checked={form.is_superuser}
                onCheckedChange={(value) => updateForm('is_superuser', value === true)}
              />
              <span>
                <span id="user-superuser-label" className="block text-sm font-medium">
                  Superuser access
                </span>
                <span className="block text-xs text-muted-foreground">
                  Superusers can manage users and other restricted platform settings.
                </span>
              </span>
            </label>
          </div>

          {formError && <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{formError}</div>}

          <DialogFooter>
            <Button variant="ghost" onClick={closeModal} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => void handleSubmit()} disabled={saving}>
              {saving ? 'Saving...' : modalMode === 'create' ? 'Create user' : 'Save changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
