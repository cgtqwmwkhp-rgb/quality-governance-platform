import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { standardsCellAggregateApi, getApiErrorMessage } from '../../../api/client'
import type {
  NearShareApplyResponse,
  StandardsCellNearShare,
} from '../../../api/standardsCellAggregateTypes'
import { Badge, Button } from '../../../components/ui'

interface NearShareBannerProps {
  frameworkId: string
  clauseNumber: string
  nearShare?: StandardsCellNearShare | null
  onShared: () => void
}

/**
 * AP-07: propose one conformance evidence link onto ISO NEAR peer columns.
 * Amber, not sky — NEAR is not EXACT. Apply writes PROPOSED only.
 */
export function NearShareBanner({
  frameworkId,
  clauseNumber,
  nearShare,
  onShared,
}: NearShareBannerProps) {
  const { t } = useTranslation()
  const [selectedTargets, setSelectedTargets] = useState<string[]>([])
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [undoHandle, setUndoHandle] = useState<NearShareApplyResponse['undo'] | null>(null)

  const eligibleTargets = useMemo(
    () => (nearShare?.candidates ?? []).filter((c) => c.eligible),
    [nearShare],
  )
  const shareableLinks = nearShare?.shareable_links ?? []
  const additionTexts = useMemo(() => {
    const seen = new Set<string>()
    const out: string[] = []
    for (const candidate of nearShare?.candidates ?? []) {
      const text = (candidate.addition_text || '').trim()
      if (text && !seen.has(text)) {
        seen.add(text)
        out.push(text)
      }
    }
    return out
  }, [nearShare])

  if (!nearShare?.available) {
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
      nearShare.matrix_version_id == null
    ) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await standardsCellAggregateApi.applyNearShare({
        source_link_id: selectedLinkId,
        source_framework: frameworkId,
        source_clause: clauseNumber,
        target_frameworks: selectedTargets,
        matrix_version_id: nearShare.matrix_version_id,
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
      await standardsCellAggregateApi.undoNearShare({
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
      className="rounded-md border border-amber-300 bg-amber-50/90 px-3 py-3 space-y-3"
      data-testid="near-share-banner"
    >
      <div>
        <p className="text-sm font-medium text-foreground">
          {t('compliance.standards_workspace.near_share.title', {
            defaultValue: 'NEAR alignment — propose share (ISO family only)',
          })}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {t('compliance.standards_workspace.near_share.subtitle', {
            defaultValue:
              'Creates proposed links on ISO NEAR peers. The addition is not attested, so coverage does not count until an operator confirms.',
          })}
        </p>
        <p className="text-xs text-amber-900 mt-1" data-testid="near-share-confirm-note">
          {t('compliance.standards_workspace.near_share.confirm_note', {
            defaultValue:
              'NEAR is not EXACT. Links stay proposed until someone confirms the addition is in the deliverable.',
          })}
        </p>
      </div>

      {additionTexts.length > 0 ? (
        <div
          className="rounded border border-amber-200 bg-white/70 px-2 py-2 space-y-1"
          data-testid="near-share-addition"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-amber-900">
            {t('compliance.standards_workspace.near_share.addition', {
              defaultValue: 'Required addition',
            })}
          </p>
          {additionTexts.map((text) => (
            <p key={text} className="text-xs text-foreground">
              {text}
            </p>
          ))}
        </div>
      ) : null}

      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t('compliance.standards_workspace.near_share.evidence', { defaultValue: 'Evidence' })}
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
                data-testid={`near-share-link-${link.link_id}`}
              >
                {link.title || `${link.entity_type}:${link.entity_id}`}
              </Button>
            )
          })}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t('compliance.standards_workspace.near_share.targets', {
            defaultValue: 'Propose onto',
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
                data-testid={`near-share-target-${candidate.framework}`}
              >
                {candidate.framework} · {candidate.clause_number}
              </Button>
            )
          })}
          {(nearShare.candidates ?? [])
            .filter((c) => !c.eligible)
            .map((candidate) => (
              <Badge
                key={candidate.clause_key}
                variant="secondary"
                data-testid={`near-share-blocked-${candidate.framework}`}
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
          data-testid="near-share-apply"
        >
          {t('compliance.standards_workspace.near_share.apply', { defaultValue: 'Propose share' })}
        </Button>
        {undoHandle ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void onUndo()}
            data-testid="near-share-undo"
          >
            {t('compliance.standards_workspace.near_share.undo', {
              defaultValue: 'Undo last proposal',
            })}
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="text-sm text-destructive" data-testid="near-share-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}
