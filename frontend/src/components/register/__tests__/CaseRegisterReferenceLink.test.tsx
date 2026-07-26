import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CaseRegisterReferenceLink } from '../CaseRegisterReferenceLink'
import { CaseRegisterTable } from '../CaseRegisterTable'

describe('CaseRegisterReferenceLink', () => {
  it('PX-200: renders a real href that can be opened in a new tab', () => {
    render(
      <MemoryRouter>
        <CaseRegisterReferenceLink to="/rtas/42">RTA-2026-0031</CaseRegisterReferenceLink>
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'RTA-2026-0031' })
    expect(link).toHaveAttribute('href', '/rtas/42')
  })

  it('PX-173: reference link sits inside a plain row without role=button', () => {
    render(
      <MemoryRouter>
        <CaseRegisterTable
          label="RTAs"
          rows={[{ id: 42, reference: 'RTA-2026-0031' }]}
          rowKey={(row) => row.id}
          onOpenRow={() => undefined}
          rowLabel={(row) => `View ${row.reference}`}
          empty={null}
          columns={[
            {
              key: 'reference',
              header: 'Reference',
              width: 'reference',
              render: (row) => (
                <CaseRegisterReferenceLink to={`/rtas/${row.id}`}>{row.reference}</CaseRegisterReferenceLink>
              ),
            },
          ]}
        />
      </MemoryRouter>,
    )

    const row = screen.getByLabelText('View RTA-2026-0031')
    expect(row.tagName).toBe('TR')
    expect(row).not.toHaveAttribute('role', 'button')
    expect(screen.getByRole('link', { name: 'RTA-2026-0031' })).toHaveAttribute('href', '/rtas/42')
  })
})
