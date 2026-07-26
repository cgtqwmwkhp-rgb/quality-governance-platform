import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ExportCenter from '../ExportCenter'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('ExportCenter', () => {
  it('shows honest unavailable state without fabricated module counts (PX-011 / PX-160)', () => {
    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('export-center-unavailable')).toBeInTheDocument()
    expect(screen.getByText('Export Center not available yet')).toBeInTheDocument()
    expect(
      screen.getByText(/not wired to live APIs yet/i),
    ).toBeInTheDocument()
    // PX-160: no fake bulk-export / job-history UI while those APIs do not exist.
    expect(screen.queryByText(/847 records|312 records|156 records/)).not.toBeInTheDocument()
    expect(screen.queryByText('Monthly Incident Report')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /export|download|run job/i })).not.toBeInTheDocument()
  })
})
