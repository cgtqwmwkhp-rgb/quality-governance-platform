import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Avatar } from '../Avatar'

describe('Avatar', () => {
  it('renders as a display element (div with role="img") without onClick', () => {
    render(<Avatar alt="Jane Doe" />)

    const avatar = screen.getByRole('img', { name: 'Jane Doe' })
    expect(avatar.tagName).toBe('DIV')
    expect(avatar).toHaveTextContent('JD')
  })

  it('renders as a button when onClick is provided', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    render(<Avatar alt="Jane Doe" onClick={handleClick} />)

    const avatar = screen.getByRole('button', { name: 'Jane Doe' })
    expect(avatar.tagName).toBe('BUTTON')

    await user.click(avatar)
    expect(handleClick).toHaveBeenCalledOnce()
  })

  it('displays initials from alt text when no src is provided', () => {
    render(<Avatar alt="Alice Bob Charlie" />)

    // Should take first two initials: "AB"
    const avatar = screen.getByRole('img', { name: 'Alice Bob Charlie' })
    expect(avatar).toHaveTextContent('AB')
  })

  it('uses fallback text over computed initials', () => {
    render(<Avatar alt="Jane Doe" fallback="X" />)

    const avatar = screen.getByRole('img', { name: 'Jane Doe' })
    expect(avatar).toHaveTextContent('X')
  })
})
