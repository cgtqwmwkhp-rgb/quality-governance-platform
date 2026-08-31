import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import RegisterCaptionBanner from '../RegisterCaptionBanner'

describe('RegisterCaptionBanner', () => {
  it('renders a known register without a count by default', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner registerParam="PEL-HSEQ-5033" serverTotal={99} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('PEL-HSEQ-5033')
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('RIDDOR')
    expect(screen.queryByText(/Server total/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Registers' })).toHaveAttribute(
      'href',
      '/registers',
    )
  })

  it('ignores an unknown register param', () => {
    const { container } = render(
      <MemoryRouter>
        <RegisterCaptionBanner registerParam="PEL-FAKE-0000" />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('names a server type filter and may show the SQL total', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner
          registerParam="PEL-HSEQ-5010"
          typeParam="injury"
          serverTotal={12}
          showServerTotal
        />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('type=injury')
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('Server total: 12')
  })

  it('names a statutory server filter', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner
          registerParam="PEL-HSEQ-5056"
          statutoryParam="true"
          serverTotal={4}
          showServerTotal
        />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent(
      'statutory obligations only',
    )
    expect(screen.getByTestId('register-caption-banner')).toHaveTextContent('Server total: 4')
  })

  it('offers the Export Center module export where the register is the module (REG-SSOT-E1)', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner registerParam="PEL-HSEQ-5060" />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-export-btn')).toBeInTheDocument()
    expect(screen.getByTestId('register-export-note')).toHaveTextContent('whole Complaints module')
  })

  it('offers no export for a register that is a subset of its module', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner registerParam="PEL-HSEQ-5033" />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-caption-banner')).toBeInTheDocument()
    expect(screen.queryByTestId('register-export-btn')).not.toBeInTheDocument()
  })

  it('warns that an applied type filter is missing from the export', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner registerParam="PEL-HSEQ-5010" typeParam="injury" />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-export-note')).toHaveTextContent(
      'server filter named above is not applied to the file',
    )
  })

  it('tells a slavery tracker reader the actions list is unfiltered (REG-SSOT-D3)', () => {
    render(
      <MemoryRouter>
        <RegisterCaptionBanner registerParam="PEL-PROC-5014" />
      </MemoryRouter>,
    )
    const banner = screen.getByTestId('register-caption-banner')
    expect(banner).toHaveTextContent('Modern Slavery Action Tracker')
    expect(banner).toHaveTextContent('No extra server filter')
    expect(banner).toHaveTextContent('No dedicated slavery action list in QGP')
  })
})
