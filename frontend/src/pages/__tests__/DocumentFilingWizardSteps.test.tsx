import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { DocumentFilingFunctionStep } from '../DocumentFilingFunctionStep'
import { DocumentFilingRelatedPlaceholder } from '../DocumentFilingRelatedPlaceholder'
import { DocumentFilingControlStub } from '../DocumentFilingControlStub'

const mockGet = vi.fn()
const mockToastError = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}))

function FunctionStepHarness({
  onConfirm,
  onBack,
}: {
  onConfirm: (functionCode: string | null, cascadeLevel: number | null) => void
  onBack: () => void
}) {
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [selectedCascadeLevel, setSelectedCascadeLevel] = useState<number | null>(null)
  return (
    <DocumentFilingFunctionStep
      fileName="policy.pdf"
      selectedCode={selectedCode}
      onSelectedCodeChange={setSelectedCode}
      selectedCascadeLevel={selectedCascadeLevel}
      onSelectedCascadeLevelChange={setSelectedCascadeLevel}
      onConfirm={onConfirm}
      onBack={onBack}
    />
  )
}

describe('DocumentFilingFunctionStep', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({
      data: [
        { id: 1, code: 'HSEQ', name: 'Health, Safety, Environment & Quality', sort_order: 1, active: true },
        { id: 2, code: 'IT', name: 'Information Technology', sort_order: 2, active: true },
      ],
    })
  })

  it('loads functions from the WA-2 vocabulary endpoint and confirms a code with its level', async () => {
    const onConfirm = vi.fn()
    const onBack = vi.fn()
    render(<FunctionStepHarness onConfirm={onConfirm} onBack={onBack} />)

    expect(await screen.findByTestId('documents-filing-function-step')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/api/v1/document-categories/functions')
    })

    // Radix Select: open trigger then pick HSEQ
    fireEvent.click(screen.getByTestId('documents-filing-function-select'))
    const option = await screen.findByTestId('documents-filing-function-option-HSEQ')
    fireEvent.click(option)

    // NS-1: a function alone is not enough — the PEL reference is banded by
    // cascade level, so Continue stays shut until the level is chosen.
    expect(screen.getByTestId('documents-filing-function-continue')).toBeDisabled()
    expect(screen.getByTestId('documents-filing-level-required')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('documents-filing-level-select'))
    fireEvent.click(await screen.findByTestId('documents-filing-level-option-3'))

    fireEvent.click(screen.getByTestId('documents-filing-function-continue'))
    expect(onConfirm).toHaveBeenCalledWith('HSEQ', 3)
  })

  it('allows upload without a function (API optional; required later in full WD-1)', async () => {
    const onConfirm = vi.fn()
    render(<FunctionStepHarness onConfirm={onConfirm} onBack={vi.fn()} />)
    await screen.findByTestId('documents-filing-function-file')
    fireEvent.click(await screen.findByTestId('documents-filing-function-continue'))
    // No function means no PEL reference, so no level is demanded either.
    expect(onConfirm).toHaveBeenCalledWith(null, null)
  })

  it('lets a filer record a level without a function', async () => {
    const onConfirm = vi.fn()
    render(<FunctionStepHarness onConfirm={onConfirm} onBack={vi.fn()} />)
    await screen.findByTestId('documents-filing-function-file')

    fireEvent.click(screen.getByTestId('documents-filing-level-select'))
    fireEvent.click(await screen.findByTestId('documents-filing-level-option-1'))

    fireEvent.click(screen.getByTestId('documents-filing-function-continue'))
    expect(onConfirm).toHaveBeenCalledWith(null, 1)
  })
})

describe('DocumentFilingRelatedPlaceholder', () => {
  it('is honest when document_graph is off and does not invent edges UI', () => {
    const onContinue = vi.fn()
    render(
      <DocumentFilingRelatedPlaceholder documentTitle="Safety Policy" onContinue={onContinue} />,
    )
    expect(screen.getByTestId('documents-filing-related-placeholder')).toBeInTheDocument()
    expect(screen.getByText('documents.filing.related_off.title')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('documents-filing-related-continue'))
    expect(onContinue).toHaveBeenCalled()
  })
})

describe('DocumentFilingControlStub', () => {
  it('states Bring under control waits for WC-1 and finishes the spine', () => {
    const onDone = vi.fn()
    render(<DocumentFilingControlStub onDone={onDone} />)
    expect(screen.getByTestId('documents-filing-control-stub')).toBeInTheDocument()
    expect(screen.getByText('documents.filing.control_stub.title')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('documents-filing-control-done'))
    expect(onDone).toHaveBeenCalled()
  })
})
