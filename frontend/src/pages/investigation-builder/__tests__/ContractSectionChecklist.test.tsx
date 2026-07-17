import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContractSectionChecklist } from '../ContractSectionChecklist'
import { assessContractCompliance, createInc043ScaffoldSections } from '../contractSections'

describe('ContractSectionChecklist', () => {
  it('renders INC043 checklist with mapped counts', () => {
    const checklist = assessContractCompliance(createInc043ScaffoldSections())
    render(<ContractSectionChecklist checklist={checklist} />)

    expect(screen.getByTestId('inc043-section-checklist')).toBeInTheDocument()
    expect(screen.getByText(/7\/7 sections mapped/)).toBeInTheDocument()
    expect(screen.getByText('1. Basic Information')).toBeInTheDocument()
    expect(screen.getByText('7. Lessons Learned')).toBeInTheDocument()
  })
})
