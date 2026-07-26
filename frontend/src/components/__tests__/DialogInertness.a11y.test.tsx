import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/Dialog'
import { Button } from '../ui/Button'
import PublishDialog from '../../pages/audit-builder/PublishDialog'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

/**
 * PX-162 claimed the background stays exposed to assistive technology while a
 * modal is open. That holds for hand-rolled overlays, not for the shared Dialog
 * primitive — these tests pin the difference so the claim cannot silently
 * become true again.
 */
describe('modal background inertness', () => {
  it('removes the page behind the shared Dialog from the accessibility tree', () => {
    render(
      <>
        <Button>Background action</Button>
        <Dialog open>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Incident</DialogTitle>
            </DialogHeader>
            <Button>Create incident</Button>
          </DialogContent>
        </Dialog>
      </>,
    )

    expect(screen.getByRole('dialog', { name: 'New Incident' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create incident' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Background action' })).not.toBeInTheDocument()

    // Still in the DOM — it is hidden from the accessibility tree, not unmounted.
    expect(screen.getByText('Background action')).toBeInTheDocument()
  })

  it('moves focus into the dialog when it opens', () => {
    render(
      <>
        <Button>Background action</Button>
        <Dialog open>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Incident</DialogTitle>
            </DialogHeader>
            <Button>Create incident</Button>
          </DialogContent>
        </Dialog>
      </>,
    )

    const dialog = screen.getByRole('dialog', { name: 'New Incident' })
    expect(dialog.contains(document.activeElement)).toBe(true)
  })

  it('gives the dialog close control an accessible name', () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Incident</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>,
    )

    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })
})

describe('audit builder PublishDialog', () => {
  const props = {
    isOpen: true,
    onClose: () => {},
    onConfirm: () => {},
    isPublishing: false,
    templateName: 'Depot inspection',
  }

  it('is a real dialog with a name, and hides the page behind it', () => {
    render(
      <>
        <Button>Background action</Button>
        <PublishDialog {...props} />
      </>,
    )

    const dialog = screen.getByRole('dialog', { name: 'Publish Template' })
    expect(dialog).toBeInTheDocument()
    expect(dialog.contains(document.activeElement)).toBe(true)
    expect(screen.queryByRole('button', { name: 'Background action' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('renders nothing while closed', () => {
    render(<PublishDialog {...props} isOpen={false} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
