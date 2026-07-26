import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

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
    expect(banner).toHaveTextContent(/scripted sample content/i)
    expect(screen.getByRole('heading', { name: 'AI Copilot (Demo)' })).toBeInTheDocument()
  })

  it('warns in the opening message that the figures are invented', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)

    await renderCopilot()

    expect(screen.getByText(/invented illustrations/i)).toBeInTheDocument()
    expect(screen.getByText(/not connected to any AI model/i)).toBeInTheDocument()
  })
})
