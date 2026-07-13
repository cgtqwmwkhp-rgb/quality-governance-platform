import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PresenceIndicator from '../PresenceIndicator'

describe('PresenceIndicator', () => {
  it('renders an online pulse indicator with optional label', () => {
    const { container } = render(<PresenceIndicator status="online" showLabel />)

    expect(screen.getByText('Online')).toBeInTheDocument()
    expect(container.querySelector('.animate-ping')).toBeTruthy()
    expect(container.querySelector('.bg-emerald-500')).toBeTruthy()
  })

  it('renders away / busy / offline without pulse and with labels', () => {
    const { rerender, container } = render(<PresenceIndicator status="away" showLabel />)
    expect(screen.getByText('Away')).toBeInTheDocument()
    expect(container.querySelector('.animate-ping')).toBeNull()
    expect(container.querySelector('.bg-yellow-500')).toBeTruthy()

    rerender(<PresenceIndicator status="busy" showLabel />)
    expect(screen.getByText('Busy')).toBeInTheDocument()
    expect(container.querySelector('.bg-red-500')).toBeTruthy()

    rerender(<PresenceIndicator status="offline" showLabel />)
    expect(screen.getByText('Offline')).toBeInTheDocument()
    expect(container.querySelector('.bg-gray-500')).toBeTruthy()
  })

  it('hides the status label by default and applies size classes', () => {
    const { container, rerender } = render(<PresenceIndicator status="online" />)
    expect(screen.queryByText('Online')).not.toBeInTheDocument()
    expect(container.querySelector('.w-3.h-3')).toBeTruthy()

    rerender(<PresenceIndicator status="online" size="sm" />)
    expect(container.querySelector('.w-2.h-2')).toBeTruthy()

    rerender(<PresenceIndicator status="online" size="lg" className="extra-class" />)
    expect(container.querySelector('.w-4.h-4')).toBeTruthy()
    expect(container.firstChild).toHaveClass('extra-class')
  })
})
