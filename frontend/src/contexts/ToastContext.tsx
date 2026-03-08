import { createContext, useContext, useCallback, type ReactNode } from 'react'
import { ToastContainer, useToast, type ToastVariant } from '../components/ui/Toast'

// Ref to hold the show function so it can be called from outside React (e.g. API interceptor)
const showRef = { current: null as ((msg: string, variant: ToastVariant) => void) | null }

interface ToastContextValue {
  show: (message: string, variant?: ToastVariant) => void
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const { toasts, show, dismiss } = useToast()

  // Keep showRef in sync so toast.success/error/etc can be called from anywhere
  showRef.current = show

  const showStable = useCallback(
    (message: string, variant: ToastVariant = 'success') => {
      show(message, variant)
    },
    [show],
  )

  const value: ToastContextValue = { show: showStable, dismiss }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useGlobalToast() {
  const ctx = useContext(ToastContext)
  if (ctx === undefined) {
    throw new Error('useGlobalToast must be used within a ToastProvider')
  }
  return ctx
}

/**
 * Standalone toast API — call from anywhere (including outside React, e.g. API interceptors).
 * Requires ToastProvider to be mounted. Calls before mount are no-ops.
 */
export const toast = {
  success: (msg: string) => showRef.current?.(msg, 'success'),
  error: (msg: string) => showRef.current?.(msg, 'error'),
  warning: (msg: string) => showRef.current?.(msg, 'warning'),
  info: (msg: string) => showRef.current?.(msg, 'info'),
}
