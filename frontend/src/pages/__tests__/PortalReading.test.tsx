import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PortalReading from '../PortalReading'

const mockListMyAssignments = vi.fn()
const mockOpenAssignment = vi.fn()
const mockGetAssignmentQuiz = vi.fn()
const mockSubmitQuiz = vi.fn()
const mockCompleteAssignment = vi.fn()
const mockCreateThread = vi.fn()
const mockPostMessage = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()
const mockAnnounce = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    listMyAssignments: (...args: unknown[]) => mockListMyAssignments(...args),
    openAssignment: (...args: unknown[]) => mockOpenAssignment(...args),
    getAssignmentQuiz: (...args: unknown[]) => mockGetAssignmentQuiz(...args),
    submitQuiz: (...args: unknown[]) => mockSubmitQuiz(...args),
    completeAssignment: (...args: unknown[]) => mockCompleteAssignment(...args),
  },
  knowledgeBankApi: {
    createThread: (...args: unknown[]) => mockCreateThread(...args),
    postMessage: (...args: unknown[]) => mockPostMessage(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Request failed',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}))

vi.mock('../../components/ui/LiveAnnouncer', () => ({
  useLiveAnnouncer: () => ({ announce: mockAnnounce }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function renderPage(initialEntry = '/portal/reading') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PortalReading />
    </MemoryRouter>,
  )
}

describe('PortalReading O-08', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListMyAssignments.mockResolvedValue({
      data: {
        items: [
          {
            id: 7,
            document_id: 42,
            document_title: 'H&S Policy',
            campaign_title: 'Q3 rollout',
            status: 'pending',
            due_date: '2026-08-01',
            quiz_required: true,
          },
        ],
        total: 1,
      },
    })
    mockOpenAssignment.mockResolvedValue({ data: { id: 7, status: 'opened' } })
    mockGetAssignmentQuiz.mockResolvedValue({
      data: {
        pass_mark: 80,
        questions: [
          { question_index: 0, question_text: 'Pick one', question_type: 'mcq', options: ['Yes', 'No'] },
        ],
      },
    })
    mockSubmitQuiz.mockResolvedValue({ data: { score: 100, passed: true } })
    mockCompleteAssignment.mockResolvedValue({ data: { id: 7, status: 'completed' } })
    mockCreateThread.mockResolvedValue({ data: { id: 99 } })
    mockPostMessage.mockResolvedValue({ data: { id: 1, body: 'Help?' } })
  })

  it('loads assignments and renders mobile campaign cards', async () => {
    renderPage()

    expect(await screen.findByTestId('portal-reading-assignment-7')).toBeInTheDocument()
    expect(screen.getByText('H&S Policy')).toBeInTheDocument()
    expect(mockListMyAssignments).toHaveBeenCalled()
  })

  it('records open and launches document in a new tab', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    renderPage()

    await screen.findByTestId('portal-reading-assignment-7')
    await userEvent.click(screen.getByRole('button', { name: /Open \/ Read/i }))

    await waitFor(() => {
      expect(mockOpenAssignment).toHaveBeenCalledWith(7)
      expect(openSpy).toHaveBeenCalledWith('/documents/42', '_blank', 'noopener,noreferrer')
    })
    openSpy.mockRestore()
  })

  it('expands quiz + completion flow and completes assignment', async () => {
    renderPage('/portal/reading?assignment=7')

    await screen.findByTestId('portal-reading-assignment-7')
    await waitFor(() => {
      expect(screen.getByTestId('portal-reading-complete-7')).toBeInTheDocument()
      expect(mockGetAssignmentQuiz).toHaveBeenCalledWith(7)
    })

    await waitFor(() => {
      expect(screen.getByText('Yes')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Yes'))
    await userEvent.click(screen.getByRole('button', { name: /Submit quiz/i }))
    await waitFor(() => expect(mockSubmitQuiz).toHaveBeenCalled())

    await userEvent.click(screen.getByRole('button', { name: /Complete assignment/i }))
    await waitFor(() => expect(mockCompleteAssignment).toHaveBeenCalledWith(7, expect.any(Object)))
  })

  it('sends ask-question to knowledge bank thread', async () => {
    renderPage()

    await screen.findByTestId('portal-reading-assignment-7')
    await userEvent.click(screen.getByRole('button', { name: /Ask a question/i }))
    await userEvent.type(
      screen.getByLabelText(/Ask a question/i),
      'What PPE is required on site?',
    )
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))

    await waitFor(() => {
      expect(mockCreateThread).toHaveBeenCalledWith(42, expect.objectContaining({ title: expect.any(String) }))
      expect(mockPostMessage).toHaveBeenCalledWith(99, { body: 'What PPE is required on site?' })
    })
  })
})
