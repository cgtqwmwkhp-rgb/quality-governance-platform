import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { LibraryShell } from '../LibraryShell'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('LibraryShell', () => {
  it('renders unified Library title and view-specific subtitle', () => {
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <LibraryShell activeView="documents">child content</LibraryShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'nav.library' })).toBeInTheDocument()
    expect(screen.getByText('documents.subtitle')).toBeInTheDocument()
    expect(screen.getByText('child content')).toBeInTheDocument()
  })

  it('marks the Documents tab active on /documents', () => {
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <LibraryShell activeView="documents">content</LibraryShell>
      </MemoryRouter>,
    )

    const documentsTab = screen.getByRole('link', { name: /nav\.documents/i })
    const policiesTab = screen.getByRole('link', { name: /nav\.policies/i })

    expect(documentsTab).toHaveAttribute('aria-current', 'page')
    expect(policiesTab).not.toHaveAttribute('aria-current')
    expect(documentsTab).toHaveAttribute('href', '/documents')
    expect(policiesTab).toHaveAttribute('href', '/policies')
  })

  it('marks the Policies tab active on /policies', () => {
    render(
      <MemoryRouter initialEntries={['/policies']}>
        <LibraryShell activeView="policies">content</LibraryShell>
      </MemoryRouter>,
    )

    const documentsTab = screen.getByRole('link', { name: /nav\.documents/i })
    const policiesTab = screen.getByRole('link', { name: /nav\.policies/i })

    expect(policiesTab).toHaveAttribute('aria-current', 'page')
    expect(documentsTab).not.toHaveAttribute('aria-current')
  })

  it('renders header actions when provided', () => {
    render(
      <MemoryRouter>
        <LibraryShell activeView="documents" actions={<button type="button">Upload</button>}>
          content
        </LibraryShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: 'Upload' })).toBeInTheDocument()
  })
})
