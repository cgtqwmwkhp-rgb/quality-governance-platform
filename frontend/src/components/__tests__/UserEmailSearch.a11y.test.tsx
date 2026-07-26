import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UserEmailSearch } from '../UserEmailSearch'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('../../api/client', () => ({
  usersApi: { search: vi.fn().mockResolvedValue({ data: [] }) },
}))

vi.mock('../../utils/errorTracker', () => ({ trackError: vi.fn() }))

describe('UserEmailSearch accessibility', () => {
  it('associates its visible label with the input', async () => {
    const { container } = render(
      <UserEmailSearch value="" onChange={() => {}} label="Lead investigator" />,
    )

    const input = screen.getByRole('textbox', { name: /Lead investigator/ })
    expect(input).toBeInTheDocument()
    expect(input.id).not.toBe('')
    expect(container.querySelector(`label[for="${CSS.escape(input.id)}"]`)).not.toBeNull()
    await expectNoA11yViolations(container)
  })

  it('gives each instance a distinct id so two on one page stay independent', () => {
    render(
      <>
        <UserEmailSearch value="" onChange={() => {}} label="Reporter" />
        <UserEmailSearch value="" onChange={() => {}} label="Owner" />
      </>,
    )

    const reporter = screen.getByRole('textbox', { name: 'Reporter' })
    const owner = screen.getByRole('textbox', { name: 'Owner' })
    expect(reporter.id).not.toBe(owner.id)
  })

  it('falls back to the placeholder when no visible label is supplied', () => {
    render(<UserEmailSearch value="" onChange={() => {}} placeholder="Search by email..." />)

    expect(screen.getByRole('textbox', { name: 'Search by email...' })).toBeInTheDocument()
  })

  it('names the clear control after the field it clears', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<UserEmailSearch value="a@b.com" onChange={onChange} label="Reporter" />)

    const clear = screen.getByRole('button', { name: 'Clear Reporter' })
    await user.click(clear)

    expect(onChange).toHaveBeenCalledWith('', undefined)
  })

  it('marks a required field programmatically, not only with an asterisk', () => {
    render(<UserEmailSearch value="" onChange={() => {}} label="Reporter" required />)

    const input = screen.getByRole('textbox', { name: /Reporter/ })
    expect(input).toBeRequired()
    // The asterisk is decorative; "Reporter *" must not become the name.
    expect(input).toHaveAccessibleName('Reporter')
  })
})
