/**
 * P0: Audit Builder → Documents must remount with Documents copy, not
 * audit_templates subtitle stuck from the previous AnimatedOutlet frame.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, Link, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'
import { AnimatedOutlet } from '../AnimatedOutlet'

vi.mock('framer-motion', () => {
  const Passthrough = ({
    children,
    ...props
  }: {
    children?: ReactNode
    [key: string]: unknown
  }) => {
    const { initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
    motion: {
      div: Passthrough,
    },
  }
})

function AuditTemplatesPage() {
  return (
    <div>
      <h1>audit_templates.title</h1>
      <p>audit_templates.subtitle</p>
      <Link to="/documents">Go Documents</Link>
    </div>
  )
}

function DocumentsPage() {
  return (
    <div>
      <h1>documents.title</h1>
      <p>documents.subtitle</p>
    </div>
  )
}

function Shell() {
  return (
    <div>
      <Outlet />
    </div>
  )
}

function RouteGroup() {
  return <AnimatedOutlet />
}

describe('AnimatedOutlet nav sync (Audit Builder → Documents)', () => {
  it('after navigating to documents, subtitle/copy reflects documents (not audit_templates)', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/audit-templates']}>
        <Routes>
          <Route path="/" element={<Shell />}>
            <Route element={<RouteGroup />}>
              <Route path="audit-templates" element={<AuditTemplatesPage />} />
              <Route path="documents" element={<DocumentsPage />} />
            </Route>
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('audit_templates.subtitle')).toBeInTheDocument()
    expect(screen.queryByText('documents.subtitle')).not.toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Go Documents' }))

    await waitFor(() => {
      expect(screen.getByText('documents.subtitle')).toBeInTheDocument()
    })
    expect(screen.queryByText('audit_templates.subtitle')).not.toBeInTheDocument()
    expect(screen.queryByText('audit_templates.title')).not.toBeInTheDocument()
    expect(screen.getByText('documents.title')).toBeInTheDocument()
  })
})
