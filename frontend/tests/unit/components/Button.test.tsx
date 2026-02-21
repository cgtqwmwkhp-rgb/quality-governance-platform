import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../../../src/components/ui/Button';

describe('Button', () => {
  it('renders with text content', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeTruthy();
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    fireEvent.click(screen.getByText('Click'));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('renders with default variant', () => {
    const { container } = render(<Button>Default</Button>);
    expect(container.querySelector('button')).toBeTruthy();
  });

  it('renders with outline variant', () => {
    render(<Button variant="outline">Outline</Button>);
    expect(screen.getByText('Outline')).toBeTruthy();
  });

  it('renders with ghost variant', () => {
    render(<Button variant="ghost">Ghost</Button>);
    expect(screen.getByText('Ghost')).toBeTruthy();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByText('Disabled').closest('button')?.disabled).toBe(true);
  });

  it('renders with different sizes', () => {
    render(<Button size="sm">Small</Button>);
    expect(screen.getByText('Small')).toBeTruthy();
  });
});
