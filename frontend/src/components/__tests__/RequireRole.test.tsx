import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RequireRole from '../RequireRole'

const hasRole = vi.fn()
const isSuperuser = vi.fn()

vi.mock('../../utils/auth', () => ({
  hasRole: (...args: string[]) => hasRole(...args),
  isSuperuser: () => isSuperuser(),
}))

function renderGate(props?: Partial<React.ComponentProps<typeof RequireRole>>) {
  return render(
    <MemoryRouter initialEntries={['/secure']}>
      <Routes>
        <Route
          path="/secure"
          element={
            <RequireRole allowed={['admin']} {...props}>
              <div>secret</div>
            </RequireRole>
          }
        />
        <Route path="/dashboard" element={<div>dashboard</div>} />
        <Route path="/denied" element={<div>denied</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireRole', () => {
  beforeEach(() => {
    hasRole.mockReset()
    isSuperuser.mockReset()
  })

  it('renders children when role is allowed', () => {
    hasRole.mockReturnValue(true)
    isSuperuser.mockReturnValue(false)
    renderGate()
    expect(screen.getByText('secret')).toBeInTheDocument()
  })

  it('redirects to fallback when role is missing', () => {
    hasRole.mockReturnValue(false)
    isSuperuser.mockReturnValue(false)
    renderGate({ fallback: '/denied' })
    expect(screen.getByText('denied')).toBeInTheDocument()
  })

  it('requires superuser when gate is enabled', () => {
    hasRole.mockReturnValue(true)
    isSuperuser.mockReturnValue(false)
    renderGate({ requireSuperuser: true })
    expect(screen.getByText('dashboard')).toBeInTheDocument()

    isSuperuser.mockReturnValue(true)
    renderGate({ requireSuperuser: true })
    expect(screen.getByText('secret')).toBeInTheDocument()
  })
})
