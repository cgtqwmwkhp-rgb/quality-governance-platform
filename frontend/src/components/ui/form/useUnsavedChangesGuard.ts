import { useCallback, useState } from 'react'

export interface UseUnsavedChangesGuardOptions {
  /** True when the form holds work that would be lost on close. */
  dirty: boolean
  /** Actually close the dialog and reset the form. */
  onDiscard: () => void
}

export interface UnsavedChangesGuard {
  /** Pass straight to `<Dialog onOpenChange>`; covers Escape, overlay click and the X. */
  handleOpenChange: (open: boolean) => void
  /** Use for an explicit Cancel button. */
  requestClose: () => void
  confirmOpen: boolean
  confirmDiscard: () => void
  keepEditing: () => void
}

/**
 * Stops a dialog throwing away typed work without asking.
 *
 * Escape reaching the dialog at all already means no inner popover was open —
 * Radix's dismissable-layer stack gives the topmost layer (an open Select) the
 * key first — so by the time we see it, the only question left is whether the
 * form is dirty (PX-172).
 */
export function useUnsavedChangesGuard({
  dirty,
  onDiscard,
}: UseUnsavedChangesGuardOptions): UnsavedChangesGuard {
  const [confirmOpen, setConfirmOpen] = useState(false)

  const requestClose = useCallback(() => {
    if (dirty) {
      setConfirmOpen(true)
      return
    }
    onDiscard()
  }, [dirty, onDiscard])

  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (open) return
      requestClose()
    },
    [requestClose],
  )

  const confirmDiscard = useCallback(() => {
    setConfirmOpen(false)
    onDiscard()
  }, [onDiscard])

  const keepEditing = useCallback(() => setConfirmOpen(false), [])

  return { handleOpenChange, requestClose, confirmOpen, confirmDiscard, keepEditing }
}
