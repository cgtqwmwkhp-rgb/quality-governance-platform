import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../helpers/utils'

const progressBarTrackVariants = cva('relative w-full overflow-hidden rounded-full bg-muted', {
  variants: {
    variant: {
      default: '[&_[data-progress-fill]]:bg-primary',
      success: '[&_[data-progress-fill]]:bg-success',
      warning: '[&_[data-progress-fill]]:bg-warning',
      destructive: '[&_[data-progress-fill]]:bg-destructive',
    },
    size: {
      sm: 'h-1.5',
      md: 'h-2.5',
      lg: 'h-4',
    },
  },
  defaultVariants: {
    variant: 'default',
    size: 'md',
  },
})

export interface ProgressBarProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'ref'>,
    VariantProps<typeof progressBarTrackVariants> {
  value?: number
  max?: number
}

const ProgressBar = React.forwardRef<HTMLProgressElement, ProgressBarProps>(
  ({ className, value = 0, max = 100, variant, size, ...props }, ref) => {
    const safeMax = max > 0 ? max : 100
    const clamped = Math.min(Math.max(value, 0), safeMax)
    const percent = safeMax > 0 ? (clamped / safeMax) * 100 : 0

    return (
      <div
        className={cn(progressBarTrackVariants({ variant, size }), className)}
        {...props}
      >
        <progress
          ref={ref}
          className="absolute inset-0 h-full w-full cursor-default opacity-0"
          value={clamped}
          max={safeMax}
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={safeMax}
        />
        <div
          data-progress-fill
          className="pointer-events-none absolute inset-y-0 left-0 rounded-full transition-[width] duration-200 ease-out"
          style={{ width: `${percent}%` }}
          aria-hidden
        />
      </div>
    )
  },
)
ProgressBar.displayName = 'ProgressBar'

export { ProgressBar, progressBarTrackVariants }
