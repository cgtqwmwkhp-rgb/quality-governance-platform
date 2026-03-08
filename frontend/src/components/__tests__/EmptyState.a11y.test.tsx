import { render } from '@testing-library/react'
import { expectNoA11yViolations } from '../../test/axe-helper'
import { EmptyState } from '../ui/EmptyState'
import { Button } from '../ui/Button'

describe('EmptyState accessibility', () => {
  it('has no a11y violations with all props', async () => {
    const { container } = render(
      <EmptyState
        icon={
          <span role="img" aria-label="search">
            🔍
          </span>
        }
        title="No results found"
        description="Try adjusting your search or filters."
        action={<Button>Reset Filters</Button>}
      />,
    )
    await expectNoA11yViolations(container)
  })

  it('has no a11y violations with minimal props', async () => {
    const { container } = render(<EmptyState title="Nothing here yet" />)
    await expectNoA11yViolations(container)
  })
})
