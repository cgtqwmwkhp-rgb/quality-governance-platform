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
})
