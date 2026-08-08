/**
 * Pre-publish Doc Graph impact checklist (Wave 1 PR-D).
 *
 * Read-only honesty before library publish. Flag-gated by the caller.
 * Never labels Doc Graph as the Golden Thread.
 */
import { AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import type { PublishImpactPreview } from './documentPublishImpactHelpers'

export interface DocumentPublishImpactPreviewProps {
  documentTitle: string
  preview: PublishImpactPreview | null
  loading: boolean
  error: string | null
  publishing: boolean
  /** When false, confirm is disabled (Entity360 ImpactBundle incomplete). */
  canPublish?: boolean
  degradedReasons?: string[]
  onCancel: () => void
  onConfirm: () => void
}

export function DocumentPublishImpactPreview({
  documentTitle,
  preview,
  loading,
  error,
  publishing,
  canPublish = true,
  degradedReasons = [],
  onCancel,
  onConfirm,
}: DocumentPublishImpactPreviewProps) {
  const publishBlocked = !canPublish
  return (
    <div className="space-y-4" data-testid="documents-publish-impact-preview">
      <div className="space-y-1">
        <h3 className="font-medium text-foreground">Publish impact preview</h3>
        <p className="text-sm text-muted-foreground">
          Review likely side effects before publishing{' '}
          <span className="font-medium text-foreground">{documentTitle}</span>. This is a
          read-only checklist — it does not change lineage, files, or Golden Thread links.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
          Gathering dependents, evidence, campaigns and impacts…
        </div>
      ) : null}

      {publishBlocked ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid="documents-publish-impact-blocked"
        >
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            Publish is blocked until the impact bundle is complete.
            {degradedReasons.length > 0
              ? ` ${degradedReasons.join('; ')}`
              : error
                ? ` ${error}`
                : null}
          </span>
        </div>
      ) : null}

      {error && !publishBlocked ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid="documents-publish-impact-error"
        >
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            Could not fully load the preview ({error}). You can still publish, or cancel and
            retry.
          </span>
        </div>
      ) : null}

      {!loading && preview ? (
        <div className="space-y-3" data-testid="documents-publish-impact-sections">
          {preview.empty ? (
            <p
              className="text-sm text-muted-foreground rounded-lg border border-border p-3"
              data-testid="documents-publish-impact-empty"
            >
              No downstream relationships, confirmed clause evidence, active campaigns, or open
              regulatory impacts are recorded yet. Publish will still run the governed knowledge
              lifecycle hooks for rematch and quiz draft generation.
            </p>
          ) : null}
          {preview.sections.map((section) =>
            section.items.length === 0 && section.id !== 'lifecycle' ? null : (
              <section
                key={section.id}
                className="rounded-lg border border-border p-3 space-y-2"
                data-testid={`documents-publish-impact-section-${section.id}`}
              >
                <div>
                  <h4 className="text-sm font-medium text-foreground">{section.title}</h4>
                  <p className="text-xs text-muted-foreground">{section.description}</p>
                </div>
                {section.items.length === 0 ? (
                  <p className="text-xs text-muted-foreground">None recorded.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {section.items.map((item) => (
                      <li key={item.id} className="text-sm text-foreground">
                        <span className="font-medium">{item.label}</span>
                        {item.detail ? (
                          <span className="text-muted-foreground"> — {item.detail}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ),
          )}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
        <Button
          variant="ghost"
          onClick={onCancel}
          disabled={publishing}
          data-testid="documents-publish-impact-cancel"
        >
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          disabled={publishing || loading || publishBlocked}
          data-testid="documents-publish-impact-confirm"
        >
          {publishing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Publish version
        </Button>
      </div>
    </div>
  )
}

export default DocumentPublishImpactPreview
