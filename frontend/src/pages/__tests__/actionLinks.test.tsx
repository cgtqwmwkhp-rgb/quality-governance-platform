import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import {
  LegacyActionItemRedirect,
  buildActionDetailPath,
  parseActionDetailId,
} from '../actionLinks'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    Navigate: ({ to, replace }: { to: string; replace?: boolean }) => (
      <div data-testid="navigate" data-to={to} data-replace={String(replace)} />
    ),
  }
})

describe('actionLinks', () => {
  it('buildActionDetailPath encodes action_key for RESTful permalinks', () => {
    expect(buildActionDetailPath('capa:9')).toBe('/actions/capa%3A9')
    expect(buildActionDetailPath('incident_action:3')).toBe('/actions/incident_action%3A3')
    expect(buildActionDetailPath('  ')).toBe('/actions')
  })

  it('parseActionDetailId decodes route params', () => {
    expect(parseActionDetailId('capa%3A9')).toBe('capa:9')
    expect(parseActionDetailId('incident_action%3A3')).toBe('incident_action:3')
    expect(parseActionDetailId(undefined)).toBe('')
    expect(parseActionDetailId('')).toBe('')
  })

  it('LegacyActionItemRedirect sends legacy item URLs to permalinks', () => {
    render(
      <MemoryRouter initialEntries={['/actions/item?key=capa%3A42']}>
        <Routes>
          <Route path="/actions/item" element={<LegacyActionItemRedirect />} />
        </Routes>
      </MemoryRouter>,
    )

    const nav = screen.getByTestId('navigate')
    expect(nav).toHaveAttribute('data-to', '/actions/capa%3A42')
    expect(nav).toHaveAttribute('data-replace', 'true')
  })

  it('LegacyActionItemRedirect falls back to list when key is missing', () => {
    render(
      <MemoryRouter initialEntries={['/actions/item']}>
        <Routes>
          <Route path="/actions/item" element={<LegacyActionItemRedirect />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('navigate')).toHaveAttribute('data-to', '/actions')
  })
})
