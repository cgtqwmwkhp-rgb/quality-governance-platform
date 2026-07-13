/**
 * Real axe coverage for LibraryShell tab navigation chrome (IA-W4/W5).
 * Complements LibraryShell.test.tsx functional assertions and Playwright a11y-audit.
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { LibraryShell } from '../LibraryShell'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('LibraryShell accessibility', () => {
  it('has no a11y violations on Documents view', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/documents']}>
        <LibraryShell activeView="documents">document list</LibraryShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole('navigation', { name: 'nav.library' })).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('has no a11y violations on Policies view with header actions', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/policies']}>
        <LibraryShell
          activeView="policies"
          actions={
            <button type="button">
              Create policy
            </button>
          }
        >
          policy register
        </LibraryShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: /nav\.policies/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await expectNoA11yViolations(container)
  })
})
