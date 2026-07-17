import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Plus,
  Search,
  Building,
  Edit,
  Trash2,
  Check,
  X,
  GripVertical,
  Mail,
  Phone,
  Loader2,
} from 'lucide-react'
import { contractsApi, type Contract, getApiErrorMessage } from '../../api/client'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/Dialog'
import { cn } from '../../helpers/utils'
import { AdminLoadUnavailable, captureAdminLoadError } from './adminLoadHelpers'

export default function ContractsManagement() {
  const { t } = useTranslation()
  const [contracts, setContracts] = useState<Contract[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [editingContract, setEditingContract] = useState<Contract | null>(null)
  const [isAdding, setIsAdding] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [formData, setFormData] = useState<Partial<Contract>>({
    name: '',
    code: '',
    description: '',
    client_name: '',
    client_contact: '',
    client_email: '',
    is_active: true,
  })
  const [actionError, setActionError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)

  const loadContracts = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const data = await contractsApi.list(!showInactive)
      setContracts(data.items ?? [])
    } catch (err) {
      setContracts([])
      setLoadError(
        captureAdminLoadError(
          err,
          { component: 'ContractsManagement', action: 'load' },
          'Contracts could not be loaded — this is not an empty list.',
        ),
      )
    } finally {
      setIsLoading(false)
    }
  }, [showInactive])

  useEffect(() => {
    void loadContracts()
  }, [loadContracts])

  const filteredContracts = contracts
    .filter((c) => {
      const matchesSearch =
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.client_name?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false)
      const matchesActive = showInactive || c.is_active
      return matchesSearch && matchesActive
    })
    .sort((a, b) => a.display_order - b.display_order)

  const handleEdit = (contract: Contract) => {
    setEditingContract(contract)
    setFormData(contract)
    setIsAdding(false)
  }

  const handleAdd = () => {
    setIsAdding(true)
    setEditingContract(null)
    setFormData({
      name: '',
      code: '',
      description: '',
      client_name: '',
      client_contact: '',
      client_email: '',
      is_active: true,
    })
  }

  const handleCancel = () => {
    setEditingContract(null)
    setIsAdding(false)
    setFormData({})
  }

  const handleSave = async () => {
    setIsSaving(true)
    setActionError(null)
    try {
      if (isAdding) {
        const created = await contractsApi.create({
          name: formData.name || '',
          code: formData.code || '',
          description: formData.description,
          client_name: formData.client_name,
          client_contact: formData.client_contact,
          client_email: formData.client_email,
          is_active: formData.is_active ?? true,
          display_order: contracts.length + 1,
        })
        setContracts((prev) => [...prev, created])
      } else if (editingContract) {
        const updated = await contractsApi.update(editingContract.id, formData)
        setContracts((prev) => prev.map((c) => (c.id === editingContract.id ? updated : c)))
      }

      handleCancel()
    } catch (err) {
      setActionError(getApiErrorMessage(err, t('admin.contracts.save_error', 'Failed to save contract.')))
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = (id: number) => {
    setDeleteTarget(id)
  }

  const confirmDelete = async () => {
    if (deleteTarget === null) return
    setActionError(null)
    try {
      await contractsApi.delete(deleteTarget)
      setContracts((prev) => prev.filter((c) => c.id !== deleteTarget))
    } catch (err) {
      setActionError(getApiErrorMessage(err, t('admin.contracts.delete_error', 'Failed to delete contract.')))
    } finally {
      setDeleteTarget(null)
    }
  }

  const toggleActive = async (contract: Contract) => {
    setActionError(null)
    try {
      const updated = await contractsApi.update(contract.id, { is_active: !contract.is_active })
      setContracts((prev) => prev.map((c) => (c.id === contract.id ? updated : c)))
    } catch (err) {
      setActionError(getApiErrorMessage(err, t('admin.contracts.save_error', 'Failed to save contract.')))
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-card border-b border-border">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">
                {t('admin.contracts.title', 'Contracts')}
              </h1>
              <p className="text-muted-foreground mt-1">
                {t('admin.contracts.subtitle', 'Manage contracts available in forms and reports')}
              </p>
            </div>
            <Button onClick={handleAdd} disabled={Boolean(loadError)}>
              <Plus className="w-4 h-4 mr-2" />
              {t('admin.contracts.add_contract', 'Add Contract')}
            </Button>
          </div>

          <div className="mt-6 flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t('admin.contracts.search_placeholder', 'Search contracts...')}
                className="pl-10"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded border-border"
              />
              {t('admin.contracts.show_inactive', 'Show inactive')}
            </label>
          </div>
        </div>
      </header>

      {loadError && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 mt-4">
          <AdminLoadUnavailable
            testId="contracts-list-unavailable"
            title={t('admin.contracts.unavailable_title', 'Contracts unavailable')}
            description={t(
              'admin.contracts.unavailable_description',
              'The contract list could not be loaded. Retry or check connectivity — this is not an empty list.',
            )}
            message={loadError}
            onRetry={() => void loadContracts()}
          />
        </div>
      )}

      {actionError && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 mt-4">
          <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
            <p className="text-sm text-destructive">{actionError}</p>
            <button
              onClick={() => setActionError(null)}
              className="text-sm font-medium text-destructive hover:underline"
            >
              {t('common.dismiss', 'Dismiss')}
            </button>
          </div>
        </div>
      )}

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        {isLoading ? (
          <Card className="p-12 text-center">
            <Loader2 className="w-8 h-8 mx-auto text-muted-foreground animate-spin mb-4" />
            <p className="text-muted-foreground">{t('common.loading', 'Loading')}</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-3">
              {!loadError && filteredContracts.length === 0 ? (
                <Card className="p-12 text-center">
                  <Building className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    {t('admin.contracts.empty_title', 'No contracts found')}
                  </h3>
                  <p className="text-muted-foreground mb-4">
                    {t('admin.contracts.empty_subtitle', 'Add your first contract to get started')}
                  </p>
                  <Button onClick={handleAdd}>
                    <Plus className="w-4 h-4 mr-2" />
                    {t('admin.contracts.add_contract', 'Add Contract')}
                  </Button>
                </Card>
              ) : (
                filteredContracts.map((contract) => (
                  <Card
                    key={contract.id}
                    className={cn(
                      'p-4 flex items-center gap-4 group',
                      !contract.is_active && 'opacity-60',
                      editingContract?.id === contract.id && 'ring-2 ring-primary',
                    )}
                  >
                    <GripVertical className="w-5 h-5 text-muted-foreground cursor-grab" />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-foreground">{contract.name}</h3>
                        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                          {contract.code}
                        </span>
                        {!contract.is_active && (
                          <span className="text-xs text-destructive bg-destructive/10 px-2 py-0.5 rounded">
                            Inactive
                          </span>
                        )}
                      </div>
                      {contract.client_name && (
                        <p className="text-sm text-muted-foreground">{contract.client_name}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleEdit(contract)}
                        className="p-2 hover:bg-muted rounded-lg transition-colors"
                        title="Edit"
                      >
                        <Edit className="w-4 h-4 text-muted-foreground" />
                      </button>
                      <button
                        onClick={() => void toggleActive(contract)}
                        className="p-2 hover:bg-muted rounded-lg transition-colors"
                        title={contract.is_active ? 'Deactivate' : 'Activate'}
                      >
                        {contract.is_active ? (
                          <X className="w-4 h-4 text-muted-foreground" />
                        ) : (
                          <Check className="w-4 h-4 text-primary" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDelete(contract.id)}
                        className="p-2 hover:bg-destructive/10 rounded-lg transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </button>
                    </div>
                  </Card>
                ))
              )}
            </div>

            <div>
              <Card className="p-6 sticky top-6">
                <h3 className="font-semibold text-foreground mb-4">
                  {isAdding
                    ? t('admin.contracts.add_contract', 'Add Contract')
                    : editingContract
                      ? t('admin.contracts.edit_contract', 'Edit Contract')
                      : t('admin.contracts.contract_details', 'Contract Details')}
                </h3>

                {isAdding || editingContract ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {t('admin.contracts.name_label', 'Name *')}
                      </label>
                      <Input
                        value={formData.name || ''}
                        onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                        placeholder="e.g. UKPN"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {t('admin.contracts.code_label', 'Code *')}
                      </label>
                      <Input
                        value={formData.code || ''}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            code: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''),
                          }))
                        }
                        placeholder="e.g. ukpn"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        {t(
                          'admin.contracts.code_hint',
                          'Lowercase, no spaces. Used for data storage.',
                        )}
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {t('admin.contracts.client_name', 'Client Name')}
                      </label>
                      <Input
                        value={formData.client_name || ''}
                        onChange={(e) =>
                          setFormData((prev) => ({ ...prev, client_name: e.target.value }))
                        }
                        placeholder="e.g. UK Power Networks"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="contract-description"
                        className="block text-sm font-medium text-foreground mb-2"
                      >
                        Description
                      </label>
                      <Textarea
                        id="contract-description"
                        value={formData.description || ''}
                        onChange={(e) =>
                          setFormData((prev) => ({ ...prev, description: e.target.value }))
                        }
                        placeholder="Optional description..."
                        rows={2}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {t('admin.contracts.contact_email', 'Contact Email')}
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                          type="email"
                          value={formData.client_email || ''}
                          onChange={(e) =>
                            setFormData((prev) => ({ ...prev, client_email: e.target.value }))
                          }
                          placeholder="contact@example.com"
                          className="pl-10"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {t('admin.contracts.contact_phone', 'Contact Phone')}
                      </label>
                      <div className="relative">
                        <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                          type="tel"
                          value={formData.client_contact || ''}
                          onChange={(e) =>
                            setFormData((prev) => ({ ...prev, client_contact: e.target.value }))
                          }
                          placeholder="+44 1234 567890"
                          className="pl-10"
                        />
                      </div>
                    </div>

                    <label className="flex items-center justify-between">
                      <span className="text-sm text-foreground">Active</span>
                      <input
                        type="checkbox"
                        checked={formData.is_active ?? true}
                        onChange={(e) =>
                          setFormData((prev) => ({ ...prev, is_active: e.target.checked }))
                        }
                        className="rounded border-border"
                      />
                    </label>

                    <div className="flex gap-3 pt-4">
                      <Button variant="outline" onClick={handleCancel} className="flex-1">
                        Cancel
                      </Button>
                      <Button onClick={() => void handleSave()} disabled={isSaving} className="flex-1">
                        {isSaving ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Check className="w-4 h-4 mr-2" />
                        )}
                        Save
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Building className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>{t('admin.contracts.select_to_edit', 'Select a contract to edit')}</p>
                    <p className="text-sm">{t('admin.contracts.or_add_new', 'or add a new one')}</p>
                  </div>
                )}
              </Card>
            </div>
          </div>
        )}
      </main>

      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Contract</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t(
              'admin.contracts.delete_confirm',
              'Are you sure you want to delete this contract? This action cannot be undone.',
            )}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => void confirmDelete()}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
