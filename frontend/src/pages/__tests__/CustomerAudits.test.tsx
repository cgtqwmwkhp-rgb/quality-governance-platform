import { describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import CustomerAudits from '../CustomerAudits'

vi.mock('react-router-dom', () => ({
  Navigate: ({ to, replace }: { to: string; replace?: boolean }) => (
    <div data-testid="navigate" data-to={to} data-replace={String(replace ?? false)} />
  ),
}))

describe('CustomerAudits', () => {
  it('redirects legacy /customer-audits to the Audits customer filter', () => {
    render(<CustomerAudits />)
    const redirect = document.querySelector('[data-testid="navigate"]')
    expect(redirect).toHaveAttribute('data-to', '/audits?source=customer')
    expect(redirect).toHaveAttribute('data-replace', 'true')
  })
})
