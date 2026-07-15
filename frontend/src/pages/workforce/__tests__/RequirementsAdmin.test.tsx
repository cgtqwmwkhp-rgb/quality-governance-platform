import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const list = vi.fn()

const { t } = vi.hoisted(() => ({
  t: (key: string) => key,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../api/client', () => ({
  workforceApi: { competencyRequirements: { list } },
  getApiErrorMessage: (error: unknown, fallback?: string) =>
    error instanceof Error ? error.message : (fallback ?? 'error'),
}))

describe('RequirementsAdmin', () => {
  beforeEach(() => {
    list.mockReset()
  })

  it('lists configured requirements for a supervisor', async () => {
    list.mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            asset_type_id: 2,
            template_id: 5,
            name: 'MEWP competence',
            is_mandatory: true,
            reassessment_interval_days: 365,
            site: 'Cardiff',
            tenant_id: 1,
            created_at: '2026-07-15T00:00:00Z',
            updated_at: '2026-07-15T00:00:00Z',
          },
        ],
      },
    })
    const RequirementsAdmin = (await import('../RequirementsAdmin')).default

    render(<RequirementsAdmin />)

    expect(await screen.findByTestId('requirements-admin-table')).toBeInTheDocument()
    expect(screen.getByText('MEWP competence')).toBeInTheDocument()
    expect(screen.getByText('Cardiff')).toBeInTheDocument()
    expect(list).toHaveBeenCalledWith({ page_size: 100 })
  })

  it('shows a retryable error instead of an empty requirements list', async () => {
    list.mockRejectedValue(new Error('Requirements service unavailable'))
    const RequirementsAdmin = (await import('../RequirementsAdmin')).default

    render(<RequirementsAdmin />)

    expect(await screen.findByTestId('requirements-admin-error')).toHaveTextContent(
      'Requirements service unavailable',
    )
    expect(screen.queryByTestId('requirements-admin-empty')).not.toBeInTheDocument()
  })
})
