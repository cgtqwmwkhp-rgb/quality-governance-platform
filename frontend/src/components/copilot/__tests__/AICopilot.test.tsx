import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const isAICopilotDemoEnabledMock = vi.fn(() => false)

vi.mock('../../../config/aiCopilotDemo', () => ({
  isAICopilotDemoEnabled: () => isAICopilotDemoEnabledMock(),
}))

describe('AICopilot', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    onClose.mockClear()
    isAICopilotDemoEnabledMock.mockReset()
    isAICopilotDemoEnabledMock.mockReturnValue(false)
  })

  async function renderCopilot() {
    const AICopilot = (await import('../AICopilot')).default
    return render(<AICopilot isOpen onClose={onClose} />)
  }

  it('renders nothing when the demo flag is off, even if mounted open', async () => {
    const { container } = await renderCopilot()

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('never emits the simulated welcome content while the flag is off', async () => {
    const { container } = await renderCopilot()

    expect(container.textContent).toBe('')
  })

  it('renders the chat surface when the demo flag is on', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    expect(screen.getByPlaceholderText('Ask me anything...')).toBeInTheDocument()
    expect(screen.getByTitle('Minimize')).toBeInTheDocument()
  })

  it('labels the enabled surface as a non-production demo', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    const banner = screen.getByTestId('ai-copilot-demo-banner')
    expect(banner).toHaveTextContent(/demonstration only/i)
    expect(banner).toHaveTextContent(/refused/i)
    expect(screen.getByRole('heading', { name: 'AI Copilot (Demo)' })).toBeInTheDocument()
  })

  it('warns in the opening message that live-data answers are refused', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    const welcome = screen.getAllByTestId('copilot-markdown')[0]
    expect(welcome).toHaveTextContent(/refuse live-data questions/i)
    expect(welcome).toHaveTextContent(/not connected to any AI model/i)
  })

  it('PX-248: refuses fabricated compliance figures instead of inventing 92%', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    const user = userEvent.setup()
    await renderCopilot()

    await user.type(screen.getByPlaceholderText('Ask me anything...'), 'Compliance Status')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByText(/cannot answer from live organisation data/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/92%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Overall Compliance/i)).not.toBeInTheDocument()
  })

  it('PX-248: refuses invented named risks on Risk Summary', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    const user = userEvent.setup()
    await renderCopilot()

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
    const user = userEvent.setup()
    await renderCopilot()

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
    const user = userEvent.setup()
    await renderCopilot()

    await user.type(screen.getByPlaceholderText('Ask me anything...'), 'what is CAPA')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByTestId('copilot-markdown')).toBeInTheDocument()
    })
    const md = screen.getByTestId('copilot-markdown')
    expect(md.querySelector('strong')).toBeTruthy()
    expect(md.textContent).not.toMatch(/\*\*CAPA/)
  })

  it('does not suggest Compliance Status or Risk Summary prompts', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
    await renderCopilot()

    expect(screen.queryByText('Compliance Status')).not.toBeInTheDocument()
    expect(screen.queryByText('Risk Summary')).not.toBeInTheDocument()
    expect(screen.getByText('What is CAPA?')).toBeInTheDocument()
  })
})
