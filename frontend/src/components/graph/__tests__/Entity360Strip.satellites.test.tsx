/**
 * Entity360Strip satellite gating (X-3) — requiresSatellites nests under
 * entity_360_satellites without changing DocumentDetail / Job Lifecycle.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Entity360Strip } from '../Entity360Strip'

const getBundle = vi.fn()

const flagState: Record<string, boolean> = {
  entity_360: false,
  entity_360_satellites: false,
}

vi.mock('../../../api/client', () => ({
  entity360Api: {
    getBundle: (...args: unknown[]) => getBundle(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

describe('Entity360Strip requiresSatellites', () => {
  beforeEach(() => {
    getBundle.mockReset()
    flagState.entity_360 = false
    flagState.entity_360_satellites = false
  })

  it('hides and does not fetch when satellites flag is off', () => {
    flagState.entity_360 = true
    flagState.entity_360_satellites = false
    render(
      <MemoryRouter>
        <Entity360Strip entityType="incident" entityId={9} requiresSatellites />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('entity360-connections-strip')).not.toBeInTheDocument()
    expect(getBundle).not.toHaveBeenCalled()
  })

  it('fetches when both entity_360 and satellites are on', async () => {
    flagState.entity_360 = true
    flagState.entity_360_satellites = true
    getBundle.mockResolvedValue({
      data: { complete: true, upstream: [], downstream: [], sources: [] },
    })
    render(
      <MemoryRouter>
        <Entity360Strip entityType="capa" entityId={12} requiresSatellites />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('entity360-connections-strip')).toBeInTheDocument()
    await waitFor(() => {
      expect(getBundle).toHaveBeenCalledWith('capa', 12)
    })
  })

  it('ignores satellites flag when requiresSatellites is unset', async () => {
    flagState.entity_360 = true
    flagState.entity_360_satellites = false
    getBundle.mockResolvedValue({
      data: { complete: true, upstream: [], downstream: [], sources: [] },
    })
    render(
      <MemoryRouter>
        <Entity360Strip entityType="document" entityId={3} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('entity360-connections-strip')).toBeInTheDocument()
    await waitFor(() => {
      expect(getBundle).toHaveBeenCalledWith('document', 3)
    })
  })
})
