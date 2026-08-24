import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { standardsCellAggregateApi, getApiErrorMessage } from '../../../api/client'
import type {
  ExactShareApplyResponse,
  StandardsCellExactShare,
} from '../../../api/standardsCellAggregateTypes'
import { Badge, Button } from '../../../components/ui'

interface ExactShareBannerProps {
  frameworkId: string
  clauseNumber: string
  exactShare?: StandardsCellExactShare | null
  onShared: () => void
}

/**
 * Wave 2 PR-D: share one conformance evidence link onto EXACT peer columns.
 * Renders above workspace tabs so apply/undo survive tab changes.
 */
export function ExactShareBanner({
  frameworkId,
  clauseNumber,
  exactShare,
  onShared,
}: ExactShareBannerProps) {
  const { t } = useTranslation()
  const [selectedTargets, setSelectedTargets] = useState<string[]>([])
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [undoHandle, setUndoHandle] = useState<ExactShareApplyResponse['undo'] | null>(null)

  const eligibleTargets = useMemo(
    () => (exactShare?.candidates ?? []).filter((c) => c.eligible),
    [exactShare],
  )
  const shareableLinks = exactShare?.shareable_links ?? []

  if (!exactShare?.available) {
    return null
  }

  const toggleTarget = (framework: string) => {
    setSelectedTargets((prev) =>
      prev.includes(framework) ? prev.filter((f) => f !== framework) : [...prev, framework],
    )
  }

  const onApply = async () => {
    if (
      selectedLinkId == null ||
      selectedTargets.length === 0 ||
      exactShare.matrix_version_id == null
    ) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await standardsCellAggregateApi.applyExactShare({
        source_link_id: selectedLinkId,
        source_framework: frameworkId,
        source_clause: clauseNumber,
        target_frameworks: selectedTargets,
        matrix_version_id: exactShare.matrix_version_id,
      })
      setUndoHandle(res.data.undo)
      setSelectedTargets([])
      onShared()
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const onUndo = async () => {
    if (!undoHandle) return
    setBusy(true)
    setError(null)
    try {
      await standardsCellAggregateApi.undoExactShare({
        link_ids: undoHandle.link_ids,
        applied_at: undoHandle.applied_at,
      })
      setUndoHandle(null)
      onShared()
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="rounded-md border border-sky-200 bg-sky-50/80 px-3 py-3 space-y-3"
      data-testid="exact-share-banner"
    >
      <div>
        <p className="text-sm font-medium text-foreground">
          {t('compliance.standards_workspace.exact_share.title', {
            defaultValue: 'EXACT alignment — share evidence once',
          })}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {t('compliance.standards_workspace.exact_share.subtitle', {
            defaultValue:
              'Create the same evidence link on EXACT peer columns. Existing links are left untouched.',
          })}
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t('compliance.standards_workspace.exact_share.evidence', { defaultValue: 'Evidence' })}
        </p>
        <div className="flex flex-wrap gap-2">
          {shareableLinks.map((link) => {
            const selected = selectedLinkId === link.link_id
            return (
              <Button
                key={link.link_id}
                type="button"
                size="sm"
                variant={selected ? 'default' : 'outline'}
                onClick={() => setSelectedLinkId(link.link_id)}
                data-testid={`exact-share-link-${link.link_id}`}
              >
                {link.title || `${link.entity_type}:${link.entity_id}`}
              </Button>
            )
          })}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t('compliance.standards_workspace.exact_share.targets', {
            defaultValue: 'Share onto',
          })}
        </p>
        <div className="flex flex-wrap gap-2">
          {eligibleTargets.map((candidate) => {
            const selected = selectedTargets.includes(candidate.framework)
            return (
              <Button
                key={candidate.clause_key}
                type="button"
                size="sm"
                variant={selected ? 'default' : 'outline'}
                onClick={() => toggleTarget(candidate.framework)}
                data-testid={`exact-share-target-${candidate.framework}`}
              >
                {candidate.framework} · {candidate.clause_number}
              </Button>
            )
          })}
          {(exactShare.candidates ?? [])
            .filter((c) => !c.eligible)
            .map((candidate) => (
              <Badge
                key={candidate.clause_key}
                variant="secondary"
                data-testid={`exact-share-blocked-${candidate.framework}`}
                title={candidate.blocked_reasons.join(', ')}
              >
                {candidate.framework}: {candidate.blocked_reasons.join(', ') || 'blocked'}
              </Badge>
            ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          disabled={busy || selectedLinkId == null || selectedTargets.length === 0}
          onClick={() => void onApply()}
          data-testid="exact-share-apply"
        >
          {t('compliance.standards_workspace.exact_share.apply', { defaultValue: 'Share evidence' })}
        </Button>
        {undoHandle ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void onUndo()}
            data-testid="exact-share-undo"
          >
            {t('compliance.standards_workspace.exact_share.undo', {
              defaultValue: 'Undo last share',
            })}
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="text-sm text-destructive" data-testid="exact-share-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}
