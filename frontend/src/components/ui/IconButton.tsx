import * as React from 'react'
import { Button, type ButtonProps } from './Button'

export interface IconOnlyControlProps {
  'aria-label': string
  title?: string
}

/**
 * Accessible-name props for a control whose only visible content is an icon.
 *
 * Use this on elements that cannot be an `<IconButton>` — anchors, `NavLink`,
 * or triggers rendered by a third-party primitive. Prefer `<IconButton>` for
 * plain buttons: there the name is a required prop, so the pattern cannot be
 * skipped by accident.
 *
 * `title` carries the same string so pointer users get a tooltip, but the
 * accessible name always comes from `aria-label`. `title` on its own is a
 * last-resort name that voice-control tools and touch screen readers skip.
 */
export function iconOnlyControlProps(
  label: string,
  options: { tooltip?: boolean } = {},
): IconOnlyControlProps {
  const { tooltip = true } = options

  if (import.meta.env.DEV && label.trim() === '') {
    console.error(
      'iconOnlyControlProps: icon-only control rendered with an empty accessible name. ' +
        'Screen-reader users will hear "button" with no indication of its purpose.',
    )
  }

  return tooltip ? { 'aria-label': label, title: label } : { 'aria-label': label }
}

export interface IconButtonProps
  extends Omit<ButtonProps, 'aria-label' | 'aria-labelledby' | 'title'> {
  /** Accessible name announced in place of the icon. Required — never optional. */
  label: string
  /** Set false to suppress the pointer tooltip. The accessible name is unaffected. */
  tooltip?: boolean
}

/**
 * A button whose visible content is an icon only.
 *
 * Defaults to `type="button"` so an icon control placed inside a form cannot
 * submit it, and to the ghost/icon variant these controls already use.
 */
const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      label,
      tooltip = true,
      variant = 'ghost',
      size = 'icon',
      type = 'button',
      children,
      ...props
    },
    ref,
  ) => (
    <Button
      ref={ref}
      type={type}
      variant={variant}
      size={size}
      {...props}
      {...iconOnlyControlProps(label, { tooltip })}
    >
      {children}
    </Button>
  ),
)
IconButton.displayName = 'IconButton'

export { IconButton }
