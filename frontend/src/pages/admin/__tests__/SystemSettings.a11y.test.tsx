import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SystemSettings from '../SystemSettings'
import { expectNoA11yViolations } from '../../../test/axe-helper'

const CATEGORIES = [
  'Branding',
  'Contact Details',
  'Notifications',
  'Workflow',
  'Security',
  'Regional',
]

function categoryButton(name: string) {
  return screen.getByRole('button', { name: new RegExp(`^${name}\\b`) })
}

/** Every form control currently on screen, whatever its type. */
function visibleControls(container: HTMLElement) {
  return Array.from(container.querySelectorAll<HTMLElement>('input, textarea, [role="switch"]'))
}

function accessibleNameSource(container: HTMLElement, control: HTMLElement) {
  return (
    control.getAttribute('aria-label')?.trim() ||
    control.getAttribute('aria-labelledby')?.trim() ||
    (control.id ? container.querySelector(`label[for="${CSS.escape(control.id)}"]`) : null)
  )
}

describe('SystemSettings accessibility', () => {
  it('gives every field in every category a programmatic label', async () => {
    const user = userEvent.setup()
    const { container } = render(<SystemSettings />)

    for (const category of CATEGORIES) {
      await user.click(categoryButton(category))

      const controls = visibleControls(container)
      expect(controls.length, `no controls rendered for ${category}`).toBeGreaterThan(0)

      const unlabelled = controls
        .filter((control) => !accessibleNameSource(container, control))
        .map((control) => control.outerHTML)

      expect(unlabelled, `unlabelled controls in ${category}`).toEqual([])
    }
  })

  it('associates the Branding labels with their inputs by name', () => {
    render(<SystemSettings />)

    expect(
      screen.getByRole('textbox', { name: 'Company name displayed throughout the system' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'URL to company logo image' })).toBeInTheDocument()
    expect(
      screen.getByRole('textbox', { name: 'Primary brand color (hex value)' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('textbox', { name: 'Accent/hover color (hex value)' }),
    ).toBeInTheDocument()
  })

  // PX-198: internal storage keys were rendered as visible copy beside the
  // human labels. They now only exist as DOM ids.
  it('does not render internal field keys as visible copy', () => {
    render(<SystemSettings />)

    for (const key of ['company_name', 'company_logo_url', 'primary_color', 'accent_color']) {
      expect(screen.queryByText(key)).not.toBeInTheDocument()
      expect(document.getElementById(`setting-${key}`)).not.toBeNull()
    }
  })

  it('exposes boolean settings as named switches that report their state', async () => {
    const user = userEvent.setup()
    render(<SystemSettings />)

    await user.click(categoryButton('Notifications'))

    const emailToggle = screen.getByRole('switch', { name: 'Enable email notifications' })
    expect(emailToggle).toHaveAttribute('aria-checked', 'true')

    await user.click(emailToggle)
    expect(emailToggle).toHaveAttribute('aria-checked', 'false')
  })

  it('toggles a boolean setting when its visible label is clicked', async () => {
    const user = userEvent.setup()
    render(<SystemSettings />)

    await user.click(categoryButton('Notifications'))

    const toggle = screen.getByRole('switch', { name: 'Enable push notifications' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')

    await user.click(screen.getByText('Enable push notifications'))

    expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  it('renders the settings screen without axe violations', async () => {
    const { container } = render(<SystemSettings />)
    await expectNoA11yViolations(container)
  })
})
