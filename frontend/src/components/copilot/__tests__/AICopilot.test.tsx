import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { CopilotMessage } from '../../../api/copilot'

const isAICopilotDemoEnabledMock = vi.fn(() => false)

const createSessionMock = vi.fn()
const sendMessageMock = vi.fn()
const listSessionsMock = vi.fn()
const submitFeedbackMock = vi.fn()

vi.mock('../../../config/aiCopilotDemo', () => ({
  isAICopilotDemoEnabled: () => isAICopilotDemoEnabledMock(),
}))

vi.mock('../../../api/copilot', async () => {
  const actual = await vi.importActual<typeof import('../../../api/copilot')>(
    '../../../api/copilot',
  )
  return {
    ...actual,
    copilotApi: {
      createSession: (...args: unknown[]) => createSessionMock(...args),
      sendMessage: (...args: unknown[]) => sendMessageMock(...args),
      listSessions: (...args: unknown[]) => listSessionsMock(...args),
      submitFeedback: (...args: unknown[]) => submitFeedbackMock(...args),
    },
  }
})

function apiMessage(partial: Partial<CopilotMessage> & Pick<CopilotMessage, 'content'>): CopilotMessage {
  return {
    id: partial.id ?? 42,
    session_id: partial.session_id ?? 1,
    role: partial.role ?? 'assistant',
    content: partial.content,
    content_type: partial.content_type ?? 'text',
    action_type: partial.action_type ?? null,
    action_data: partial.action_data ?? null,
    action_result: partial.action_result ?? null,
    action_status: partial.action_status ?? null,
    created_at: partial.created_at ?? new Date().toISOString(),
  }
}

function axiosLikeError(status: number, detail?: string) {
  return {
    isAxiosError: true,
    response: { status, data: { detail: detail ?? 'AI Copilot is not enabled in this environment.' } },
    message: `Request failed with status code ${status}`,
  }
}

