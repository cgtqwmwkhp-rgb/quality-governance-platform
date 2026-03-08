import { useTranslation } from 'react-i18next'
import { CheckCircle, X, AlertTriangle } from 'lucide-react'

export interface PublishDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  isPublishing: boolean
  templateName: string
  error?: string | null
}

export default function PublishDialog({
  isOpen,
  onClose,
  onConfirm,
  isPublishing,
  templateName,
  error,
}: PublishDialogProps) {
  const { t } = useTranslation()

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        role="presentation"
      />
      <div className="relative bg-card border border-border rounded-2xl p-6 max-w-md w-full shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 text-muted-foreground hover:text-foreground rounded"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-6">
          <div className="mx-auto w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-6 h-6 text-emerald-500" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">
            {t('audit_builder.publish_template', 'Publish Template')}
          </h3>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to publish{' '}
            <strong>&quot;{templateName || 'Untitled'}&quot;</strong>? Once published, this template
            will be available for audit scheduling.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={isPublishing}
            className="flex-1 px-4 py-2 bg-secondary text-foreground font-medium rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPublishing}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            {isPublishing ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <CheckCircle className="w-4 h-4" />
            )}
            Publish
          </button>
        </div>
      </div>
    </div>
  )
}
