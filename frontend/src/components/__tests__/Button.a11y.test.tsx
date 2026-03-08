import { render } from '@testing-library/react'
import { expectNoA11yViolations } from '../../test/axe-helper'
import { Button } from '../ui/Button'

describe('Button accessibility', () => {
  it('has no a11y violations with default variant', async () => {
    const { container } = render(<Button>Click me</Button>)
    await expectNoA11yViolations(container)
  })

  it('has no a11y violations when disabled', async () => {
    const { container } = render(<Button disabled>Disabled</Button>)
    await expectNoA11yViolations(container)
  })

  it('has no a11y violations with destructive variant', async () => {
    const { container } = render(<Button variant="destructive">Delete</Button>)
    await expectNoA11yViolations(container)
  })
})