describe('AICopilot', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    onClose.mockClear()
    isAICopilotDemoEnabledMock.mockReset()
    isAICopilotDemoEnabledMock.mockReturnValue(false)
    createSessionMock.mockReset()
    sendMessageMock.mockReset()
    listSessionsMock.mockReset()
    submitFeedbackMock.mockReset()

    createSessionMock.mockResolvedValue({
      data: {
        id: 1,
        title: null,
        context_type: null,
        context_id: null,
        is_active: true,
        created_at: new Date().toISOString(),
        last_message_at: null,
      },
    })
    sendMessageMock.mockResolvedValue({
      data: apiMessage({ content: 'Mocked assistant reply' }),
    })
    submitFeedbackMock.mockResolvedValue({ data: { status: 'submitted', feedback_id: 1 } })
  })

  async function renderCopilot() {
    const AICopilot = (await import('../AICopilot')).default
    return render(<AICopilot isOpen onClose={onClose} />)
  }

  it('renders nothing when the demo flag is off, even if mounted open', async () => {
    const { container } = await renderCopilot()

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(createSessionMock).not.toHaveBeenCalled()
  })

  it('never emits the simulated welcome content while the flag is off', async () => {
    const { container } = await renderCopilot()

    expect(container.textContent).toBe('')
  })

  it('renders the chat surface when the demo flag is on', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask me anything...')).toBeInTheDocument()
    })
    expect(screen.getByTitle('Minimize')).toBeInTheDocument()
    expect(createSessionMock).toHaveBeenCalledTimes(1)
  })

  it('labels the enabled surface as a non-production demo', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    const banner = await screen.findByTestId('ai-copilot-demo-banner')
    expect(banner).toHaveTextContent(/demonstration only/i)
    expect(banner).toHaveTextContent(/refused/i)
    expect(screen.getByRole('heading', { name: 'AI Copilot (Demo)' })).toBeInTheDocument()
  })

  it('warns in the opening message that live-data answers are refused', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    await waitFor(() => {
      expect(screen.getAllByTestId('copilot-markdown')[0]).toHaveTextContent(
        /refuse live-data questions/i,
      )
    })
    const welcome = screen.getAllByTestId('copilot-markdown')[0]
    expect(welcome).toHaveTextContent(/not connected to any AI model/i)
  })

  it('shows unavailable state on 404 and never falls back to canned local answers', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    createSessionMock.mockRejectedValue(axiosLikeError(404))

    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByTestId('ai-copilot-unavailable')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-copilot-unavailable')).toHaveTextContent(
      /not enabled in this environment/i,
    )
    expect(screen.queryByText(/92%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Overall Compliance/i)).not.toBeInTheDocument()
    expect(sendMessageMock).not.toHaveBeenCalled()
  })

  it('PX-248: refuses fabricated compliance figures via API instead of inventing 92%', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    sendMessageMock.mockResolvedValue({
      data: apiMessage({
        content:
          'I cannot answer from live organisation data. This demo is not connected to your registers.',
        content_type: 'action',
        action_type: 'get_compliance_status',
        action_status: 'not_performed',
        action_result: { performed: false, reason: 'no_live_data' },
      }),
    })
    const user = userEvent.setup()
    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask me anything...')).not.toBeDisabled()
    })

    await user.type(screen.getByPlaceholderText('Ask me anything...'), 'Compliance Status')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByText(/cannot answer from live organisation data/i)).toBeInTheDocument()
    })
    expect(sendMessageMock).toHaveBeenCalledWith(1, 'Compliance Status')
    expect(screen.queryByText(/92%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Overall Compliance/i)).not.toBeInTheDocument()
  })

  it('PX-248: refuses invented named risks on Risk Summary via API', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    sendMessageMock.mockResolvedValue({
      data: apiMessage({
        content:
          'I cannot answer from live organisation data. Open the Risk Register for the live register.',
        content_type: 'action',
        action_type: 'get_risk_summary',
        action_status: 'not_performed',
      }),
    })
    const user = userEvent.setup()
    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask me anything...')).not.toBeDisabled()
    })

    await user.type(screen.getByPlaceholderText('Ask me anything...'), 'Risk Summary')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByText(/cannot answer from live organisation data/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/Supply Chain Disruption/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Cybersecurity Threat/i)).not.toBeInTheDocument()
  })

  it('PX-250: refuses incident creation without claiming Action completed', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    sendMessageMock.mockResolvedValue({
      data: apiMessage({
        content:
          'I cannot create or update records from this demo. Nothing was written. Use the Incidents register (New) to log a real safety event.',
        content_type: 'action',
        action_type: 'create_incident',
        action_status: 'not_performed',
        action_result: { performed: false, reason: 'demo_cannot_write' },
      }),
    })
    const user = userEvent.setup()
    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask me anything...')).not.toBeDisabled()
    })

    await user.type(
      screen.getByPlaceholderText('Ask me anything...'),
      'create an incident for a slip in the yard',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByTestId('copilot-action-not-performed')).toBeInTheDocument()
    })
    expect(screen.getByText(/cannot create or update records/i)).toBeInTheDocument()
    expect(screen.queryByText(/Action completed/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Shall I proceed/i)).not.toBeInTheDocument()
  })

  it('PX-249: renders markdown bold instead of raw ** markers', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    sendMessageMock.mockResolvedValue({
      data: apiMessage({
        content:
          '**CAPA (Corrective and Preventive Action)** is a systematic approach.\n\n_General guidance only._',
      }),
    })
    const user = userEvent.setup()
    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask me anything...')).not.toBeDisabled()
    })

    await user.type(screen.getByPlaceholderText('Ask me anything...'), 'what is CAPA')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      const mdBlocks = screen.getAllByTestId('copilot-markdown')
      expect(mdBlocks.some((el) => el.querySelector('strong'))).toBe(true)
    })
    const capaBlock = screen
      .getAllByTestId('copilot-markdown')
      .find((el) => el.textContent?.includes('CAPA'))
    expect(capaBlock).toBeTruthy()
    expect(capaBlock!.textContent).not.toMatch(/\*\*CAPA/)
  })

  it('does not suggest Compliance Status or Risk Summary prompts', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByText('What is CAPA?')).toBeInTheDocument()
    })
    expect(screen.queryByText('Compliance Status')).not.toBeInTheDocument()
    expect(screen.queryByText('Risk Summary')).not.toBeInTheDocument()
  })

  it('does not call generateResponse-style local simulation — replies come from sendMessage', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    sendMessageMock.mockResolvedValue({
      data: apiMessage({ content: 'Backend-only reply for unique-token-xyz' }),
    })
    const user = userEvent.setup()
    await renderCopilot()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask me anything...')).not.toBeDisabled()
    })

    await user.type(screen.getByPlaceholderText('Ask me anything...'), 'hello there')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByText(/unique-token-xyz/i)).toBeInTheDocument()
    })
    expect(sendMessageMock).toHaveBeenCalledWith(1, 'hello there')
  })
})
