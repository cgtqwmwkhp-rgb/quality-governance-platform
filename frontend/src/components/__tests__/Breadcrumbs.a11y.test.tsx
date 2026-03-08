import { render } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { expectNoA11yViolations } from '../../test/axe-helper'
import { Breadcrumbs } from '../ui/Breadcrumbs'

describe('Breadcrumbs accessibility', () => {
  it('has no a11y violations', async () => {
    const { container } = render(
      <BrowserRouter>
        <Breadcrumbs
          items={[{ label: 'Incidents', href: '/incidents' }, { label: 'INC-2026-0001' }]}
        />
      </BrowserRouter>,
    )
    await expectNoA11yViolations(container)
  })

  it('marks the last item as current page', () => {
    const { getByText } = render(
      <BrowserRouter>
        <Breadcrumbs items={[{ label: 'Home', href: '/' }, { label: 'Detail Page' }]} />
      </BrowserRouter>,
    )
    expect(getByText('Detail Page')).toHaveAttribute('aria-current', 'page')
  })
})
