import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from './ui/Button'

export interface SessionExpiryWarningProps {
  /** True while the "stay signed in" refresh is in flight. */
  extending?: boolean
  onExtend: () => void
}

/**
 * Warns before the session ends instead of dropping the user on the login
 * page without explanation (PX-179).
 *
 * Copy is limited to the two keys pre-landed by #1352
 * (`session.expiry_warning` / `session.expiry_warning_action`); this lane does
 * not own the locale files, so no failure-state copy is added here. If the
 * extend attempt fails the banner simply stays put and the action can be
 * retried until the 401 interceptor takes over.
 *
 * Lazy-loaded by `Layout`, which is also what gates rendering — so this
 * component has no `open` prop and its code stays out of the shell's entry
 * chunk until the session is genuinely ending.
 */
export default function SessionExpiryWarning({
  extending = false,
  onExtend,
}: SessionExpiryWarningProps) {
  const { t } = useTranslation()

  return (
    <div
      // assertive: the user has ~2 minutes, so this must interrupt rather than
      // wait for a pause in screen-reader output.
      role="alert"
      aria-live="assertive"
      className="fixed top-20 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg bg-warning/10 text-warning border border-warning/30 backdrop-blur-sm"
    >
      <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
      <span className="text-sm font-medium">
        {t('session.expiry_warning', 'Your session expires soon.')}
      </span>
      <Button size="sm" onClick={onExtend} disabled={extending}>
        {t('session.expiry_warning_action', 'Stay signed in')}
      </Button>
    </div>
  )
}
