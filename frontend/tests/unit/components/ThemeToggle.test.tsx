import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../../../src/contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    resolvedTheme: 'light',
    setTheme: vi.fn(),
    toggleTheme: vi.fn(),
  }),
}));

import { ThemeToggle } from '../../../src/components/ui/ThemeToggle';

describe('ThemeToggle', () => {
  it('renders theme toggle button (icon variant)', () => {
    render(<ThemeToggle />);
    expect(screen.getByLabelText('Switch to dark mode')).toBeTruthy();
  });

  it('renders full variant with Light, Dark, System buttons', () => {
    render(<ThemeToggle variant="full" />);
    expect(screen.getByText('Light')).toBeTruthy();
    expect(screen.getByText('Dark')).toBeTruthy();
    expect(screen.getByText('System')).toBeTruthy();
  });

  it('applies custom className', () => {
    const { container } = render(<ThemeToggle className="my-class" />);
    expect(container.querySelector('.my-class')).toBeTruthy();
  });
});
