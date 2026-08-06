import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RecordCompletionSheet } from '../RecordCompletionSheet'

const {
  mockComplete,
  mockUpload,
  mockDelete,
  mockToastSuccess,
  mockToastError,
} = vi.hoisted(() => ({
  mockComplete: vi.fn(),
  mockUpload: vi.fn(),
  mockDelete: vi.fn(),
  mockToastSuccess: vi.fn(),
  mockToastError: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: string | { defaultValue?: string }) => {
      if (typeof opts === 'string') return opts
      if (opts?.defaultValue) return opts.defaultValue
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: {
    success: mockToastSuccess,
    error: mockToastError,
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('../../../api/client', () => ({
  complianceScheduleApi: {
    completeRequirement: mockComplete,
  },
  evidenceAssetsApi: {
    upload: mockUpload,
    delete: mockDelete,
  },
}))

function renderSheet(
  overrides: Partial<{
    open: boolean
    onOpenChange: (open: boolean) => void
    onCompleted: () => void
  }> = {},
) {
  const onOpenChange = overrides.onOpenChange ?? vi.fn()
  const onCompleted = overrides.onCompleted ?? vi.fn()
  render(
    <RecordCompletionSheet
      open={overrides.open ?? true}
      onOpenChange={onOpenChange}
      requirementId={42}
      requirementTitle="Fire Risk Assessment"
      nextDueDate="2026-09-01"
      onCompleted={onCompleted}
    />,
  )
  return { onOpenChange, onCompleted }
}

describe('RecordCompletionSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockComplete.mockResolvedValue({ data: { id: 99 } })
    mockUpload.mockImplementation(async (_file: File, _data: unknown) => ({
      data: { id: mockUpload.mock.calls.length + 100 },
    }))
    mockDelete.mockResolvedValue({})
  })

  it('completes without evidence_asset_ids when no files are attached', async () => {
    const user = userEvent.setup()
    const { onCompleted, onOpenChange } = renderSheet()

    await user.click(screen.getByTestId('compliance-schedule-complete-submit'))

    await waitFor(() => {
      expect(mockComplete).toHaveBeenCalledWith(
        42,
        expect.objectContaining({
          check_passed: true,
          evidence_asset_ids: undefined,
        }),
      )
    })
    expect(mockUpload).not.toHaveBeenCalled()
    expect(mockToastSuccess).toHaveBeenCalled()
    expect(onCompleted).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('uploads staged files then passes evidence_asset_ids on complete', async () => {
    const user = userEvent.setup()
    renderSheet()

    const input = screen.getByTestId('compliance-schedule-complete-evidence-input')
    const file = new File(['fra-pdf'], 'fra.pdf', { type: 'application/pdf' })
    await user.upload(input, file)

    expect(screen.getByTestId('compliance-schedule-complete-evidence-list')).toHaveTextContent(
      'fra.pdf',
    )

    await user.click(screen.getByTestId('compliance-schedule-complete-submit'))

    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledWith(
        file,
        expect.objectContaining({
          source_module: 'induction',
          source_id: 42,
          title: 'fra.pdf',
        }),
      )
      expect(mockComplete).toHaveBeenCalledWith(
        42,
        expect.objectContaining({
          evidence_asset_ids: [101],
        }),
      )
    })
    expect(mockDelete).not.toHaveBeenCalled()
  })

  it('discards staged uploads when complete fails', async () => {
    const user = userEvent.setup()
    mockComplete.mockRejectedValueOnce(new Error('conflict'))
    mockUpload.mockResolvedValueOnce({ data: { id: 55 } })
    renderSheet()

    const input = screen.getByTestId('compliance-schedule-complete-evidence-input')
    await user.upload(input, new File(['x'], 'photo.jpg', { type: 'image/jpeg' }))
    await user.click(screen.getByTestId('compliance-schedule-complete-submit'))

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith(55)
      expect(mockToastError).toHaveBeenCalled()
    })
  })

  it('resets notes and pending files when the sheet reopens', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const { rerender } = render(
      <RecordCompletionSheet
        open
        onOpenChange={onOpenChange}
        requirementId={42}
        requirementTitle="Fire Risk Assessment"
        nextDueDate="2026-09-01"
        onCompleted={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('Notes'), 'done')
    const input = screen.getByTestId('compliance-schedule-complete-evidence-input')
    await user.upload(input, new File(['a'], 'a.pdf', { type: 'application/pdf' }))
    expect(screen.getByTestId('compliance-schedule-complete-evidence-list')).toBeInTheDocument()

    rerender(
      <RecordCompletionSheet
        open={false}
        onOpenChange={onOpenChange}
        requirementId={42}
        requirementTitle="Fire Risk Assessment"
        nextDueDate="2026-09-01"
        onCompleted={vi.fn()}
      />,
    )
    rerender(
      <RecordCompletionSheet
        open
        onOpenChange={onOpenChange}
        requirementId={42}
        requirementTitle="Fire Risk Assessment"
        nextDueDate="2026-09-01"
        onCompleted={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Notes')).toHaveValue('')
    expect(screen.queryByTestId('compliance-schedule-complete-evidence-list')).not.toBeInTheDocument()
  })
})
