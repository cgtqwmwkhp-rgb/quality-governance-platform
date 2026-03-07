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
import { configureAxe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

const axe = configureAxe({
  rules: {
    // Disable color-contrast in JSDOM since it can't compute styles
    'color-contrast': { enabled: false },
    region: { enabled: false },
  },
});

export async function expectNoA11yViolations(container: HTMLElement): Promise<void> {
  const results = await axe(container);
  // @ts-expect-error jest-axe matcher extension
  expect(results).toHaveNoViolations();
}
