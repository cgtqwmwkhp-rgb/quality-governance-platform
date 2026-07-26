import { describe, it, expect, vi, afterEach } from 'vitest'
import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { X } from 'lucide-react'
import { IconButton, iconOnlyControlProps } from '../IconButton'
import { expectNoA11yViolations } from '../../../test/axe-helper'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('IconButton', () => {
  it('names an icon-only control for assistive technology', async () => {
    const { container } = render(
      <IconButton label="Dismiss banner">
        <X className="h-4 w-4" aria-hidden="true" />
      </IconButton>,
    )

    expect(screen.getByRole('button', { name: 'Dismiss banner' })).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('exposes the same string as a pointer tooltip by default', () => {
    render(
      <IconButton label="Dismiss banner">
        <X aria-hidden="true" />
      </IconButton>,
    )

    expect(screen.getByRole('button', { name: 'Dismiss banner' })).toHaveAttribute(
      'title',
      'Dismiss banner',
    )
  })

  it('keeps the accessible name when the tooltip is suppressed', () => {
    render(
      <IconButton label="Dismiss banner" tooltip={false}>
        <X aria-hidden="true" />
      </IconButton>,
    )

    const button = screen.getByRole('button', { name: 'Dismiss banner' })
    expect(button).not.toHaveAttribute('title')
  })

  it('defaults to type="button" so it cannot submit a surrounding form', () => {
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <IconButton label="Clear field">
          <X aria-hidden="true" />
        </IconButton>
      </form>,
    )

    expect(screen.getByRole('button', { name: 'Clear field' })).toHaveAttribute('type', 'button')
  })

  it('still allows an explicit submit button', () => {
    render(
      <IconButton label="Save" type="submit">
        <X aria-hidden="true" />
      </IconButton>,
    )

    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'submit')
  })

  it('forwards clicks, refs, and disabled state', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    const ref = createRef<HTMLButtonElement>()

    const { rerender } = render(
      <IconButton ref={ref} label="Refresh" onClick={onClick}>
        <X aria-hidden="true" />
      </IconButton>,
    )

    expect(ref.current).toBeInstanceOf(HTMLButtonElement)
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(onClick).toHaveBeenCalledTimes(1)

    rerender(
      <IconButton ref={ref} label="Refresh" onClick={onClick} disabled>
        <X aria-hidden="true" />
      </IconButton>,
    )
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('reports an empty accessible name instead of rendering a nameless control', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <IconButton label="   ">
        <X aria-hidden="true" />
      </IconButton>,
    )

    expect(consoleError).toHaveBeenCalledWith(
      expect.stringContaining('empty accessible name'),
    )
  })
})

describe('iconOnlyControlProps', () => {
  it('returns an aria-label and a matching tooltip', () => {
    expect(iconOnlyControlProps('Notifications')).toEqual({
      'aria-label': 'Notifications',
      title: 'Notifications',
    })
  })

  it('omits the tooltip when asked', () => {
    expect(iconOnlyControlProps('Notifications', { tooltip: false })).toEqual({
      'aria-label': 'Notifications',
    })
  })

  it('names a link that cannot be an IconButton', () => {
    render(
      // eslint-disable-next-line jsx-a11y/anchor-is-valid
      <a href="/notifications" {...iconOnlyControlProps('Notifications, 3 unread')}>
        <X aria-hidden="true" />
      </a>,
    )

    expect(screen.getByRole('link', { name: 'Notifications, 3 unread' })).toBeInTheDocument()
  })
})
