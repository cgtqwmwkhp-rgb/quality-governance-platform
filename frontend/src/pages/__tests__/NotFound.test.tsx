import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import NotFound from '../NotFound'

const navigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

describe('NotFound', () => {
  it('renders 404 copy and navigates on CTA clicks', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/missing']}>
        <Routes>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('404')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /page not found/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /go back/i }))
    expect(navigate).toHaveBeenCalledWith(-1)

    await user.click(screen.getByRole('button', { name: /go to dashboard/i }))
    expect(navigate).toHaveBeenCalledWith('/dashboard')
  })
})
