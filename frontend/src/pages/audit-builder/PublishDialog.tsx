import { useTranslation } from 'react-i18next'
import { CheckCircle, AlertTriangle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'

export interface PublishDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  isPublishing: boolean
  templateName: string
  error?: string | null
  runHref?: string
  runCtaLabel?: string
}

export default function PublishDialog({
  isOpen,
  onClose,
  onConfirm,
  isPublishing,
  templateName,
  error,
  runHref,
  runCtaLabel,
}: PublishDialogProps) {
  const { t } = useTranslation()

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      {/* Radix supplies role="dialog", aria-modal, the focus trap, Escape, and
          aria-hidden on everything behind the overlay. The hand-rolled div this
          replaced had none of them (PX-162). */}
      <DialogContent className="max-w-md">
        <DialogHeader className="text-center sm:text-center">
          <div className="mx-auto w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-6 h-6 text-emerald-500" aria-hidden="true" />
          </div>
          <DialogTitle className="text-lg font-semibold text-foreground mb-2">
            {t('audit_builder.publish_template', 'Publish Template')}
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            Are you sure you want to publish{' '}
            <strong>&quot;{templateName || 'Untitled'}&quot;</strong>?{' '}
            {t(
              'audit_builder.publish_available',
              'Once published, this template will be available for the matching run type.',
            )}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0" aria-hidden="true" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPublishing}
            className="flex-1 px-4 py-2 bg-secondary text-foreground font-medium rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPublishing}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            {isPublishing ? (
              <div
                aria-hidden="true"
                className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"
              />
            ) : (
              <CheckCircle className="w-4 h-4" aria-hidden="true" />
            )}
            Publish
          </button>
        </div>
        {runHref && runCtaLabel ? (
          <p className="text-xs text-muted-foreground text-center">
            After publish:{' '}
            <a href={runHref} className="text-primary underline-offset-2 hover:underline">
              {runCtaLabel}
            </a>
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
