import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { Switch } from '../../../src/components/ui/Switch';

describe('Switch', () => {
  it('renders switch toggle', () => {
    const { container } = render(<Switch />);
    expect(container.querySelector('button')).toBeTruthy();
  });

  it('renders in unchecked state by default', () => {
    const { container } = render(<Switch />);
    const button = container.querySelector('button');
    expect(button?.getAttribute('data-state')).toBe('unchecked');
  });

  it('renders in checked state when checked', () => {
    const { container } = render(<Switch checked />);
    const button = container.querySelector('button');
    expect(button?.getAttribute('data-state')).toBe('checked');
  });

  it('calls onCheckedChange when toggled', () => {
    const handleChange = vi.fn();
    const { container } = render(<Switch onCheckedChange={handleChange} />);
    const button = container.querySelector('button')!;
    fireEvent.click(button);
    expect(handleChange).toHaveBeenCalled();
  });

  it('is disabled when disabled prop is set', () => {
    const { container } = render(<Switch disabled />);
    expect(container.querySelector('button')?.hasAttribute('disabled')).toBe(true);
  });
});
