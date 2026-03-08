import { render } from '@testing-library/react'
import { expectNoA11yViolations } from '../../test/axe-helper'
import { ToastProvider } from '../../contexts/ToastContext'

describe('Toast accessibility', () => {
  it('has no a11y violations when rendered', async () => {
    const { container } = render(
      <ToastProvider>
        <div>App content</div>
      </ToastProvider>,
    )
    await expectNoA11yViolations(container)
  })
})
