import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SystemSettings from '../SystemSettings'
import { expectNoA11yViolations } from '../../../test/axe-helper'

const mockList = vi.fn()

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>('../../../api/client')
  return {
    ...actual,
    settingsApi: {
      list: (...args: unknown[]) => mockList(...args),
      update: vi.fn(),
      get: vi.fn(),
    },
  }
})

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
  return Array.from(
    container.querySelectorAll<HTMLElement>('input, textarea, select, [role="switch"]'),
  )
}

function accessibleNameSource(container: HTMLElement, control: HTMLElement) {
  return (
    control.getAttribute('aria-label')?.trim() ||
    control.getAttribute('aria-labelledby')?.trim() ||
    (control.id ? container.querySelector(`label[for="${CSS.escape(control.id)}"]`) : null)
  )
}

describe('SystemSettings accessibility', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockList.mockResolvedValue({
      items: [
        {
          key: 'company_name',
          value: 'Plantexpand Limited',
          category: 'branding',
          description: 'Company name displayed throughout the system',
          value_type: 'string',
          is_editable: true,
        },
        {
          key: 'company_logo_url',
          value: 'https://example.com/logo.png',
          category: 'branding',
          description: 'URL to company logo image',
          value_type: 'string',
          is_editable: true,
        },
        {
          key: 'primary_color',
          value: '#0B6E4F',
          category: 'branding',
          description: 'Primary brand color',
          value_type: 'color',
          is_editable: true,
        },
        {
          key: 'accent_color',
          value: '#148F5C',
          category: 'branding',
          description: 'Accent/hover color',
          value_type: 'color',
          is_editable: true,
        },
      ],
      total: 4,
    })
  })

  it('gives every field in every category a programmatic label', async () => {
    const user = userEvent.setup()
    const { container } = render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

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

  it('associates the Branding labels with their inputs by name', async () => {
    render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

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

  it('does not render internal field keys as visible copy', async () => {
    render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

    for (const key of ['company_name', 'company_logo_url', 'primary_color', 'accent_color']) {
      expect(screen.queryByText(key)).not.toBeInTheDocument()
      expect(document.getElementById(`setting-${key}`)).not.toBeNull()
    }
  })

  it('exposes boolean settings as named switches that report their state', async () => {
    const user = userEvent.setup()
    render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

    await user.click(categoryButton('Notifications'))

    const emailToggle = screen.getByRole('switch', { name: 'Enable email notifications' })
    expect(emailToggle).toHaveAttribute('aria-checked', 'true')

    await user.click(emailToggle)
    expect(emailToggle).toHaveAttribute('aria-checked', 'false')
  })

  it('toggles a boolean setting when its visible label is clicked', async () => {
    const user = userEvent.setup()
    render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

    await user.click(categoryButton('Notifications'))

    const toggle = screen.getByRole('switch', { name: 'Enable push notifications' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')

    await user.click(screen.getByText('Enable push notifications', { selector: 'label' }))
    expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  it('has no serious a11y violations on the branding panel', async () => {
    const { container } = render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')
    await expectNoA11yViolations(container)
  })
})
