import { useEffect } from 'react'

/** Overlay roles whose own Escape handling must win over a page-level shortcut. */
const OVERLAY_SELECTOR =
  '[role="dialog"],[role="alertdialog"],[role="listbox"],[role="menu"],[data-radix-popper-content-wrapper]'

/**
 * True when the keystroke happened inside a dialog, popover, menu or listbox.
 *
 * The overlay is still mounted while its own Escape handler runs, so this is
 * reliable from a `window` listener firing later in the same event.
 */
export function isEventInsideOverlay(event: Pick<KeyboardEvent, 'target'>): boolean {
  const target = event.target
  if (!(target instanceof Element)) return false
  return target.closest(OVERLAY_SELECTOR) !== null
}

/** True when any overlay is currently open, regardless of where focus sits. */
function anyOverlayOpen(doc: Document): boolean {
  return doc.querySelector('[role="dialog"],[role="alertdialog"]') !== null
}

/**
 * "Escape goes back to the register" for a detail page, without stealing Escape
 * from whatever is on top of it.
 *
 * A bare `window` keydown listener also fires for Escape pressed inside a modal,
 * so closing a dialog navigated the route away and discarded the user's work in
 * one keystroke (PX-172). Escape is handled here only when nothing is layered
 * over the page and no other handler has already claimed the event.
 */
export function useEscapeToGoBack(enabled: boolean, onGoBack: () => void): void {
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (event.defaultPrevented) return
      if (isEventInsideOverlay(event)) return
      if (anyOverlayOpen(document)) return
      onGoBack()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled, onGoBack])
}
