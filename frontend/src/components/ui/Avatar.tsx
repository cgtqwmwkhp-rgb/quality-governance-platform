import * as React from 'react'
import { cn } from '../../helpers/utils'

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  src?: string
  alt?: string
  fallback?: string
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
  xl: 'h-16 w-16 text-lg',
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, size = 'md', src, alt, fallback, ...props }, ref) => {
    const [imageError, setImageError] = React.useState(false)

    const initials =
      fallback ||
      (alt
        ? alt
            .split(' ')
            .map((w) => w[0])
            .join('')
            .slice(0, 2)
            .toUpperCase()
        : '?')
    const isInteractive = !!props.onClick

    const { onClick, ...restProps } = props as any

    if (isInteractive) {
      return (
        <button
          ref={ref as React.Ref<HTMLButtonElement>}
          type="button"
          aria-label={alt || initials}
          onClick={onClick}
          className={cn(
            'relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface font-medium text-muted-foreground border-0 p-0',
            sizeClasses[size],
            className,
          )}
          {...restProps}
        >
          {src && !imageError ? (
            // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- onError is a DOM event, not user interaction
            <img
              src={src}
              alt={alt || ''}
              className="aspect-square h-full w-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            <span>{initials}</span>
          )}
        </button>
      )
    }

    return (
      <div
        ref={ref}
        role="img"
        aria-label={alt || initials}
        className={cn(
          'relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface font-medium text-muted-foreground',
          sizeClasses[size],
          className,
        )}
        {...restProps}
      >
        {src && !imageError ? (
          // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- onError is a DOM event, not user interaction
          <img
            src={src}
            alt={alt || ''}
            className="aspect-square h-full w-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <span>{initials}</span>
        )}
      </div>
    )
  },
)
Avatar.displayName = 'Avatar'

export { Avatar }
