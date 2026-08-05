import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { workforceApi } from '../../api/client'
import { EngineerPeoplePicker } from '../EngineerPeoplePicker'

vi.mock('../../api/client', () => ({
  workforceApi: {
    listEngineers: vi.fn(),
  },
}))

const ROSTER_ONLY = {
  id: 31,
  display_name: 'Warwick, C',
  job_title: 'Technician',
  user_id: null,
}

const WITH_LOGIN = {
  id: 12,
  display_name: 'Harris, D',
  job_title: 'Manager',
  user_id: 4,
  linked_user: { id: 4, email: 'david@example.com', full_name: 'David Harris' },
}

function mockRoster(items: unknown[]) {
  vi.mocked(workforceApi.listEngineers).mockResolvedValue({
    data: { items, total: items.length },
  } as never)
}

async function openPicker() {
  const input = await screen.findByPlaceholderText('Search employees…')
  fireEvent.focus(input)
  return input
}

describe('EngineerPeoplePicker', () => {
  beforeEach(() => {
    vi.mocked(workforceApi.listEngineers).mockReset()
  })

  describe('when a login is required (case owners, action assignees)', () => {
    it('disables roster-only people and tells the user how to make them assignable', async () => {
      mockRoster([ROSTER_ONLY])
      render(<EngineerPeoplePicker onChange={vi.fn()} requireLogin />)
      await openPicker()

      const option = await screen.findByRole('button', { name: /Warwick, C/ })
      expect(option).toBeDisabled()
      expect(
        screen.getByText('No login — link on Employees profile to assign'),
      ).toBeInTheDocument()
    })

    it('cannot be bypassed by clicking the disabled row', async () => {
      mockRoster([ROSTER_ONLY])
      const onChange = vi.fn()
      render(<EngineerPeoplePicker onChange={onChange} requireLogin />)
      await openPicker()

      fireEvent.click(await screen.findByRole('button', { name: /Warwick, C/ }))
      expect(onChange).not.toHaveBeenCalled()
    })
  })

  describe('when a login is not required (investigation lead, named roles)', () => {
    it('does not tell the user to link a login, and says naming carries no notification', async () => {
      mockRoster([ROSTER_ONLY])
      render(<EngineerPeoplePicker onChange={vi.fn()} requireLogin={false} />)
      await openPicker()

      expect(
        await screen.findByText('No login — can be named, but will not be notified'),
      ).toBeInTheDocument()
      expect(
        screen.queryByText('No login — link on Employees profile to assign'),
      ).not.toBeInTheDocument()
    })

    it('lets a roster-only person be selected by name', async () => {
      mockRoster([ROSTER_ONLY])
      const onChange = vi.fn()
      render(<EngineerPeoplePicker onChange={onChange} requireLogin={false} />)
      await openPicker()

      const option = await screen.findByRole('button', { name: /Warwick, C/ })
      expect(option).toBeEnabled()
      fireEvent.click(option)

      await waitFor(() =>
        expect(onChange).toHaveBeenCalledWith({
          engineerId: 31,
          label: 'Warwick, C — Technician',
          user: undefined,
          hasLogin: false,
        }),
      )
    })
  })

  it('shows the email for a linked person regardless of the surface', async () => {
    mockRoster([WITH_LOGIN])
    render(<EngineerPeoplePicker onChange={vi.fn()} requireLogin />)
    await openPicker()

    expect(await screen.findByText('david@example.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Harris, D/ })).toBeEnabled()
  })
})
