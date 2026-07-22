import { useEffect, useRef, useState } from 'react'
import { Loader2, Save, X } from 'lucide-react'
import { safetyAssetsApi, type SafetyAsset, type SafetyAssetType } from '../../api/safetyAssetsClient'
import EntitySelectAnswer from './EntitySelectAnswer'
import { ASSESSMENT_MODES } from './types'

export interface AssessmentDimensionsValue {
  assessmentMode: string | null
  assetId: number | null
  assetTypeId: number | null
  locationId: number | null
  customerCode: string | null
}

export interface AssessmentDimensionsPanelProps {
  value: AssessmentDimensionsValue
  onSave: (value: AssessmentDimensionsValue) => Promise<void> | void
  onClose: () => void
  saving?: boolean
  error?: string | null
}

/** Header panel (Phase 1) letting the auditor set/adjust the run's branching +
 * reporting dimensions — which drives section composition and analytics. */
export default function AssessmentDimensionsPanel({
  value,
  onSave,
  onClose,
  saving = false,
  error,
}: AssessmentDimensionsPanelProps) {
  const [draft, setDraft] = useState<AssessmentDimensionsValue>(value)
  const [assetTypes, setAssetTypes] = useState<SafetyAssetType[]>([])
  const [assetQuery, setAssetQuery] = useState('')
  const [assetResults, setAssetResults] = useState<SafetyAsset[]>([])
  const [assetLabel, setAssetLabel] = useState('')
  const [assetLoading, setAssetLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => setDraft(value), [value])

  useEffect(() => {
    safetyAssetsApi
      .listAssetTypes({ page_size: 100, is_active: true })
      .then(({ data }) => setAssetTypes(data.items))
      .catch(() => setAssetTypes([]))
  }, [])

  useEffect(() => {
    if (!draft.assetId) return
    safetyAssetsApi
      .getAsset(draft.assetId)
      .then(({ data }) => setAssetLabel(`${data.name} (${data.asset_number})`))
      .catch(() => setAssetLabel(`Asset #${draft.assetId}`))
    // Only re-resolve the label when the selected asset id itself changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.assetId])

  const runAssetSearch = (search: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (search.trim().length < 2) {
        setAssetResults([])
        return
      }
      setAssetLoading(true)
      safetyAssetsApi
        .listAssets({
          search: search.trim(),
          asset_type_id: draft.assetTypeId ?? undefined,
          page_size: 20,
        })
        .then(({ data }) => setAssetResults(data.items))
        .catch(() => setAssetResults([]))
        .finally(() => setAssetLoading(false))
    }, 300)
  }

  return (
    <div className="bg-card/95 border-b border-border px-4 py-4" data-testid="assessment-dimensions-panel">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-foreground">Assessment details</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close assessment details"
          className="p-1 text-muted-foreground hover:text-foreground"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Assessment mode</p>
          <div className="flex flex-wrap gap-1.5">
            {ASSESSMENT_MODES.map((mode) => (
              <button
                key={mode.value}
                type="button"
                data-testid={`dimensions-mode-${mode.value}`}
                onClick={() =>
                  setDraft((prev) => ({
                    ...prev,
                    assessmentMode: prev.assessmentMode === mode.value ? null : mode.value,
                  }))
                }
                className={`px-2 py-1.5 rounded-lg text-xs transition-colors ${
                  draft.assessmentMode === mode.value
                    ? 'bg-primary/20 text-primary border border-primary/40'
                    : 'bg-secondary text-muted-foreground border border-border hover:bg-secondary/70'
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label htmlFor="dimensions-asset-type" className="block text-xs text-muted-foreground mb-1">
            Asset type
          </label>
          <select
            id="dimensions-asset-type"
            value={draft.assetTypeId ?? ''}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                assetTypeId: e.target.value ? Number(e.target.value) : null,
              }))
            }
            className="w-full px-3 py-2 bg-secondary border border-border rounded-lg text-sm text-foreground"
          >
            <option value="">Not set</option>
            {assetTypes.map((assetType) => (
              <option key={assetType.id} value={assetType.id}>
                {assetType.name}
              </option>
            ))}
          </select>
        </div>

        <div className="relative">
          <label htmlFor="dimensions-asset" className="block text-xs text-muted-foreground mb-1">
            Asset
          </label>
          <input
            id="dimensions-asset"
            type="text"
            value={assetQuery || assetLabel}
            onChange={(e) => {
              setAssetQuery(e.target.value)
              setAssetLabel('')
              setDraft((prev) => ({ ...prev, assetId: null }))
              runAssetSearch(e.target.value)
            }}
            placeholder="Search assets…"
            className="w-full px-3 py-2 bg-secondary border border-border rounded-lg text-sm text-foreground"
          />
          {assetLoading && (
            <Loader2 className="absolute right-2 top-9 w-4 h-4 animate-spin text-muted-foreground" />
          )}
          {assetQuery.trim().length >= 2 && assetResults.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-lg border border-border bg-card shadow-xl max-h-48 overflow-y-auto">
              {assetResults.map((asset) => (
                <button
                  key={asset.id}
                  type="button"
                  onClick={() => {
                    setDraft((prev) => ({
                      ...prev,
                      assetId: asset.id,
                      assetTypeId: prev.assetTypeId ?? asset.asset_type_id,
                    }))
                    setAssetLabel(`${asset.name} (${asset.asset_number})`)
                    setAssetQuery('')
                    setAssetResults([])
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                >
                  {asset.name} <span className="text-xs text-muted-foreground">({asset.asset_number})</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <span className="block text-xs text-muted-foreground mb-1">Location</span>
          <EntitySelectAnswer
            kind="location"
            value={draft.locationId ? String(draft.locationId) : ''}
            onChange={(id) => setDraft((prev) => ({ ...prev, locationId: id ? Number(id) : null }))}
          />
        </div>

        <div>
          <span className="block text-xs text-muted-foreground mb-1">Customer</span>
          <EntitySelectAnswer
            kind="customer"
            value={draft.customerCode ?? ''}
            onChange={(code) => setDraft((prev) => ({ ...prev, customerCode: code || null }))}
          />
        </div>
      </div>

      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => void onSave(draft)}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save details
        </button>
      </div>
    </div>
  )
}
