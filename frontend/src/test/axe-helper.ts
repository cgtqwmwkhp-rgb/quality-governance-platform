/**
 * Accessibility test helper using axe-core.
 *
 * Usage in component tests:
 *
 *   import { render } from '@testing-library/react';
 *   import { expectNoA11yViolations } from '../test/axe-helper';
 *
 *   it('has no accessibility violations', async () => {
 *     const { container } = render(<MyComponent />);
 *     await expectNoA11yViolations(container);
 *   });
 */
import { configureAxe, toHaveNoViolations } from 'jest-axe'

expect.extend(toHaveNoViolations)

const axe = configureAxe({
  rules: {
    // color-contrast: enabled — JSDOM reports as "incomplete" (not violation)
    // so this won't cause false failures; Lighthouse CI covers real browser checks.
    region: { enabled: false },
  },
})

export async function expectNoA11yViolations(container: HTMLElement): Promise<void> {
  const results = await axe(container)
  // @ts-expect-error jest-axe matcher extension
  expect(results).toHaveNoViolations()
}
