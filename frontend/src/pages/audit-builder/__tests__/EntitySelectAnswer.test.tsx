import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockUsersSearch = vi.fn()
const mockListLocations = vi.fn()
const mockLookupsList = vi.fn()

vi.mock('../../../api/client', () => ({
  usersApi: {
    search: (...args: unknown[]) => mockUsersSearch(...args),
  },
  lookupsApi: {
    list: (...args: unknown[]) => mockLookupsList(...args),
  },
  getApiErrorMessage: (err: unknown, fallback?: string) =>
    err instanceof Error ? err.message : fallback || 'error',
}))

vi.mock('../../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listLocations: (...args: unknown[]) => mockListLocations(...args),
  },
}))

import EntitySelectAnswer from '../EntitySelectAnswer'

describe('EntitySelectAnswer', () => {
  beforeEach(() => {
    mockUsersSearch.mockReset()
    mockListLocations.mockReset()
    mockLookupsList.mockReset()
  })

  it('searches users after debounce and emits stable id + label on select', async () => {
    mockUsersSearch.mockResolvedValue({
      data: [
        { id: 42, email: 'jane@example.com', full_name: 'Jane Doe', display_name: 'Jane Doe' },
      ],
    })
    const onChange = vi.fn()

    render(<EntitySelectAnswer kind="user" value="" onChange={onChange} />)

    const input = screen.getByLabelText('Search for a user')
    fireEvent.change(input, { target: { value: 'jane' } })

    await waitFor(() => expect(mockUsersSearch).toHaveBeenCalledWith('jane'), { timeout: 2000 })

    const option = await screen.findByText('Jane Doe')
    await userEvent.click(option)

    expect(onChange).toHaveBeenCalledWith('42', 'Jane Doe')
  })

  it('clears the selected user id when the search text is edited', async () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <EntitySelectAnswer kind="user" value="42" label="Jane Doe" onChange={onChange} />,
    )

    const input = screen.getByLabelText('Search for a user')
    fireEvent.change(input, { target: { value: 'Jane D' } })
    expect(onChange).toHaveBeenCalledWith('', undefined)

    rerender(<EntitySelectAnswer kind="user" value="" label={undefined} onChange={onChange} />)
    expect(input).toHaveValue('Jane D')
  })

  it('shows an error message when location loading fails', async () => {
    mockListLocations.mockRejectedValue(new Error('network down'))

    render(<EntitySelectAnswer kind="location" value="" onChange={vi.fn()} />)

    expect(await screen.findByText('network down')).toBeInTheDocument()
  })

  it('paginates locations beyond the first page', async () => {
    mockListLocations
      .mockResolvedValueOnce({
        data: {
          items: Array.from({ length: 200 }, (_, i) => ({ id: i + 1, name: `Loc ${i + 1}` })),
          total: 201,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [{ id: 201, name: 'Loc 201' }],
          total: 201,
        },
      })

    render(<EntitySelectAnswer kind="location" value="" onChange={vi.fn()} />)

    expect(await screen.findByLabelText('Select a location')).toBeInTheDocument()
    await waitFor(() => expect(mockListLocations).toHaveBeenCalledTimes(2))
    expect(screen.getByText('Loc 201')).toBeInTheDocument()
  })

  it('renders a customer select populated from active lookup options, keyed by code', async () => {
    mockLookupsList.mockResolvedValue({
      items: [
        { code: 'ukpn', label: 'UK Power Networks', is_active: true },
        { code: 'retired', label: 'Retired Co', is_active: false },
      ],
    })
    const onChange = vi.fn()

    render(<EntitySelectAnswer kind="customer" value="" onChange={onChange} />)

    const select = await screen.findByLabelText('Select a customer')
    expect(screen.getByText('UK Power Networks')).toBeInTheDocument()
    expect(screen.queryByText('Retired Co')).not.toBeInTheDocument()

    await userEvent.selectOptions(select, 'ukpn')
    expect(onChange).toHaveBeenCalledWith('ukpn', 'UK Power Networks')
  })

  it('shows an empty state when no locations are configured', async () => {
    mockListLocations.mockResolvedValue({ data: { items: [], total: 0 } })

    render(<EntitySelectAnswer kind="location" value="" onChange={vi.fn()} />)

    expect(await screen.findByText(/No locations configured yet/)).toBeInTheDocument()
  })
})
