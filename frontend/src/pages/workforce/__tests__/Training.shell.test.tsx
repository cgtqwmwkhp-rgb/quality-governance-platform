import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : _key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../api/client', () => ({
  trainingMatrixApi: {
    listCompliance: vi.fn().mockResolvedValue({ items: [], total: 0, atlas_hub_url: 'https://atlas' }),
    getLatestImportQa: vi.fn().mockRejectedValue(new Error('none')),
    myTraining: vi.fn().mockResolvedValue({ items: [], total: 0, atlas_hub_url: 'https://atlas' }),
    listNameMaps: vi.fn().mockResolvedValue([]),
    listRequirements: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listCourses: vi.fn().mockResolvedValue([]),
    uploadImport: vi.fn(),
    upsertNameMap: vi.fn(),
    createRequirement: vi.fn(),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({ data: { items: [] } }),
    listInductions: vi.fn().mockResolvedValue({ data: { items: [] } }),
    listAssetTypes: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  auditsApi: {
    listTemplates: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  getApiErrorMessage: (e: unknown) => (e instanceof Error ? e.message : 'error'),
  ATLAS_HUB_URL: 'https://www.atlas-hub.co.uk/o/98b88f4e-2c3f-44c1-a812-36ea66222c7d/',
}))

import Training from '../Training'

describe('Training shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders compliance tabs and switches to Admin', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('training-shell')).toBeInTheDocument()
    expect(screen.getByTestId('training-matrix-gap-board')).toBeInTheDocument()

    await user.click(screen.getByTestId('training-tab-admin'))
    expect(await screen.findByTestId('training-matrix-admin')).toBeInTheDocument()
  })
})
