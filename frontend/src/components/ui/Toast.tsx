import { useEffect, useRef, useCallback, useState } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface ToastData {
  id: string;
  message: string;
  variant: ToastVariant;
}

const ICONS: Record<ToastVariant, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success:
    'bg-card border-success/30 text-foreground shadow-[0_0_0_1px_hsl(var(--success)/0.1)]',
  error:
    'bg-card border-destructive/30 text-foreground shadow-[0_0_0_1px_hsl(var(--destructive)/0.1)]',
  warning:
    'bg-card border-warning/30 text-foreground shadow-[0_0_0_1px_hsl(var(--warning)/0.1)]',
  info:
    'bg-card border-border text-foreground shadow-[0_0_0_1px_hsl(var(--border)/0.5)]',
};

const ICON_STYLES: Record<ToastVariant, string> = {
  success: 'text-success',
  error: 'text-destructive',
  warning: 'text-warning',
  info: 'text-info',
};

const PROGRESS_STYLES: Record<ToastVariant, string> = {
  success: 'bg-success',
  error: 'bg-destructive',
  warning: 'bg-warning',
  info: 'bg-info',
};

function ToastItem({
  toast,
  onDismiss,
  duration = 4000,
}: {
  toast: ToastData;
  onDismiss: (id: string) => void;
  duration?: number;
}) {
  const [exiting, setExiting] = useState(false);
  const [progress, setProgress] = useState(100);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const startRef = useRef(Date.now());
  const rafRef = useRef<number>();

  const dismiss = useCallback(() => {
    setExiting(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setTimeout(() => onDismiss(toast.id), 280);
  }, [onDismiss, toast.id]);

  useEffect(() => {
    startRef.current = Date.now();

    const tick = () => {
      const elapsed = Date.now() - startRef.current;
      const remaining = Math.max(0, 1 - elapsed / duration);
      setProgress(remaining * 100);
      if (remaining > 0) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    timerRef.current = setTimeout(dismiss, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [dismiss, duration]);

  const Icon = ICONS[toast.variant];

  return (
    <div
      role="alert"
      aria-live="polite"
      className={`
        pointer-events-auto w-[380px] max-w-[calc(100vw-2rem)]
        flex items-start gap-3 rounded-xl border px-4 py-3.5
        shadow-lg backdrop-blur-sm
        ${VARIANT_STYLES[toast.variant]}
        ${exiting ? 'animate-toast-out' : 'animate-toast-in'}
      `}
      style={{
        animationFillMode: 'forwards',
      }}
    >
      <div
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${ICON_STYLES[toast.variant]}`}
      >
        <Icon className="h-[18px] w-[18px]" strokeWidth={2.2} />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium leading-snug">{toast.message}</p>
      </div>

      <button
        onClick={dismiss}
        className="mt-0.5 shrink-0 rounded-md p-0.5 text-muted-foreground/60 transition-colors hover:text-foreground hover:bg-muted/50"
        aria-label="Dismiss notification"
      >
        <X className="h-4 w-4" />
      </button>

      {/* Progress bar */}
      <div className="absolute bottom-0 left-3 right-3 h-[2px] overflow-hidden rounded-full bg-muted/30">
        <div
          className={`h-full rounded-full transition-none ${PROGRESS_STYLES[toast.variant]}`}
          style={{ width: `${progress}%`, opacity: 0.5 }}
        />
      </div>
    </div>
  );
}

/**
 * Toast container — renders in a fixed position below the top nav bar.
 * Stacks multiple toasts with spacing.
 */
export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastData[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-[72px] right-5 z-[200] flex flex-col gap-2.5 pointer-events-none"
      aria-label="Notifications"
      aria-live="polite"
      aria-atomic="false"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// ============================================================================
// Hook for easy consumption
// ============================================================================

let toastCounter = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((message: string, variant: ToastVariant = 'success') => {
    const id = `toast-${++toastCounter}-${Date.now()}`;
    setToasts((prev) => [...prev, { id, message, variant }]);
  }, []);

  return { toasts, show, dismiss };
}
