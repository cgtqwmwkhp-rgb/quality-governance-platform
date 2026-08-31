import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RegisterExportButton from '../RegisterExportButton'

const toastSuccess = vi.fn()
const toastError = vi.fn()

vi.mock('../../../config/apiBase', () => ({
  API_BASE_URL: 'http://api.test',
}))

vi.mock('../../../utils/auth', () => ({
  getPlatformToken: () => 'test-token',
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: {
    success: (msg: string) => toastSuccess(msg),
    error: (msg: string) => toastError(msg),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

const overlay = { module: 'incidents', moduleLabel: 'Incidents' } as const

function stubDownloadPlumbing() {
  const createObjectURL = vi.fn(() => 'blob:register-export')
  const revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
  const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  return { createObjectURL, anchorClick }
}

describe('RegisterExportButton', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    toastSuccess.mockClear()
    toastError.mockClear()
  })

  it('posts the register tag to the existing Export Center endpoint', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async () => ({
      ok: true,
      blob: async () => new Blob(['id,title\n'], { type: 'text/csv' }),
      headers: {
        get: (name: string) =>
          name === 'Content-Disposition'
            ? 'attachment; filename="incidents_export_PEL-HSEQ-5010_20260831.csv"'
            : name === 'X-Export-Truncated'
              ? 'false'
              : null,
      },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const { anchorClick } = stubDownloadPlumbing()

    render(<RegisterExportButton docRef="PEL-HSEQ-5010" overlay={overlay} />)

    await user.click(screen.getByTestId('register-export-btn'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/v1/exports',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            module: 'incidents',
            format: 'csv',
            register: 'PEL-HSEQ-5010',
          }),
        }),
      )
    })
    expect(anchorClick).toHaveBeenCalled()
    expect(toastSuccess).toHaveBeenCalledWith(
      'incidents_export_PEL-HSEQ-5010_20260831.csv downloaded — whole Incidents module.',
    )
  })

  it('says the file is the whole module, not a per-register dump', () => {
    render(<RegisterExportButton docRef="PEL-HSEQ-5010" overlay={overlay} />)

    const note = screen.getByTestId('register-export-note')
    expect(note).toHaveTextContent('whole Incidents module')
    expect(note).toHaveTextContent('not a separate PEL-HSEQ-5010 extract')
    expect(note).not.toHaveTextContent('server filter named above')
  })

  it('warns that a server filter on screen is not applied to the file', () => {
    render(
      <RegisterExportButton docRef="PEL-HSEQ-5010" overlay={overlay} serverFilterApplied />,
    )

    expect(screen.getByTestId('register-export-note')).toHaveTextContent(
      'server filter named above is not applied to the file',
    )
  })

  it('reports a row cap instead of claiming a full module', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        blob: async () => new Blob(['id\n'], { type: 'text/csv' }),
        headers: {
          get: (name: string) =>
            name === 'Content-Disposition'
              ? 'attachment; filename="incidents_export_PEL-HSEQ-5010_20260831.csv"'
              : name === 'X-Export-Truncated'
                ? 'true'
                : null,
        },
      })),
    )
    stubDownloadPlumbing()

    render(<RegisterExportButton docRef="PEL-HSEQ-5010" overlay={overlay} />)
    await user.click(screen.getByTestId('register-export-btn'))

    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith(
        'incidents_export_PEL-HSEQ-5010_20260831.csv downloaded — row cap reached, so this is not the whole Incidents module.',
      )
    })
  })

  it('surfaces the server refusal rather than a silent no-op', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Register 'PEL-HSEQ-5033' has no Export Center overlay." }),
      })),
    )
    stubDownloadPlumbing()

    render(<RegisterExportButton docRef="PEL-HSEQ-5010" overlay={overlay} />)
    await user.click(screen.getByTestId('register-export-btn'))

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        "Register 'PEL-HSEQ-5033' has no Export Center overlay.",
      )
    })
    expect(screen.getByTestId('register-export-btn')).not.toBeDisabled()
  })
})
