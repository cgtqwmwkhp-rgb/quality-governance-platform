import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, ArrowLeft, Award, Camera, Loader2, Package, QrCode } from 'lucide-react'
import {
  safetyAssetsApi,
  type SafetyAsset,
  type SafetyAssetType,
  type SafetyLocation,
} from '../api/safetyAssetsClient'
import {
  evidenceAssetsApi,
  getApiErrorMessage,
  workforceApi,
  type CompetencyRequirement,
  type WdpEngineerMatrix,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Card, CardContent } from '../components/ui/Card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'

function statusVariant(status: string): BadgeVariant {
  switch (status) {
    case 'active':
      return 'success'
    case 'quarantined':
      return 'critical'
    case 'vor':
    case 'maintenance':
      return 'warning'
    case 'decommissioned':
      return 'secondary'
    default:
      return 'outline'
  }
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleDateString()
}

const STATUS_OPTIONS = ['active', 'vor', 'maintenance', 'decommissioned', 'quarantined'] as const

function holderState(state: string | undefined): boolean {
  return state === 'active' || state === 'competent'
}

export default function SafetyAssetDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const assetId = Number(id)

  const [asset, setAsset] = useState<SafetyAsset | null>(null)
  const [assetType, setAssetType] = useState<SafetyAssetType | null>(null)
  const [location, setLocation] = useState<SafetyLocation | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [savingStatus, setSavingStatus] = useState(false)
  const [uploadingPhoto, setUploadingPhoto] = useState(false)
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null)
  const [photoError, setPhotoError] = useState<string | null>(null)
  const [competencyRequirements, setCompetencyRequirements] = useState<
    CompetencyRequirement[] | null
  >(null)
  const [competencyRequirementsUnavailable, setCompetencyRequirementsUnavailable] = useState(false)
  const [competencyMatrix, setCompetencyMatrix] = useState<WdpEngineerMatrix | null>(null)
  const [competencyMatrixUnavailable, setCompetencyMatrixUnavailable] = useState(false)

  const load = useCallback(async () => {
    if (!Number.isFinite(assetId) || assetId <= 0) {
      setLoadError(t('safetyAssets.detail.invalid_id', 'Invalid asset id.'))
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError(null)
    setPhotoError(null)
    try {
      const res = await safetyAssetsApi.getAsset(assetId)
      const next = res.data
      setAsset(next)

      const [typeRes, locRes] = await Promise.allSettled([
        safetyAssetsApi.listAssetTypes({ page: 1, page_size: 200 }),
        next.location_id != null
          ? safetyAssetsApi.getLocation(next.location_id)
          : Promise.resolve(null),
      ])
      if (typeRes.status === 'fulfilled') {
        const match = (typeRes.value.data.items ?? []).find((at) => at.id === next.asset_type_id)
        setAssetType(match ?? null)
      } else {
        setAssetType(null)
      }
      if (locRes.status === 'fulfilled' && locRes.value) {
        setLocation(locRes.value.data)
      } else {
        setLocation(null)
      }

      const [requirementsRes, matrixRes] = await Promise.allSettled([
        workforceApi.competencyRequirements.list({
          asset_type_id: next.asset_type_id,
          page_size: 500,
        }),
        workforceApi.analytics.getEngineerMatrix(),
      ])
      if (requirementsRes.status === 'fulfilled') {
        setCompetencyRequirements(requirementsRes.value.data.items ?? [])
        setCompetencyRequirementsUnavailable(false)
      } else {
        setCompetencyRequirements(null)
        setCompetencyRequirementsUnavailable(true)
      }
      if (matrixRes.status === 'fulfilled') {
        setCompetencyMatrix(matrixRes.value.data)
        setCompetencyMatrixUnavailable(false)
      } else {
        setCompetencyMatrix(null)
        setCompetencyMatrixUnavailable(true)
      }

      if (next.photo_evidence_id != null) {
        try {
          const signed = await evidenceAssetsApi.getSignedUrl(next.photo_evidence_id)
          setPhotoPreviewUrl(signed.data?.signed_url ?? null)
        } catch {
          setPhotoPreviewUrl(null)
          setPhotoError(
            t(
              'safetyAssets.detail.photo_unavailable',
              'Photo evidence reference exists but preview is unavailable.',
            ),
          )
        }
      } else {
        setPhotoPreviewUrl(null)
      }
    } catch (err) {
      const message = getApiErrorMessage(
        err,
        t('safetyAssets.detail.load_failed', 'Could not load asset detail.'),
      )
      setLoadError(message)
      setAsset(null)
    } finally {
      setLoading(false)
    }
  }, [assetId, t])

  useEffect(() => {
    void load()
  }, [load])

  const handleStatusChange = async (status: string) => {
    if (!asset) return
    setSavingStatus(true)
    try {
      const res = await safetyAssetsApi.updateAsset(asset.id, { status })
      setAsset(res.data)
      toast.success(t('safetyAssets.detail.status_updated', 'Status updated.'))
    } catch (err) {
      toast.error(
        getApiErrorMessage(err, t('safetyAssets.detail.status_failed', 'Status update failed.')),
      )
    } finally {
      setSavingStatus(false)
    }
  }

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!asset || !e.target.files?.length) return
    const file = e.target.files[0]
    setUploadingPhoto(true)
    setPhotoError(null)
    try {
      const uploadRes = await evidenceAssetsApi.upload(file, {
        source_module: 'asset',
        source_id: asset.id,
        title: file.name,
        visibility: 'internal_customer',
      })
      const evidenceId = uploadRes.data?.id
      if (evidenceId == null) {
        throw new Error(
          t('safetyAssets.detail.photo_no_id', 'Upload succeeded but no evidence id returned.'),
        )
      }
      const updated = await safetyAssetsApi.updateAsset(asset.id, {
        photo_evidence_id: evidenceId,
      })
      setAsset(updated.data)
      try {
        const signed = await evidenceAssetsApi.getSignedUrl(evidenceId)
        setPhotoPreviewUrl(signed.data?.signed_url ?? null)
      } catch {
        setPhotoPreviewUrl(null)
      }
      toast.success(t('safetyAssets.detail.photo_uploaded', 'Photo attached.'))
    } catch (err) {
      const message = getApiErrorMessage(
        err,
        t('safetyAssets.detail.photo_failed', 'Photo upload failed.'),
      )
      setPhotoError(message)
      toast.error(message)
    } finally {
      setUploadingPhoto(false)
      e.target.value = ''
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        {t('safetyAssets.loading', 'Loading…')}
      </div>
    )
  }

  if (loadError || !asset) {
    return (
      <div className="space-y-4">
        <Link
          to="/safety-assets"
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('safetyAssets.detail.back', 'Back to register')}
        </Link>
        <div
          className="rounded-lg border border-destructive/30 bg-destructive/5 p-4"
          role="alert"
          data-testid="safety-asset-detail-error"
        >
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <p className="text-sm font-medium">
              {loadError ?? t('safetyAssets.detail.not_found', 'Asset not found.')}
            </p>
          </div>
        </div>
      </div>
    )
  }

  const assignmentLabel = asset.vehicle_reg
    ? t('safetyAssets.detail.assignment_vehicle', 'Vehicle {{reg}}', { reg: asset.vehicle_reg })
    : location
      ? t('safetyAssets.detail.assignment_location', '{{name}} ({{kind}})', {
          name: location.name,
          kind: location.kind,
        })
      : asset.location_id
        ? t('safetyAssets.detail.assignment_location_id', 'Location #{{id}}', {
            id: asset.location_id,
          })
        : asset.site || t('safetyAssets.detail.assignment_none', 'Unassigned')

  const competencyHolders =
    competencyMatrix?.engineers.filter((engineer) =>
      holderState(engineer.competencies[asset.asset_type_id]),
    ) ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <Link
            to="/safety-assets"
            className="mb-3 inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('safetyAssets.detail.back', 'Back to register')}
          </Link>
          <div className="flex items-center gap-3">
            <Package className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-3xl font-bold text-foreground">{asset.name}</h1>
              <p className="text-muted-foreground">{asset.asset_number}</p>
            </div>
          </div>
        </div>
        <Badge variant={statusVariant(asset.status)}>{asset.status}</Badge>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-3 p-5">
            <h2 className="text-sm font-semibold text-foreground">
              {t('safetyAssets.detail.identity', 'Identity')}
            </h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_number', 'Number')}
              </dt>
              <dd className="text-foreground">{asset.asset_number}</dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_type', 'Type')}
              </dt>
              <dd className="text-foreground">
                {assetType?.name ?? `#${asset.asset_type_id}`}
                {assetType?.category ? ` · ${assetType.category}` : ''}
              </dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_make', 'Make / model')}
              </dt>
              <dd className="text-foreground">
                {[asset.make, asset.model].filter(Boolean).join(' ') || '—'}
              </dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_serial', 'Serial')}
              </dt>
              <dd className="text-foreground">{asset.serial_number || '—'}</dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_external', 'External ID')}
              </dt>
              <dd className="font-mono text-xs text-foreground">{asset.external_id}</dd>
            </dl>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardContent className="space-y-4 p-5" data-testid="safety-asset-competency">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Award className="h-4 w-4" />
              {t('safetyAssets.detail.competency', 'Competency')}
            </h2>
            <div className="rounded-lg border border-border bg-secondary/30 p-3 text-sm">
              <p className="font-medium text-foreground">
                {t('safetyAssets.detail.competency_type_heading', 'Asset type requirements')}
              </p>
              <p className="mt-1 text-muted-foreground">
                {t(
                  'safetyAssets.detail.competency_type_explainer',
                  'Requirements are linked to the asset type, not to this physical asset instance.',
                )}
              </p>
            </div>
            {competencyRequirementsUnavailable ? (
              <p
                className="text-sm text-muted-foreground"
                data-testid="safety-asset-competency-requirements-unavailable"
              >
                {t(
                  'safetyAssets.detail.competency_requirements_unavailable',
                  'Type competency requirements are currently unavailable.',
                )}
              </p>
            ) : competencyRequirements?.length ? (
              <ul className="space-y-2" data-testid="safety-asset-competency-requirements">
                {competencyRequirements.map((requirement) => (
                  <li
                    key={requirement.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3 text-sm"
                  >
                    <div>
                      <p className="font-medium text-foreground">{requirement.name}</p>
                      {requirement.description ? (
                        <p className="mt-1 text-muted-foreground">{requirement.description}</p>
                      ) : null}
                    </div>
                    <Badge variant={requirement.is_mandatory ? 'warning' : 'secondary'}>
                      {requirement.is_mandatory
                        ? t('safetyAssets.detail.competency_mandatory', 'Mandatory')
                        : t('safetyAssets.detail.competency_optional', 'Optional')}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : competencyRequirements ? (
              <p
                className="text-sm text-muted-foreground"
                data-testid="safety-asset-competency-requirements-empty"
              >
                {t(
                  'safetyAssets.detail.competency_requirements_empty',
                  'No competency requirements are configured for this asset type.',
                )}
              </p>
            ) : null}

            <div className="border-t border-border pt-4">
              <p className="font-medium text-foreground">
                {t(
                  'safetyAssets.detail.competency_instance_heading',
                  'This physical asset instance',
                )}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {t(
                  'safetyAssets.detail.competency_instance_explainer',
                  'Competency records identify workforce capability for this asset type. They are not assigned to asset instance {{assetNumber}}.',
                  { assetNumber: asset.asset_number },
                )}
              </p>
              {competencyMatrixUnavailable ? (
                <p
                  className="mt-3 text-sm text-muted-foreground"
                  data-testid="safety-asset-competency-holders-unavailable"
                >
                  {t(
                    'safetyAssets.detail.competency_holders_unavailable',
                    'Workforce competency status is currently unavailable.',
                  )}
                </p>
              ) : competencyMatrix ? (
                competencyHolders.length ? (
                  <ul className="mt-3 space-y-2" data-testid="safety-asset-competency-holders">
                    {competencyHolders.map((engineer) => (
                      <li
                        key={engineer.engineer_id}
                        className="flex items-center justify-between rounded-md border border-border p-3 text-sm"
                      >
                        <span className="text-foreground">
                          {t('safetyAssets.detail.competency_engineer', 'Engineer #{{id}}', {
                            id: engineer.engineer_id,
                          })}
                        </span>
                        <Badge variant="success">
                          {engineer.competencies[asset.asset_type_id]}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p
                    className="mt-3 text-sm text-muted-foreground"
                    data-testid="safety-asset-competency-holders-empty"
                  >
                    {t(
                      'safetyAssets.detail.competency_holders_empty',
                      'No active competency holders are recorded for this asset type.',
                    )}
                  </p>
                )
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-5">
            <h2 className="text-sm font-semibold text-foreground">
              {t('safetyAssets.detail.hierarchy', 'Hierarchy assignment')}
            </h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_assignment', 'Assignment')}
              </dt>
              <dd className="text-foreground">{assignmentLabel}</dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_owner', 'Owner')}
              </dt>
              <dd className="text-foreground">
                {asset.owner_user_id != null ? `#${asset.owner_user_id}` : '—'}
              </dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_expiry', 'Expiry')}
              </dt>
              <dd className="text-foreground">{formatDate(asset.expiry_date)}</dd>
              <dt className="text-muted-foreground">
                {t('safetyAssets.detail.field_site', 'Legacy site')}
              </dt>
              <dd className="text-foreground">{asset.site || '—'}</dd>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-5">
            <h2 className="text-sm font-semibold text-foreground">
              {t('safetyAssets.detail.status_heading', 'Status')}
            </h2>
            <Select
              value={asset.status}
              onValueChange={(v) => {
                void handleStatusChange(v)
              }}
              disabled={savingStatus}
            >
              <SelectTrigger data-testid="safety-asset-status-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {savingStatus ? (
              <p className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                {t('safetyAssets.detail.saving', 'Saving…')}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <QrCode className="h-4 w-4" />
              {t('safetyAssets.detail.qr', 'QR code')}
            </h2>
            {asset.qr_code_data ? (
              <div
                className="rounded-lg border border-border bg-secondary/40 p-4"
                data-testid="safety-asset-qr"
              >
                <p className="break-all font-mono text-xs text-foreground">{asset.qr_code_data}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('safetyAssets.detail.qr_none', 'No QR payload recorded for this asset.')}
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardContent className="space-y-3 p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Camera className="h-4 w-4" />
              {t('safetyAssets.detail.photo', 'Photo evidence')}
            </h2>
            {photoPreviewUrl ? (
              <img
                src={photoPreviewUrl}
                alt={t('safetyAssets.detail.photo_alt', 'Asset photo')}
                className="max-h-48 rounded-lg border border-border object-contain"
              />
            ) : asset.photo_evidence_id != null ? (
              <p className="text-sm text-muted-foreground">
                {t('safetyAssets.detail.photo_id', 'Evidence #{{id}}', {
                  id: asset.photo_evidence_id,
                })}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('safetyAssets.detail.photo_none', 'No photo attached.')}
              </p>
            )}
            {photoError ? (
              <p className="text-sm text-destructive" role="status">
                {photoError}
              </p>
            ) : null}
            <div>
              <label className="inline-flex cursor-pointer">
                <span className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-secondary">
                  {uploadingPhoto
                    ? t('safetyAssets.detail.photo_uploading', 'Uploading…')
                    : t('safetyAssets.detail.photo_upload', 'Upload photo')}
                </span>
                <input
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  onChange={(e) => {
                    void handlePhotoUpload(e)
                  }}
                  disabled={uploadingPhoto}
                  data-testid="safety-asset-photo-input"
                />
              </label>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Placeholders for AM-THREAD — honest empty, not fabricated links */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="p-5" data-testid="safety-asset-linked-cases">
            <h2 className="text-sm font-semibold text-foreground">
              {t('safetyAssets.detail.linked_cases', 'Linked cases')}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {t(
                'safetyAssets.detail.linked_cases_placeholder',
                'No linked cases yet — case linkage will be wired by AM-THREAD.',
              )}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5" data-testid="safety-asset-open-actions">
            <h2 className="text-sm font-semibold text-foreground">
              {t('safetyAssets.detail.open_actions', 'Open actions')}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {t(
                'safetyAssets.detail.open_actions_placeholder',
                'No open actions shown — CAPA/actions wiring lands with AM-THREAD.',
              )}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
