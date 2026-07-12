import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Actions from '../Actions'

const mockList = vi.fn()
const mockSummary = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => (key === 'actions.view_finding' ? 'View finding' : key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  actionsApi: {
    list: (...args: unknown[]) => mockList(...args),
    summary: (...args: unknown[]) => mockSummary(...args),
    create: vi.fn(),
  },
}))

const action = (overrides: Record<string, unknown>) => ({
  id: 1,
  reference_number: 'ACT-0001',
  title: 'Correct audit finding',
  description: 'Resolve the finding',
  action_type: 'corrective',
  priority: 'high',
  status: 'open',
  display_status: 'open',
  action_key: 'capa:1',
  source_type: 'audit_finding',
  source_id: 42,
  created_at: '2026-07-12T10:00:00Z',
  ...overrides,
})

describe('Actions finding deep-link', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSummary.mockResolvedValue({ data: { total: 3, by_display_status: { open: 3 } } })
  })

  it('links only audit-finding rows with a positive source id', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [
          action({ id: 1, action_key: 'capa:1', source_id: 42 }),
          action({ id: 2, action_key: 'capa:2', source_id: 0 }),
          action({ id: 3, action_key: 'incident_action:3', source_type: 'incident', source_id: 7 }),
        ],
      },
    })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    const links = await screen.findAllByRole('link', { name: 'View finding' })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/audits?view=findings&findingId=42')
  })
})
