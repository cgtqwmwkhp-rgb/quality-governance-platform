import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PortalReading from '../PortalReading'

const mockListMyAssignments = vi.fn()
const mockOpenAssignment = vi.fn()
const mockGetAssignmentDocumentUrl = vi.fn()
const mockGetAssignmentQuiz = vi.fn()
const mockSubmitQuiz = vi.fn()
const mockCompleteAssignment = vi.fn()
const mockAskAssignmentQuestion = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()
const mockAnnounce = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../../api/client', () => ({
  default: {
    defaults: { baseURL: 'http://localhost:8000' },
  },
  documentCampaignApi: {
    listMyAssignments: (...args: unknown[]) => mockListMyAssignments(...args),
    openAssignment: (...args: unknown[]) => mockOpenAssignment(...args),
    getAssignmentDocumentUrl: (...args: unknown[]) => mockGetAssignmentDocumentUrl(...args),
    getAssignmentQuiz: (...args: unknown[]) => mockGetAssignmentQuiz(...args),
    submitQuiz: (...args: unknown[]) => mockSubmitQuiz(...args),
    completeAssignment: (...args: unknown[]) => mockCompleteAssignment(...args),
    askAssignmentQuestion: (...args: unknown[]) => mockAskAssignmentQuestion(...args),
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
            quiz_attempts: 0,
          },
        ],
        total: 1,
      },
    })
    mockOpenAssignment.mockResolvedValue({ data: { id: 7, status: 'opened' } })
    mockGetAssignmentDocumentUrl.mockResolvedValue({
      data: { signed_url: 'https://storage.example/doc.pdf?sig=abc' },
    })
    mockGetAssignmentQuiz.mockResolvedValue({
      data: {
        pass_mark: 80,
        questions: [
          { question_index: 0, question_text: 'Pick one', question_type: 'mcq', options: ['Yes', 'No'] },
        ],
      },
    })
    mockSubmitQuiz.mockResolvedValue({ data: { score: 100, passed: true, quiz_attempts: 1 } })
    mockCompleteAssignment.mockResolvedValue({ data: { id: 7, status: 'completed' } })
    mockAskAssignmentQuestion.mockResolvedValue({ data: { id: 99 } })
  })

  it('loads assignments and renders mobile campaign cards', async () => {
    renderPage()

    expect(await screen.findByTestId('portal-reading-assignment-7')).toBeInTheDocument()
    expect(screen.getByText('H&S Policy')).toBeInTheDocument()
    expect(mockListMyAssignments).toHaveBeenCalled()
  })

  it('records open and launches signed document URL in a new tab', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    renderPage()

    await screen.findByTestId('portal-reading-assignment-7')
    await userEvent.click(screen.getByRole('button', { name: /Open \/ Read/i }))

    await waitFor(() => {
      expect(mockOpenAssignment).toHaveBeenCalledWith(7)
      expect(mockGetAssignmentDocumentUrl).toHaveBeenCalledWith(7)
      expect(openSpy).toHaveBeenCalledWith(
        'https://storage.example/doc.pdf?sig=abc',
        '_blank',
        'noopener,noreferrer',
      )
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

    await userEvent.click(screen.getByRole('radio', { name: 'Yes' }))
    await userEvent.click(screen.getByRole('button', { name: /Submit quiz/i }))
    await waitFor(() => expect(mockSubmitQuiz).toHaveBeenCalled())

    const gate = await screen.findByTestId('portal-reading-question-gate-7')
    await userEvent.click(within(gate).getByRole('button', { name: 'No' }))
    await userEvent.type(screen.getByLabelText(/Signature \(required\)/i), 'Alex Engineer')
    await userEvent.click(screen.getByRole('button', { name: /Complete assignment/i }))
    await waitFor(() =>
      expect(mockCompleteAssignment).toHaveBeenCalledWith(7, {
        acceptance_statement: expect.any(String),
        signature_disposition: 'signed',
        signature_data: 'Alex Engineer',
      }),
    )
  })

  it('sends ask-question via campaign assignment API', async () => {
    renderPage()

    await screen.findByTestId('portal-reading-assignment-7')
    await userEvent.click(screen.getByRole('button', { name: /Ask a question/i }))
    await userEvent.type(
      screen.getByLabelText(/Ask a question/i),
      'What PPE is required on site?',
    )
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))

    await waitFor(() => {
      expect(mockAskAssignmentQuestion).toHaveBeenCalledWith(7, {
        title: 'What PPE is required on site?',
        body: 'What PPE is required on site?',
      })
    })
  })
})
